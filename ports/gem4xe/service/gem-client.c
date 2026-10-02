#include "gem-service.h"
#include <string.h>

static UWORD result(struct GemClient *c, UWORD status)
{
    c->status = status;
    return status;
}

UWORD GemStatus(const struct GemClient *c) { return c->status; }

UWORD GemClientInit(struct GemClient *c, struct GemServer *s)
{
    if (!GemAddressExtent(c, sizeof(*c)) || c->server || FindTask(NULL) != s->owner)
        return GEM_BAD_PACKET;
    if (s->state != GEM_RUNNING)
        return result(c, GEM_STOPPING);
    if (s->client)
        return result(c, GEM_BUSY);
    c->replies = CreateMsgPort();
    if (!c->replies)
        return result(c, GEM_NO_MEMORY);
    c->packet = AllocMem(GEM_LIMIT_PACKET_BYTES, MEMF_PUBLIC | MEMF_CLEAR);
    if (!GemUpperExtent(c->packet, GEM_LIMIT_PACKET_BYTES) ||
        !RetainTask(s->owner, &c->owner_lease)) {
        if (c->packet)
            FreeMem(c->packet, GEM_LIMIT_PACKET_BYTES);
        DeleteMsgPort(c->replies);
        c->packet = NULL;
        c->replies = NULL;
        return result(c, GEM_NO_MEMORY);
    }
    c->server = s;
    c->next_sequence = 1;
    s->client = c;
    s->client_reply = c->replies;
    return result(c, GEM_OK);
}

UWORD GemClientDispose(struct GemClient *c)
{
    struct GemServer *s = c->server;
    if (!s || FindTask(NULL) != s->owner || s->client != c)
        return result(c, GEM_BAD_SESSION);
    if (c->pending || (s->state != GEM_RETIRED && s->session))
        return result(c, GEM_BUSY);
    s->client = NULL;
    s->client_reply = NULL;
    FreeMem(c->packet, GEM_LIMIT_PACKET_BYTES);
    DeleteMsgPort(c->replies);
    ReleaseTask(&c->owner_lease);
    memset(c, 0, sizeof(*c));
    return GEM_OK;
}

UWORD GemPrepare(struct GemClient *c, UWORD operation, UWORD commands, UWORD payload_bytes)
{
    struct GemRequest *r = c->packet;
    if (!c->server || FindTask(NULL) != c->server->owner || c->server->client != c)
        return result(c, GEM_BAD_SESSION);
    if (c->pending)
        return result(c, GEM_BUSY);
    if (commands > GEM_LIMIT_COMMANDS || payload_bytes > GEM_LIMIT_PAYLOAD_BYTES ||
        payload_bytes < (ULONG)commands * GEM_COMMAND_BYTES)
        return result(c, GEM_BAD_PACKET);
    memset(r, 0, GEM_LIMIT_PACKET_BYTES);
    r->message.mn_ReplyPort = c->replies;
    r->message.mn_Length = GEM_REQUEST_BYTES + payload_bytes;
    r->version = GEM_VERSION;
    r->total_bytes = r->message.mn_Length;
    r->operation = operation;
    r->session = operation == GEM_OP_OPEN ? 0 : c->session;
    r->sequence = operation == GEM_OP_OPEN ? 1 : c->next_sequence;
    r->command_count = commands;
    return result(c, GEM_OK);
}

UWORD GemPrepareCursor(struct GemClient *c, WORD x, WORD y, UWORD visible)
{
    UWORD status;
    struct GemCursor *cursor;
    if (x < 0 || x > 639 || y < 0 || y > 239 || visible > 1)
        return result(c, GEM_BAD_PACKET);
    status = GemPrepare(c, GEM_OP_CURSOR, 0, GEM_CURSOR_BYTES);
    if (status != GEM_OK) return status;
    cursor = (struct GemCursor *)(c->packet + 1);
    cursor->x = x;
    cursor->y = y;
    cursor->visible = visible;
    return GEM_OK;
}

UWORD GemSubmit(struct GemClient *c)
{
    struct GemServer *s = c->server;
    struct GemRequest *r = c->packet;
    UWORD status = GEM_OK;
    if (!s || FindTask(NULL) != s->owner || s->client != c)
        return result(c, GEM_BAD_SESSION);
    Forbid();
    if (c->pending || s->inflight)
        status = GEM_BUSY;
    else if (s->state != GEM_RUNNING)
        status = GEM_STOPPING;
    else if (!GemUpperExtent(r, GEM_LIMIT_PACKET_BYTES) ||
             r->message.mn_Length < GEM_REQUEST_BYTES || r->message.mn_Length > GEM_LIMIT_PACKET_BYTES ||
             r->message.mn_ReplyPort != c->replies)
        status = GEM_BAD_PACKET;
    else {
        c->pending = s->inflight = r;
        PutMsg(s->port, &r->message);
    }
    Permit();
    return result(c, status);
}

UWORD GemTryCollect(struct GemClient *c, UWORD *ready)
{
    struct GemRequest *r = c->pending;
    UWORD status;
    if (!ready) return result(c, GEM_BAD_PACKET);
    *ready = 0;
    if (!c->server || FindTask(NULL) != c->server->owner || c->server->client != c || !r)
        return result(c, GEM_BAD_SESSION);
    /* The private reply port contains only this exact request. Do not consume
     * an unexpected message, or release any storage whose ownership is unclear. */
    Forbid();
    if (IsListEmpty(&c->replies->mp_MsgList)) {
        Permit();
        return GEM_OK;
    }
    if (c->replies->mp_MsgList.lh_Head != &r->message.mn_Node) {
        Permit();
        return result(c, GEM_BAD_PACKET);
    }
    if (GetMsg(c->replies) != &r->message) {
        Permit();
        return result(c, GEM_BAD_PACKET);
    }
    status = r->result;
    c->pending = NULL;
    c->server->inflight = NULL;
    if (status == GEM_OK) {
        if (r->operation == GEM_OP_OPEN) {
            c->session = r->session;
            c->next_sequence = 2;
        } else if (r->operation == GEM_OP_CLOSE) {
            c->session = 0;
            c->next_sequence = 1;
        } else {
            ++c->next_sequence;
        }
    } else if (status == GEM_DEVICE_FAULT) {
        c->session = 0;
        c->next_sequence = 1;
    }
    *ready = 1;
    Permit();
    return result(c, status);
}

UWORD GemCollect(struct GemClient *c)
{
    UWORD ready, status = GemTryCollect(c, &ready);
    if (status != GEM_OK || ready) return status;
    WaitPort(c->replies);
    return GemTryCollect(c, &ready);
}

UWORD GemCall(struct GemClient *c, UWORD opcode, UWORD subopcode,
              UWORD pairs, UWORD words, const WORD *points, const WORD *ints)
{
    struct GemCommand *command;
    UWORD bytes, offset, status;
    if (pairs > GEM_MAX_POINT_PAIRS || words > GEM_MAX_INT_WORDS ||
        (pairs && !points) || (words && !ints) ||
        (ULONG)points > 0xffffffUL || (ULONG)ints > 0xffffffUL ||
        (pairs && (ULONG)points > 0x1000000UL - (ULONG)pairs * 4) ||
        (words && (ULONG)ints > 0x1000000UL - (ULONG)words * 2))
        return result(c, GEM_BAD_PACKET);
    bytes = pairs * 4 + words * 2;
    status = GemPrepare(c, opcode == 1 ? GEM_OP_OPEN : GEM_OP_SUBMIT, 1, GEM_COMMAND_BYTES + bytes);
    if (status != GEM_OK)
        return status;
    command = (struct GemCommand *)(c->packet + 1);
    command->opcode = opcode;
    command->subopcode = subopcode;
    command->point_pairs = pairs;
    command->int_words = words;
    offset = GEM_REQUEST_BYTES + GEM_COMMAND_BYTES;
    if (pairs) {
        command->points_offset = offset;
        memcpy((UBYTE *)c->packet + offset, points, pairs * 4);
        offset += pairs * 4;
    }
    if (words) {
        command->ints_offset = offset;
        memcpy((UBYTE *)c->packet + offset, ints, words * 2);
    }
    status = GemSubmit(c);
    return status == GEM_OK ? GemCollect(c) : status;
}

UWORD GemOpen(struct GemClient *c)
{
    static const WORD work[] = {1,1,1,1,1,1,1,1,1,1,2};
    return GemCall(c, 1, 0, 0, 11, NULL, work);
}

UWORD GemClose(struct GemClient *c)
{
    UWORD status = GemPrepare(c, GEM_OP_CLOSE, 0, 0);
    if (status == GEM_OK)
        status = GemSubmit(c);
    return status == GEM_OK ? GemCollect(c) : status;
}

UWORD GemServiceStop(struct GemServer *s)
{
    struct MsgPort *replies;
    struct GemRequest *r;
    UWORD status;
    if (FindTask(NULL) != s->owner)
        return GEM_BAD_SESSION;
    if (s->state != GEM_RUNNING)
        return GEM_STOPPING;
    replies = s->stop_replies;
    r = s->stop_packet;
    if (!replies || !GemUpperExtent(r, GEM_REQUEST_BYTES))
        return GEM_BAD_PACKET;
    r->message.mn_ReplyPort = replies;
    r->message.mn_Length = r->total_bytes = GEM_REQUEST_BYTES;
    r->version = GEM_VERSION;
    r->operation = GEM_OP_STOP;
    Forbid();
    s->state = GEM_STOPPING_STATE;
    s->stop_packet = r;
    PutMsg(s->port, &r->message);
    Permit();
    if (WaitPort(replies) != &r->message || GetMsg(replies) != &r->message)
        return GEM_BAD_PACKET; /* Retain storage on an impossible identity failure. */
    status = r->result;
    FreeMem(r, GEM_REQUEST_BYTES);
    DeleteMsgPort(replies);
    s->stop_packet = NULL;
    s->stop_replies = NULL;
    return status;
}
