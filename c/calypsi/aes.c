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
    if (c->identity != 0 && r->status != AES_IDENTITY &&
        r->status != AES_BUSY && r->status != AES_OVERFLOW)
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
    if (c->identity != 0) { c->diagnostic = AES_OK; return c->gemId; }
    return submit(c, AES_OP_INIT);
}

WORD appl_exit(void)
{
    struct ExecAESContext *c = ExecAESContext();
    return c != NULL ? submit(c, AES_OP_EXIT) : 0;
}

void EXEC_CALL aes_call(AESPB *pb)
{
    struct ExecAESContext *c = ExecAESContext();
    WORD result = 0;
    UWORD i, op;
    if (c == NULL) return;
    c->diagnostic = AES_MALFORMED;
    if (!ExecAESPointer(pb, sizeof(*pb)) ||
        !ExecAESPointer(pb->control, 10) ||
        !ExecAESPointer(pb->global, 30) ||
        !ExecAESPointer(pb->int_out, 2)) return;
    op = pb->control[0];
    if (op == AES_OP_INIT) result = -1;
    if ((op == AES_OP_INIT || op == AES_OP_EXIT) &&
        pb->control[1] == 0 && pb->control[2] == 1 &&
        pb->control[3] == 0 && pb->control[4] == 0)
        result = op == AES_OP_INIT ? appl_init() : appl_exit();
    else if (op != AES_OP_INIT && op != AES_OP_EXIT)
        c->diagnostic = AES_UNSUPPORTED;
    pb->int_out[0] = result;
    for (i = 0; i < AES_GLOBAL_WORDS; ++i) pb->global[i] = c->request.global[i];
}
