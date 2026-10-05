#include <exec816/aes.h>
#include <proto/exec.h>

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
    if (context->busy || context->request.client != 0) {
        context->diagnostic = AES_BUSY;
        return FALSE;
    }
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
