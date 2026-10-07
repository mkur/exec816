#include "aes-private.h"
#include <proto/exec.h>

/* Private caller helpers: context admission belongs to the public event call.
 * Interest precedes its final queue inspection; no helper clears a signal. */
UWORD ExecAESInputArm(struct ExecAESContext *c, UWORD flags)
{
    struct AESInputInbox *input = c->endpoint->input;
    UWORD status = AES_OK;
    Forbid();
    if (input->windowEpoch == 0) status = AES_IDENTITY;
    else input->interest = flags & (AES_INPUT_KEY | AES_INPUT_BUTTON);
    Permit();
    return status;
}

void ExecAESInputDisarm(struct ExecAESContext *c)
{
    Forbid();
    c->endpoint->input->interest = 0;
    Permit();
}

/* Call only after retiring an outstanding alarm/frozen selection. Producers
 * stopped admitting the lost source; advancing its head acknowledges that
 * boundary without changing unrelated input or either message queue. */
UWORD ExecAESInputRecover(struct ExecAESContext *c, UWORD flags)
{
    struct AESInputInbox *input = c->endpoint->input;
    UWORD lost, status = AES_OK;
    Forbid();
    lost = input->loss & flags;
    if (!input->windowEpoch) status = AES_IDENTITY;
    else if (input->exhausted & flags) status = AES_OVERFLOW;
    else if (lost) {
        if (lost & AES_INPUT_KEY) input->keyHead = input->keyTail;
        if (lost & AES_INPUT_BUTTON) input->buttonHead = input->buttonTail;
        input->loss &= ~lost;
        status = AES_INPUT_LOST;
    }
    Permit();
    return status;
}
