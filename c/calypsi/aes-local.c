#include "aes-private.h"

/* Bound before clients start; separate from per-application C contexts. */
void EXEC_PTR *ExecAESLocalEntry;

/* The binding has admitted this Task. Native waits retain busy until their
 * caller or system continuation finishes; no descriptor is sent as a message. */
UWORD ExecAESLocal(struct ExecAESContext *c, UWORD operation)
{
    UWORD handled;
    if (!ExecAESLocalEntry) {
        c->request.status=AES_UNSUPPORTED;
        return 1;
    }
    c->request.operation=operation;
    c->request.client=c->identity;
    c->busy=1;
    handled=_AESLocalCall(&c->request);
    c->busy=0;
    return handled;
}
