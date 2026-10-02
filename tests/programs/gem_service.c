/* G2 uses an explicit fixture backend. No GEM or display routine is linked. */
#include "gem-service.h"
#include <clib/alib_protos.h>
#include <string.h>

volatile UWORD variant, failures, first_failure, checks, finished;
volatile UWORD progress[2], active, saw_stop;
volatile UWORD peer_stop_result;
volatile ULONG checksum[2];
struct GemServer server;
struct GemClient client, other_client;
static struct Task *parent, *peer, *blockers[6];
static struct TaskLease peer_lease, copied_lease, extra_lease;
static volatile UWORD peer_done, blockers_done;
static UWORD opens, closes, calls, fences, backend_live;
static UWORD fail_open, fail_command, fail_fence;
static ULONG order_hash;
static void *held[32];
static ULONG held_size[32];
static UWORD held_count;

static void check(UWORD condition)
{
    ++checks;
    if (!condition) {
        if (!failures)
            first_failure = checks;
        ++failures;
    }
}

static void compute(UWORD who)
{
    ULONG a = 0x12345678UL + who, b = 0x87654321UL - who;
    UWORD i;
    for (i = 0; i < 30000; ++i) {
        a = ((a << 1) ^ (a >> 31)) ^ b;
        b += a ^ i;
        progress[who] = i + 1;
    }
    checksum[who] = a ^ b;
}

void Peer(void)
{
    compute(0);
    FindTask(NULL)->tc_UserData = &server;
    GemServiceWorker(); /* A duplicate entry must leave the live service alone. */
    peer_stop_result = GemServiceStop(&server);
    Wait(1);
    Forbid();
    peer_done = 1;
    Signal(parent, 1UL << 30);
    RemTask(NULL);
}

void Blocker(void)
{
    Wait(1);
    Forbid();
    ++blockers_done;
    Signal(parent, 1UL << 30);
    RemTask(NULL);
}

static UWORD backend_open(void *context, WORD *reply)
{
    UWORD i;
    check(context == &server && !backend_live);
    if (fail_open)
        return GEM_NO_MEMORY;
    backend_live = 1;
    ++opens;
    for (i = 0; i < 57; ++i)
        reply[i] = i + 100;
    return GEM_OK;
}

static UWORD backend_command(void *context, const struct GemCommand *command,
                             const WORD *points, const WORD *ints, WORD *reply)
{
    check(context == &server && backend_live);
    check(points == server.scratch->points && ints == server.scratch->ints);
    ++calls;
    active = 1;
    if (variant == 2) {
        UWORD i;
        Signal(parent, 1UL << 29);
        for (i = 0; i < 60000 && server.state == GEM_RUNNING; ++i)
            progress[1] = i + 1;
        saw_stop = server.state == GEM_STOPPING_STATE;
        check(saw_stop);
    } else if (!progress[1]) {
        compute(1);
    }
    active = 0;
    order_hash = order_hash * 31 + command->opcode;
    if (fail_command && calls == fail_command)
        return GEM_DEVICE_FAULT;
    if (command->opcode == 11)
        check(points[0] == 2 && points[1] == 3 && points[2] == 8 && points[3] == 9);
    if (command->opcode == 8 && command->int_words == 64)
        check(ints[0] == 255 && ints[63] == 255);
    if (command->opcode == 6 && command->point_pairs == 16)
        check(points[0] == 0 && points[31] == 31);
    *reply = command->int_words ? ints[0] : 0;
    return GEM_OK;
}

static UWORD backend_fence(void *context)
{
    check(context == &server && backend_live);
    ++fences;
    return fail_fence && fences == fail_fence ? GEM_DEVICE_FAULT : GEM_OK;
}

static UWORD backend_close(void *context)
{
    check(context == &server && backend_live);
    backend_live = 0;
    ++closes;
    return GEM_OK;
}

static const struct GemBackend backend = {
    backend_open, backend_command, backend_fence, backend_close, &server
};

static struct GemCommand *commands(void) { return (struct GemCommand *)(client.packet + 1); }

static void batch(void)
{
    struct GemCommand *c;
    WORD *values;
    check(GemPrepare(&client, GEM_OP_SUBMIT, 3, 48) == GEM_OK);
    c = commands();
    values = (WORD *)((UBYTE *)client.packet + GEM_REQUEST_BYTES + 36);
    values[0] = 5; values[1] = 7;
    values[2] = 2; values[3] = 3; values[4] = 8; values[5] = 9;
    c[0].opcode = 17; c[0].int_words = 1; c[0].ints_offset = GEM_REQUEST_BYTES + 36;
    c[1].opcode = 25; c[1].int_words = 1; c[1].ints_offset = GEM_REQUEST_BYTES + 38;
    c[2].opcode = 11; c[2].subopcode = 1; c[2].point_pairs = 2; c[2].points_offset = GEM_REQUEST_BYTES + 40;
}

static ULONG input_hash(void)
{
    UWORD i;
    ULONG h = 0;
    UBYTE *p = (UBYTE *)client.packet;
    for (i = 16; i < 34; ++i)
        h = h * 31 + p[i];
    h = h * 31 + client.packet->reserved;
    for (i = GEM_REQUEST_BYTES; i < client.packet->message.mn_Length; ++i)
        h = h * 31 + p[i];
    return h;
}

static UWORD exchange(void)
{
    check(GemSubmit(&client) == GEM_OK);
    return GemCollect(&client);
}

static void malformed(void)
{
    UWORD kind;
    for (kind = 0; kind < 23; ++kind) {
        UWORD expected = GEM_BAD_PACKET, before = calls;
        ULONG sequence = server.next_sequence, hash;
        struct GemCommand *c;
        batch();
        c = commands();
        switch (kind) {
        case 0: client.packet->version = 0; break;
        case 1: client.packet->flags = 1; break;
        case 2: client.packet->reserved = 1; break;
        case 3: --client.packet->total_bytes; break;
        case 4: client.packet->command_count = 0; break;
        case 5: client.packet->command_count = 17; break;
        case 6: client.packet->command_count = 0xffff; break;
        case 7: client.packet->total_bytes = client.packet->message.mn_Length = GEM_REQUEST_BYTES; break;
        case 8: c[0].ints_offset = 42; break;
        case 9: ++c[0].ints_offset; break;
        case 10: c[2].points_offset = client.packet->total_bytes - 2; break;
        case 11: c[0].points_offset = GEM_REQUEST_BYTES + 36; break;
        case 12: c[0].int_words = 0x8000; break;
        case 13: c[2].point_pairs = 0xffff; break;
        case 14: c[0].ints_offset = 0xffff; break;
        case 15: c[2].opcode = 99; expected = GEM_UNSUPPORTED; break;
        case 16: c[2].subopcode = 0; expected = GEM_UNSUPPORTED; break;
        case 17: c[0].opcode = 23; expected = GEM_UNSUPPORTED; break;
        case 18: c[0].opcode = 32; expected = GEM_UNSUPPORTED; break;
        case 19: *(WORD *)((UBYTE *)client.packet + c[0].ints_offset) = 16; expected = GEM_UNSUPPORTED; break;
        case 20: c[0].opcode = 1; expected = GEM_UNSUPPORTED; break;
        case 21: --client.packet->sequence; expected = GEM_BAD_SESSION; break;
        case 22: ++client.packet->session; expected = GEM_BAD_SESSION; break;
        }
        hash = input_hash();
        check(exchange() == expected);
        check(calls == before && server.next_sequence == sequence);
        check(client.packet->reply_words == 0 && client.packet->completed_count == 0);
        check(input_hash() == hash);
    }
}

static void raw_packets(void)
{
    struct MsgPort *replies = CreateMsgPort();
    struct GemRequest *r = AllocMem(GEM_REQUEST_BYTES, MEMF_PUBLIC | MEMF_CLEAR);
    ULONG session = server.session, sequence = server.next_sequence;
    UWORD i;
    check(replies != NULL && r != NULL);
    if (!replies || !r)
        return;
    r->message.mn_ReplyPort = replies;
    /* A valid Exec Message with a short service header gets only an Exec reply.
     * The receiver must not write past the advertised header. */
    r->message.mn_Length = sizeof(struct Message);
    r->result = 0x55aa;
    PutMsg(server.port, &r->message);
    check(WaitPort(replies) == &r->message && GetMsg(replies) == &r->message);
    check(r->result == 0x55aa);
    r->message.mn_Length = r->total_bytes = GEM_REQUEST_BYTES;
    r->version = GEM_VERSION;
    for (i = 0; i < 2; ++i) {
        r->operation = i ? GEM_OP_STOP : GEM_OP_CLOSE;
        r->session = i ? 0 : session;
        r->sequence = i ? 0 : sequence;
        PutMsg(server.port, &r->message);
        check(WaitPort(replies) == &r->message && GetMsg(replies) == &r->message);
        check(r->result == GEM_BAD_SESSION && !r->completed_count && !r->reply_words);
        check(server.state == GEM_RUNNING && server.session == session && server.next_sequence == sequence);
    }
    FreeMem(r, GEM_REQUEST_BYTES);
    DeleteMsgPort(replies);
}

static void limits(void)
{
    struct GemCommand *c;
    WORD glyphs[64], points[32], value = 1;
    UWORD i;
    check(GemPrepare(&client, GEM_OP_SUBMIT, 16, 2048) == GEM_OK);
    c = commands();
    *(WORD *)((UBYTE *)client.packet + GEM_REQUEST_BYTES + 192) = 5;
    for (i = 0; i < 16; ++i) {
        c[i].opcode = 22;
        c[i].int_words = 1;
        c[i].ints_offset = GEM_REQUEST_BYTES + 192; /* Shared read-only input. */
    }
    check(exchange() == GEM_OK && client.packet->completed_count == 16 && client.packet->reply_words == 16);
    for (i = 0; i < 16; ++i)
        check(client.packet->reply[i] == 5);
    for (i = 0; i < 64; ++i)
        glyphs[i] = 255;
    for (i = 0; i < 32; ++i)
        points[i] = i;
    check(GemCall(&client, 8, 0, 1, 64, points, glyphs) == GEM_OK);
    check(GemCall(&client, 6, 0, 16, 0, points, NULL) == GEM_OK);
    check(GemCall(&client, 23, 0, 0, 1, NULL, &value) == GEM_OK);
    check(GemCall(&client, 32, 0, 0, 1, NULL, &value) == GEM_OK);
    check(GemCall(&client, 129, 0, 2, 1, points, &value) == GEM_OK);
    check(GemCall(&client, 4, 0, 0, 0, NULL, NULL) == GEM_OK);
    check(GemCall(&client, 8, 0, 1, 2, points, (const WORD *)0xfffffeUL) == GEM_BAD_PACKET);
}

static void protocol(void)
{
    ULONG hash, generation;
    UWORD before;
    WORD letter = 256, xy[2] = {4, 5};
    check(GemOpen(&client) == GEM_OK);
    generation = client.session;
    check(generation == 1 && client.packet->reply_words == 57);
    check(client.packet->reply[0] == 100 && client.packet->reply[56] == 156);
    check(GemOpen(&client) == GEM_BUSY);
    check(GemClientInit(&other_client, &server) == GEM_BUSY);
    batch();
    hash = input_hash();
    check(GemSubmit(&client) == GEM_OK);
    check(GemSubmit(&client) == GEM_BUSY);
    check(GemPrepare(&client, GEM_OP_CLOSE, 0, 0) == GEM_BUSY);
    check(GemClientDispose(&client) == GEM_BUSY);
    check(GemCollect(&client) == GEM_OK);
    check(input_hash() == hash && client.packet->completed_count == 3);
    check(client.packet->reply_words == 2 && client.packet->reply[0] == 5 && client.packet->reply[1] == 7);
    check(order_hash == (17UL * 31 + 25) * 31 + 11);
    check(GemCollect(&client) == GEM_BAD_SESSION);
    malformed();
    raw_packets();
    limits();
    before = calls;
    check(GemCall(&client, 8, 0, 1, 1, xy, &letter) == GEM_UNSUPPORTED);
    check(GemStatus(&client) == GEM_UNSUPPORTED && calls == before);
    check(GemCall(&client, 8, 0, 1, 0, xy, NULL) == GEM_OK);
    check(GemClose(&client) == GEM_OK && !server.session);
    check(GemOpen(&client) == GEM_OK && client.session > generation);
    batch(); client.packet->session = generation;
    check(exchange() == GEM_BAD_SESSION);
    /* A command failure and a fence failure each report only a fenced prefix. */
    batch(); fail_command = calls + 2;
    check(exchange() == GEM_DEVICE_FAULT);
    check(client.packet->completed_count == 1 && client.packet->reply_words == 1 && !client.session);
    fail_command = 0;
    check(GemOpen(&client) == GEM_OK);
    batch(); fail_fence = fences + 2;
    check(exchange() == GEM_DEVICE_FAULT);
    check(client.packet->completed_count == 1 && client.packet->reply_words == 1 && !server.session);
    fail_fence = 0;
    generation = server.generation;
    fail_open = 1;
    check(GemOpen(&client) == GEM_NO_MEMORY && server.generation == generation && !backend_live);
    fail_open = 0;
    check(GemOpen(&client) == GEM_OK);
    /* Fixture-only boundary seeding; the service never wraps these counters. */
    server.next_sequence = client.next_sequence = 0xfffffffeUL;
    check(GemCall(&client, 3, 0, 0, 0, NULL, NULL) == GEM_OK);
    check(GemCall(&client, 3, 0, 0, 0, NULL, NULL) == GEM_EXHAUSTED);
    check(GemClose(&client) == GEM_OK);
    server.generation = 0xfffffffeUL;
    check(GemOpen(&client) == GEM_OK && client.session == 0xffffffffUL);
    check(GemClose(&client) == GEM_OK);
    check(GemOpen(&client) == GEM_EXHAUSTED);
}

static void exhaust(ULONG spare)
{
    void *reserve = spare ? AllocMem(spare, MEMF_PUBLIC) : NULL;
    ULONG bytes;
    while ((bytes = AvailMem(MEMF_LARGEST)) != 0 && held_count < 32) {
        held_size[held_count] = bytes;
        held[held_count] = AllocMem(bytes, MEMF_PUBLIC);
        check(held[held_count] != NULL);
        ++held_count;
    }
    check(AvailMem(0) == 0);
    if (reserve)
        FreeMem(reserve, spare);
}

static void restore_heap(void)
{
    while (held_count) {
        --held_count;
        FreeMem(held[held_count], held_size[held_count]);
    }
}

int main(void)
{
    ULONG available = AvailMem(0);
    UWORD status, i, count = 0;
    BYTE bits[16], bit;
    parent = FindTask(NULL);
    check(AllocSignal(29) == 29 && AllocSignal(30) == 30);
    Forbid();
    peer = CreateTask("G2 peer", 0, (APTR)Peer, 2560UL);
    check(peer != NULL && RetainTask(peer, &peer_lease));
    copied_lease = peer_lease;
    check(ReleaseTask(&copied_lease) == 0);
    check(RetainTask((struct Task *)0x1000000UL, &extra_lease) == 0);
    check(RetainTask(peer, (struct TaskLease *)0x1000000UL) == 0);
    check(ReleaseTask((struct TaskLease *)0x1000000UL) == 0);
    check(RetainTask(peer, &extra_lease) == 1);
    check(ReleaseTask(&extra_lease) == 1 && ReleaseTask(&extra_lease) == 0);
    Permit();
    check(!GemUpperExtent((void *)0x1000000UL, 156));
    check(!GemUpperExtent((void *)0xfffff0UL, 156));
    check(!GemUpperExtent((void *)0xbfffeUL, 156));
    check(!GemUpperExtent((void *)0xd0001UL, 156));
    check(GemUpperExtent((void *)0xbff64UL, 156));
    if (variant == 3) {
        Forbid();
        for (i = 0; i < 6; ++i) {
            blockers[i] = CreateTask("G2 blocker", 0, (APTR)Blocker, 1024UL);
            check(blockers[i] != NULL);
        }
        Permit();
    }
    if (variant == 4)
        while ((bit = AllocSignal(-1)) != -1)
            bits[count++] = bit;
    if (variant == 5 || variant == 6)
        exhaust(variant == 6 ? 224 : 192);
    if (variant == 9 || variant == 10)
        exhaust(variant == 10 ? 32 : 0);
    status = GemServiceStart(&server, &backend);
    if ((variant >= 3 && variant <= 6) || variant == 9 || variant == 10) {
        check(status == GEM_NO_MEMORY && !server.worker && !server.port && !server.scratch);
        check(!server.owner_lease.task && !server.worker_lease.task);
        check(!server.stop_packet && !server.stop_replies);
        if (variant == 4)
            while (count)
                FreeSignal(bits[--count]);
        restore_heap();
        if (variant == 3) {
            for (i = 0; i < 6; ++i)
                Signal(blockers[i], 1);
            while (blockers_done != 6)
                Wait(1UL << 30);
        }
        goto done;
    }
    check(status == GEM_OK);
    if (status != GEM_OK)
        goto done;
    if (variant == 7 || variant == 8) {
        exhaust(variant == 8 ? 32 : 0);
        check(GemClientInit(&client, &server) == GEM_NO_MEMORY);
        check(!client.packet && !client.replies && !client.owner_lease.task && !server.client);
        restore_heap();
    }
    check(GemClientInit(&client, &server) == GEM_OK);
    if (variant == 11) { RemTask(server.worker); return 1; }
    if (variant == 12) { RemTask(NULL); return 1; }
    if (variant == 0)
        protocol();
    else if (variant == 1 || variant == 2) {
        check(GemOpen(&client) == GEM_OK);
        batch();
        if (variant == 1)
            Forbid();
        check(GemSubmit(&client) == GEM_OK);
        if (variant == 2) {
            Wait(1UL << 29);
            check(active);
        }
        check(GemServiceStop(&server) == GEM_OK);
        if (variant == 1)
            Permit();
        check(GemClientDispose(&client) == GEM_BUSY);
        check(GemCollect(&client) == GEM_OK);
        check(client.packet->completed_count == 3 && client.packet->reply_words == 2);
        goto dispose;
    } else {
        check(GemOpen(&client) == GEM_OK);
    }
    if (variant == 13)
        exhaust(0);
    check(GemServiceStop(&server) == GEM_OK);
    restore_heap();
dispose:
    check(server.state == GEM_RETIRED && !server.worker && !server.port && !backend_live);
    check(!server.owner_lease.task && !server.worker_lease.task);
    check(GemPrepare(&client, GEM_OP_CLOSE, 0, 0) == GEM_OK);
    check(GemSubmit(&client) == GEM_STOPPING);
    check(GemClientDispose(&client) == GEM_OK);
    check(opens == closes);
done:
    Forbid();
    check(ReleaseTask(&peer_lease) == 1);
    Signal(peer, 1);
    Permit();
    while (!peer_done)
        Wait(1UL << 30);
    check(peer_stop_result == GEM_BAD_SESSION);
    FreeSignal(29);
    FreeSignal(30);
    check(AvailMem(0) == available);
    finished = 1;
    return failures != 0;
}
