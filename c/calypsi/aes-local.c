#include "aes-private.h"

/* Bound before clients start; separate from per-application C contexts. */
void EXEC_PTR *ExecAESLocalEntry;

/* The public binding has already admitted this Task's context. A miss leaves
 * the operation unapplied and the transport sequence available to RPC. */
UWORD ExecAESLocal(struct ExecAESContext *c, UWORD operation)
{
    UWORD handled;
    if (!ExecAESLocalEntry) return 0;
    c->request.operation=operation;
    c->request.client=c->identity;
    c->busy=1;
    handled=_AESLocalCall(&c->request);
    c->busy=0;
    return handled;
}
