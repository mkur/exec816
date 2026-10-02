#include "gem-service.h"
#include <clib/alib_protos.h>

UWORD GemAddressExtent(const void *pointer, ULONG bytes)
{
    ULONG address = (ULONG)pointer;
    return address >= 0x10000UL && address <= 0xffffffUL && bytes &&
           bytes <= 0x1000000UL - address;
}

UWORD GemUpperExtent(const void *pointer, ULONG bytes)
{
    ULONG address = (ULONG)pointer;
    return GemAddressExtent(pointer, bytes) && !(address & 1) &&
           bytes <= 0x10000UL - (address & 0xffffUL);
}

static UWORD array_extent(UWORD offset, ULONG bytes, ULONG first, UWORD total)
{
    if (!bytes)
        return offset == 0;
    return !(offset & 1) && offset >= first && offset <= total && bytes <= (ULONG)total - offset;
}

UWORD GemValidatePacket(const struct GemRequest *r)
{
    const struct GemCommand *commands;
    ULONG first;
    UWORD i, status;
    /* The caller supplies a valid Exec Message even for malformed headers. */
    if (!GemUpperExtent(r, GEM_REQUEST_BYTES) || r->message.mn_Length < GEM_REQUEST_BYTES)
        return GEM_BAD_PACKET;
    if (r->total_bytes != r->message.mn_Length || r->total_bytes > GEM_LIMIT_PACKET_BYTES ||
        !GemUpperExtent(r, r->total_bytes) || r->version != GEM_VERSION || r->flags || r->reserved)
        return GEM_BAD_PACKET;
    if (r->operation == GEM_OP_CLOSE || r->operation == GEM_OP_STOP)
        return r->command_count == 0 && r->total_bytes == GEM_REQUEST_BYTES ? GEM_OK : GEM_BAD_PACKET;
    if (r->operation != GEM_OP_OPEN && r->operation != GEM_OP_SUBMIT)
        return GEM_UNSUPPORTED;
    if (!r->command_count || r->command_count > GEM_LIMIT_COMMANDS ||
        (r->operation == GEM_OP_OPEN && r->command_count != 1))
        return GEM_BAD_PACKET;
    first = GEM_REQUEST_BYTES + (ULONG)r->command_count * GEM_COMMAND_BYTES;
    if (first > r->total_bytes)
        return GEM_BAD_PACKET;
    commands = (const struct GemCommand *)(r + 1);
    for (i = 0; i < r->command_count; ++i) {
        const struct GemCommand *c = &commands[i];
        if (!array_extent(c->points_offset, (ULONG)c->point_pairs * 4, first, r->total_bytes) ||
            !array_extent(c->ints_offset, (ULONG)c->int_words * 2, first, r->total_bytes))
            return GEM_BAD_PACKET;
        status = GemValidateCommand(r->operation, c, (const WORD *)((const UBYTE *)r + c->ints_offset));
        if (status != GEM_OK)
            return status;
    }
    return GEM_OK;
}

static UWORD close_session(struct GemServer *s)
{
    UWORD status = GEM_OK;
    if (s->session) {
        status = s->backend->close(s->backend->context);
        s->session = 0;
        s->next_sequence = 0;
    }
    return status == GEM_OK ? GEM_OK : GEM_DEVICE_FAULT;
}

static UWORD process(struct GemServer *s, struct GemRequest *r)
{
    UWORD status, i, j;
    const struct GemCommand *commands = (const struct GemCommand *)(r + 1);
    if (r->operation == GEM_OP_STOP) {
        if (r != s->stop_packet || r->session || r->sequence ||
            r->message.mn_ReplyPort->mp_SigTask != s->owner)
            return GEM_BAD_SESSION;
        return close_session(s);
    }
    if (r->operation == GEM_OP_OPEN && s->session)
        return GEM_BUSY;
    if (r != s->inflight || r->message.mn_ReplyPort != s->client_reply ||
        r->message.mn_ReplyPort->mp_SigTask != s->owner)
        return GEM_BAD_SESSION;
    if (r->operation == GEM_OP_OPEN) {
        if (r->session || r->sequence != 1)
            return GEM_BAD_SESSION;
        if (s->generation == 0xffffffffUL)
            return GEM_EXHAUSTED;
        status = s->backend->open(s->backend->context, r->reply);
        if (status != GEM_OK)
            return status; /* Open failure must roll back inside the backend. */
        status = s->backend->fence(s->backend->context);
        if (status != GEM_OK) {
            s->backend->close(s->backend->context);
            return GEM_DEVICE_FAULT;
        }
        s->session = ++s->generation;
        s->next_sequence = 2;
        r->session = s->session;
        r->completed_count = 1;
        r->reply_words = GEM_LIMIT_REPLY_WORDS;
        return GEM_OK;
    }
    if (!s->session || r->session != s->session || r->sequence != s->next_sequence)
        return GEM_BAD_SESSION;
    if (r->operation == GEM_OP_CLOSE)
        return close_session(s);
    if (s->next_sequence == 0xffffffffUL)
        return GEM_EXHAUSTED; /* The final sequence is reserved for CLOSE. */
    ++s->next_sequence;
    for (i = 0; i < r->command_count; ++i) {
        struct GemCommand command = commands[i];
        const WORD *points = (const WORD *)((const UBYTE *)r + command.points_offset);
        const WORD *ints = (const WORD *)((const UBYTE *)r + command.ints_offset);
        WORD result = 0;
        for (j = 0; j < command.point_pairs * 2; ++j)
            s->scratch->points[j] = points[j];
        for (j = 0; j < command.int_words; ++j)
            s->scratch->ints[j] = ints[j];
        status = s->backend->command(s->backend->context, &command,
                                    s->scratch->points, s->scratch->ints, &result);
        /* Count only fenced commands, so a failed fence has an honest prefix. */
        if (status == GEM_OK)
            status = s->backend->fence(s->backend->context);
        if (status != GEM_OK) {
            close_session(s);
            return GEM_DEVICE_FAULT;
        }
        if (GemCommandReplyWords(command.opcode))
            r->reply[r->reply_words++] = result;
        ++r->completed_count;
    }
    return GEM_OK;
}

static void release_worker(struct GemServer *s)
{
    if (s->scratch) {
        FreeMem(s->scratch, sizeof(*s->scratch));
        s->scratch = NULL;
    }
    if (s->port) {
        DeleteMsgPort(s->port);
        s->port = NULL;
    }
}

/* Startup owns this reserve until the supervisor collects the terminal STOP.
 * The worker never frees a port whose signal belongs to the supervisor. */
static void release_stop(struct GemServer *s)
{
    if (s->stop_packet) {
        FreeMem(s->stop_packet, GEM_REQUEST_BYTES);
        s->stop_packet = NULL;
    }
    if (s->stop_replies) {
        DeleteMsgPort(s->stop_replies);
        s->stop_replies = NULL;
    }
}

void GemServiceWorker(void)
{
    struct Task *self = FindTask(NULL);
    struct GemServer *s = self->tc_UserData;
    struct GemRequest *stop = NULL;
    struct Task *owner;
    if (!GemAddressExtent(s, sizeof(*s)) || s->state != GEM_STARTING ||
        s->worker != self || s->worker_lease.task != self ||
        s->worker_lease.identity != (void *)&s->worker_lease)
        return;
    owner = s->owner;
    s->port = CreateMsgPort();
    if (s->port)
        s->scratch = AllocMem(sizeof(*s->scratch), MEMF_PUBLIC | MEMF_CLEAR);
    if (!s->port || !s->scratch) {
        release_worker(s);
        Forbid();
        s->startup_result = GEM_NO_MEMORY;
        s->state = GEM_RETIRED;
        s->worker = NULL;
        ReleaseTask(&s->owner_lease);
        ReleaseTask(&s->worker_lease);
        Signal(owner, s->ready_mask);
        RemTask(NULL);
        return;
    }
    Forbid();
    s->startup_result = GEM_OK;
    s->state = GEM_RUNNING;
    Signal(owner, s->ready_mask);
    Permit();
    while (!stop) {
        struct GemRequest *r;
        UWORD status;
        WaitPort(s->port);
        r = (struct GemRequest *)GetMsg(s->port);
        /* Short/invalid envelopes have no writable service reply fields. */
        if (!GemUpperExtent(r, GEM_REQUEST_BYTES) || r->message.mn_Length < GEM_REQUEST_BYTES) {
            ReplyMsg(&r->message);
            continue;
        }
        r->completed_count = r->reply_words = 0;
        status = GemValidatePacket(r);
        if (status == GEM_OK) {
            status = process(s, r);
            if ((status == GEM_OK || status == GEM_DEVICE_FAULT) &&
                r == s->stop_packet && r->operation == GEM_OP_STOP &&
                r->session == 0 && r->sequence == 0)
                stop = r;
        }
        r->result = status;
        if (!stop)
            ReplyMsg(&r->message); /* Never dereference r after this call. */
    }
    /* Admission closed before STOP was queued. Drain any rejected raw traffic. */
    for (;;) {
        struct GemRequest *r = (struct GemRequest *)GetMsg(s->port);
        if (!r)
            break;
        if (GemUpperExtent(r, GEM_REQUEST_BYTES) && r->message.mn_Length >= GEM_REQUEST_BYTES) {
            r->result = GEM_STOPPING;
            r->completed_count = r->reply_words = 0;
        }
        ReplyMsg(&r->message);
    }
    release_worker(s);
    /* Final publication and removal are indivisible, as for resident workers. */
    Forbid();
    s->state = GEM_RETIRED;
    s->worker = NULL;
    ReleaseTask(&s->owner_lease);
    ReleaseTask(&s->worker_lease);
    ReplyMsg(&stop->message);
    RemTask(NULL);
}

UWORD GemServiceStart(struct GemServer *s, const struct GemBackend *backend)
{
    BYTE bit;
    if (!GemAddressExtent(s, sizeof(*s)) || s->state != GEM_DOWN || !backend ||
        !backend->open || !backend->command || !backend->fence || !backend->close)
        return GEM_BAD_PACKET;
    bit = AllocSignal(-1);
    if (bit == -1)
        return GEM_NO_MEMORY;
    s->owner = FindTask(NULL);
    s->ready_mask = 1UL << bit;
    s->backend = backend;
    s->state = GEM_STARTING;
    s->startup_result = GEM_NO_MEMORY;
    s->stop_replies = CreateMsgPort();
    if (s->stop_replies)
        s->stop_packet = AllocMem(GEM_REQUEST_BYTES, MEMF_PUBLIC | MEMF_CLEAR);
    if (!s->stop_replies || !GemUpperExtent(s->stop_packet, GEM_REQUEST_BYTES)) {
        release_stop(s);
        s->state = GEM_RETIRED;
        FreeSignal(bit);
        s->ready_mask = 0;
        return GEM_NO_MEMORY;
    }
    Forbid();
    if (RetainTask(s->owner, &s->owner_lease)) {
        s->worker = CreateTask("GEM service", 0, (APTR)GemServiceWorker, 2560UL);
        if (s->worker && RetainTask(s->worker, &s->worker_lease)) {
            s->worker->tc_UserData = s;
        } else {
            if (s->worker)
                RemTask(s->worker);
            s->worker = NULL;
            ReleaseTask(&s->owner_lease);
        }
    }
    Permit();
    if (s->worker) {
        while (s->state == GEM_STARTING)
            Wait(s->ready_mask);
    } else {
        s->state = GEM_RETIRED;
    }
    FreeSignal(bit);
    s->ready_mask = 0;
    if (s->startup_result != GEM_OK)
        release_stop(s);
    return s->startup_result;
}
