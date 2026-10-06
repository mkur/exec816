#include <exec816/aes.h>
#include <proto/exec.h>
#include <gem.h>

/* This table belongs to the resident C image. No implicit C TLS or shared
 * GEM parameter block. Each live Task owns a separately allocated context. */
static struct ExecAESContext *contexts[AES_CONTEXTS];

BOOL ExecAESPointer(const void *pointer, ULONG bytes)
{
    ULONG address = (ULONG)pointer;
    return address != 0 && address <= 0xffffffUL &&
           bytes != 0 && bytes <= 0x1000000UL-address;
}

struct ExecAESContext *ExecAESContext(void)
{
    struct Task *owner = FindTask(NULL);
    struct ExecAESContext *result = NULL;
    UWORD i;
    /* Keep another Task from freeing a candidate during this lookup. Only
     * the current Task can subsequently detach the returned context. */
    Forbid();
    for (i = 0; i < AES_CONTEXTS; ++i)
        if (contexts[i] != NULL && contexts[i]->request.owner == owner) {
            result = contexts[i];
            break;
        }
    Permit();
    return result;
}

BOOL ExecAESAttach(struct MsgPort *service)
{
    struct ExecAESContext *context;
    UWORD i;
    if (!ExecAESPointer(service, sizeof(*service)))
        return FALSE;
    Forbid();
    context = ExecAESContext();
    if (context != NULL) {
        BOOL same = context->service == service;
        Permit();
        return same;
    }
    for (i = 0; i < AES_CONTEXTS && contexts[i] != NULL; ++i) {}
    if (i == AES_CONTEXTS) {
        Permit();
        return FALSE;
    }
    context = AllocMem(sizeof(*context), MEMF_PUBLIC | MEMF_CLEAR);
    if (context == NULL) {
        Permit();
        return FALSE;
    }
    context->replies = CreateMsgPort();
    if (context->replies == NULL) {
        FreeMem(context, sizeof(*context));
        Permit();
        return FALSE;
    }
    context->service = service;
    context->request.owner = FindTask(NULL);
    context->request.binding = (UBYTE *)context;
    context->request.message.mn_ReplyPort = context->replies;
    context->request.message.mn_Length = sizeof(context->request);
    context->request.version = AES_VERSION;
    context->request.bytes = sizeof(context->request);
    contexts[i] = context;
    Permit();
    return TRUE;
}

BOOL ExecAESDetach(void)
{
    struct ExecAESContext *context = ExecAESContext();
    UWORD i;
    if (context == NULL)
        return TRUE;
    if (context->busy) {
        context->diagnostic = AES_BUSY;
        return FALSE;
    }
    if (context->identity != 0 && !appl_exit())
        return FALSE;
    Forbid();
    for (i = 0; i < AES_CONTEXTS; ++i)
        if (contexts[i] == context)
            contexts[i] = NULL;
    DeleteMsgPort(context->replies);
    FreeMem(context, sizeof(*context));
    Permit();
    return TRUE;
}

UWORD ExecAESDiagnostic(void)
{
    struct ExecAESContext *context = ExecAESContext();
    return context != NULL ? context->diagnostic : AES_IDENTITY;
}

/* One caller, one packet, one outstanding call. A signal is only a hint: the
 * queue is checked first, including when the reply preceded PutMsg's return. */
static WORD submit(struct ExecAESContext *c, UWORD operation)
{
    struct AESRequest *r = &c->request;
    struct Message *reply;
    ULONG sequence;
    WORD failure = operation == AES_OP_INIT ? -1 : 0;
    if (c->busy) { c->diagnostic = AES_BUSY; return failure; }
    if (c->identity == 0 && operation != AES_OP_INIT) {
        c->diagnostic = AES_IDENTITY; return failure;
    }
    if (c->sequence == 0xffffffffUL ||
        (c->sequence == 0xfffffffeUL && operation != AES_OP_EXIT)) {
        c->diagnostic = AES_OVERFLOW; return failure;
    }
    sequence = c->sequence+1;
    r->operation = operation;
    r->status = AES_PENDING;
    r->client = c->identity;
    r->sequence = sequence;
    c->busy = 1;
    PutMsg(c->service, &r->message);
    while ((reply = GetMsg(c->replies)) == NULL) WaitPort(c->replies);
    /* This is a private port and binding. No borrowed pointers survive reply. */
    if (reply != &r->message || r->version != AES_VERSION ||
        r->bytes != sizeof(*r) || r->sequence != sequence ||
        r->operation != operation || r->owner != FindTask(NULL) ||
        r->binding != (UBYTE *)c || r->message.mn_ReplyPort != c->replies ||
        (operation != AES_OP_INIT && operation != AES_OP_EXIT &&
         r->client != c->identity)) {
        c->diagnostic = AES_MALFORMED;
        c->busy = 0;
        return failure;
    }
    c->diagnostic = r->status;
    if (c->identity != 0)
        c->sequence = sequence;
    if (r->status == AES_OK) {
        if (operation == AES_OP_INIT) {
            if (r->client == 0 || r->intout[0] <= 0) {
                c->diagnostic = AES_MALFORMED;
            } else {
                c->identity = r->client;
                c->gemId = r->intout[0];
                c->sequence = sequence;
            }
        } else if (operation == AES_OP_EXIT) {
            if (r->client != 0) c->diagnostic = AES_MALFORMED;
            else { c->identity = 0; c->sequence = 0; c->gemId = 0; }
        }
    }
    c->busy = 0;
    return c->diagnostic == AES_OK ? r->intout[0] : failure;
}

WORD appl_init(void)
{
    struct ExecAESContext *c = ExecAESContext();
    if (c == NULL) return -1;
    if (c->busy) { c->diagnostic = AES_BUSY; return -1; }
    if (c->identity != 0) { c->diagnostic = AES_OK; return c->gemId; }
    return submit(c, AES_OP_INIT);
}

WORD appl_exit(void)
{
    struct ExecAESContext *c = ExecAESContext();
    return c != NULL ? submit(c, AES_OP_EXIT) : 0;
}

WORD appl_write(WORD id, WORD length, const WORD *message)
{
    struct ExecAESContext *c = ExecAESContext();
    UWORD i;
    if (c == NULL) return 0;
    if (c->busy) { c->diagnostic = AES_BUSY; return 0; }
    if (length != 16 || !ExecAESPointer(message, 16)) {
        c->diagnostic = AES_MALFORMED; return 0;
    }
    c->request.intin[0] = id;
    c->request.intin[1] = length;
    for (i = 0; i < AES_MESSAGE_WORDS; ++i) c->request.words[i] = message[i];
    return submit(c, AES_OP_WRITE);
}

WORD evnt_mesag(WORD *message)
{
    struct ExecAESContext *c = ExecAESContext();
    UWORD i;
    WORD result;
    if (c == NULL) return 0;
    if (!ExecAESPointer(message, 16)) { c->diagnostic = AES_MALFORMED; return 0; }
    result = submit(c, AES_OP_MESAG);
    if (result)
        for (i = 0; i < AES_MESSAGE_WORDS; ++i) message[i] = c->request.words[i];
    return result;
}

WORD evnt_timer(UWORD lo, UWORD hi)
{
    struct ExecAESContext *c = ExecAESContext();
    if (c == NULL) return 0;
    if (c->busy) { c->diagnostic = AES_BUSY; return 0; }
    c->request.intin[0] = (WORD)lo;
    c->request.intin[1] = (WORD)hi;
    return submit(c, AES_OP_TIMER);
}

static WORD multi(struct ExecAESContext *c, WORD *message)
{
    UWORD i, flags = (UWORD)c->request.intin[0];
    WORD result;
    if (flags == 0 || (flags & ~(MU_MESAG | MU_TIMER))) {
        c->diagnostic = AES_UNSUPPORTED; return 0;
    }
    if ((flags & MU_MESAG) && !ExecAESPointer(message, 16)) {
        c->diagnostic = AES_MALFORMED; return 0;
    }
    result = submit(c, AES_OP_MULTI);
    if (result & MU_MESAG)
        for (i = 0; i < AES_MESSAGE_WORDS; ++i) message[i] = c->request.words[i];
    return result;
}

WORD evnt_multi(WORD flags, WORD bclk, WORD bmsk, WORD bst,
    WORD m1flags, WORD m1x, WORD m1y, WORD m1w, WORD m1h,
    WORD m2flags, WORD m2x, WORD m2y, WORD m2w, WORD m2h,
    WORD *msg, WORD tlo, WORD thi,
    WORD *mx, WORD *my, WORD *mb, WORD *ks, WORD *kr, WORD *br)
{
    struct ExecAESContext *c = ExecAESContext();
    WORD *in, result;
    if (c == NULL) return 0;
    if (c->busy) { c->diagnostic = AES_BUSY; return 0; }
    if (!ExecAESPointer(mx, 2) || !ExecAESPointer(my, 2) ||
        !ExecAESPointer(mb, 2) || !ExecAESPointer(ks, 2) ||
        !ExecAESPointer(kr, 2) || !ExecAESPointer(br, 2)) {
        c->diagnostic = AES_MALFORMED; return 0;
    }
    in = c->request.intin;
    in[0] = flags; in[1] = bclk; in[2] = bmsk; in[3] = bst;
    in[4] = m1flags; in[5] = m1x; in[6] = m1y; in[7] = m1w; in[8] = m1h;
    in[9] = m2flags; in[10] = m2x; in[11] = m2y; in[12] = m2w; in[13] = m2h;
    in[14] = tlo; in[15] = thi;
    result = multi(c, msg);
    *mx = *my = *mb = *ks = *kr = *br = 0;
    return result;
}

WORD evnt_multi_moblk(UWORD flags, WORD bclk, UWORD bmsk, UWORD bst,
    const MOBLK *m1, const MOBLK *m2, WORD *msg, UWORD tlo, UWORD thi,
    WORD *mx, WORD *my, WORD *mb, WORD *ks, WORD *kr, WORD *br)
{
    /* Rectangle values are ignored only when their event bits are absent.
     * Unsupported rectangle events are rejected as a whole by evnt_multi. */
    return evnt_multi((WORD)flags, bclk, (WORD)bmsk, (WORD)bst,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, msg, (WORD)tlo, (WORD)thi,
        mx, my, mb, ks, kr, br);
}

void EXEC_CALL aes_call(AESPB *pb)
{
    struct ExecAESContext *c = ExecAESContext();
    WORD result = 0;
    UWORD i, op, inputs = 0, addresses = 0, outputs = 1;
    if (c == NULL) return;
    c->diagnostic = AES_MALFORMED;
    if (!ExecAESPointer(pb, sizeof(*pb)) ||
        !ExecAESPointer(pb->control, 10) ||
        !ExecAESPointer(pb->global, 30) ||
        !ExecAESPointer(pb->int_out, 2)) return;
    op = pb->control[0];
    if (op == AES_OP_WRITE) { inputs = 2; addresses = 1; }
    if (op == AES_OP_MESAG) addresses = 1;
    if (op == AES_OP_TIMER) inputs = 2;
    if (op == AES_OP_MULTI) { inputs = 16; addresses = 1; outputs = 7; }
    if (op == AES_OP_INIT) result = -1;
    if (op != AES_OP_INIT && op != AES_OP_EXIT && op != AES_OP_WRITE &&
        op != AES_OP_MESAG && op != AES_OP_TIMER && op != AES_OP_MULTI) {
        c->diagnostic = AES_UNSUPPORTED; pb->int_out[0] = 0; return;
    }
    if (pb->control[1] != inputs || pb->control[2] != outputs ||
        pb->control[3] != addresses || pb->control[4] != 0 ||
        !ExecAESPointer(pb->int_out, outputs*2) ||
        (inputs && !ExecAESPointer(pb->int_in, inputs*2)) ||
        (addresses && !ExecAESPointer(pb->addr_in, addresses*4))) {
        pb->int_out[0] = result; return;
    }
    switch (op) {
    case AES_OP_INIT: result = appl_init(); break;
    case AES_OP_EXIT: result = appl_exit(); break;
    case AES_OP_WRITE:
        result = appl_write(pb->int_in[0], pb->int_in[1], (WORD *)(ULONG)pb->addr_in[0]); break;
    case AES_OP_MESAG: result = evnt_mesag((WORD *)(ULONG)pb->addr_in[0]); break;
    case AES_OP_TIMER:
        result = evnt_timer((UWORD)pb->int_in[0], (UWORD)pb->int_in[1]); break;
    case AES_OP_MULTI:
        if (c->busy) { c->diagnostic = AES_BUSY; break; }
        for (i = 0; i < 16; ++i) c->request.intin[i] = pb->int_in[i];
        result = multi(c, (WORD *)(ULONG)pb->addr_in[0]);
        for (i = 1; i < 7; ++i) pb->int_out[i] = 0;
        break;
    default:
        c->diagnostic = AES_UNSUPPORTED;
    }
    pb->int_out[0] = result;
    for (i = 0; i < AES_GLOBAL_WORDS; ++i) pb->global[i] = c->request.global[i];
}
