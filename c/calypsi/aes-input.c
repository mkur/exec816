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
    else {
        input->selectedWindow = input->windowEpoch;
        input->interest = flags & (AES_INPUT_KEY | AES_INPUT_BUTTON);
    }
    Permit();
    return status;
}

/* Caller holds Forbid. These are lifetime/epoch checks, not repeated admission
 * validation. They also cover loss or close during alarm retirement. */
UWORD ExecAESInputState(struct ExecAESContext *c, UWORD flags)
{
    struct AESInputInbox *in = c->endpoint->input;
    if (!flags) return AES_OK;
    if (c->endpoint->state != AES_ENDPOINT_ACCEPTING ||
        !in->selectedWindow || in->windowEpoch != in->selectedWindow)
        return AES_IDENTITY;
    if (in->exhausted & flags) return AES_OVERFLOW;
    if (in->loss & flags) return AES_INPUT_LOST;
    return AES_OK;
}

static BOOL matches(struct ExecAESContext *c, UWORD buttons)
{
    return (((buttons & 1) == (UWORD)c->intin[3]) !=
            ((c->intin[1] & 0x100) != 0));
}

/* Freeze only a bounded selection, without moving consumer heads. Each copy
 * has its own short guard; the at-most-sixteen predicate scan runs outside it.
 * Producer records are immutable until this caller retires their positions. */
UWORD ExecAESInputSelect(struct ExecAESContext *c, UWORD flags)
{
    struct AESInputInbox *in = c->endpoint->input;
    UWORD ready = 0;
    UBYTE cursor, tail;
    if (!flags) return 0;
    Forbid();
    c->diagnostic = ExecAESInputState(c, flags);
    if (c->diagnostic != AES_OK) { Permit(); return 0; }
    in->selectionFlags = 0;
    in->keyTailSeen = in->keyTail;
    in->buttonTailSeen = in->buttonTail;
    in->selectedKey.epoch = in->keyEpoch;
    in->selectedButton.epoch = in->buttonEpoch;
    in->nextKey = in->keyHead;
    in->nextButton = in->buttonHead;
    if ((flags & AES_INPUT_KEY) && in->keyHead != in->keyTailSeen) {
        in->selectedKey = in->keys[in->keyHead & (AES_INPUT_SLOTS-1)];
        ++in->nextKey;
        ready |= AES_MU_KEYBD;
    }
    cursor = in->buttonHead;
    tail = in->buttonTailSeen;
    Permit();
    if (!(flags & AES_INPUT_BUTTON)) return ready;
    while (cursor != tail) {
        Forbid();
        in->selectedButton = in->buttons[cursor & (AES_INPUT_SLOTS-1)];
        Permit();
        ++cursor;
        if (matches(c, in->selectedButton.buttons)) {
            in->nextButton = cursor;
            return ready | AES_MU_BUTTON;
        }
    }
    Forbid();
    if (in->eligible && matches(c, in->latest.buttons)) {
        in->selectedButton = in->latest;
        in->selectedButton.epoch = in->buttonEpoch;
        in->nextButton = tail;
        in->selectionFlags = 1;
        ready |= AES_MU_BUTTON;
    }
    Permit();
    return ready;
}

/* Held by the event decision. New arrivals before freezing require another
 * selection; arrivals after freezing belong to the following call. */
BOOL ExecAESInputStable(struct ExecAESContext *c, UWORD flags)
{
    struct AESInputInbox *in = c->endpoint->input;
    return (!(flags & AES_INPUT_KEY) || in->keyTail == in->keyTailSeen) &&
           (!(flags & AES_INPUT_BUTTON) || in->buttonTail == in->buttonTailSeen);
}

/* Reconcile level eligibility at the actual frozen decision. A queued edge
 * is historical and keeps its recipient; an earlier level hint may have
 * changed with focus/locks while the timer clock was being read. Guard held. */
UWORD ExecAESInputLevel(struct ExecAESContext *c, UWORD ready)
{
    struct AESInputInbox *in = c->endpoint->input;
    if (!(ready & AES_MU_BUTTON) || in->selectionFlags) {
        ready &= ~AES_MU_BUTTON;
        if (in->eligible && matches(c, in->latest.buttons)) {
            in->selectedButton = in->latest;
            in->selectedButton.epoch = in->buttonEpoch;
            in->nextButton = in->buttonTailSeen;
            in->selectionFlags = 1;
            ready |= AES_MU_BUTTON;
        }
    }
    return ready;
}

UWORD ExecAESInputCommitState(struct ExecAESContext *c, UWORD flags)
{
    struct AESInputInbox *in = c->endpoint->input;
    UWORD status = ExecAESInputState(c, flags);
    if (status != AES_OK) return status;
    if (((flags & AES_INPUT_KEY) && in->selectedKey.epoch != in->keyEpoch) ||
        ((flags & AES_INPUT_BUTTON) && in->selectedButton.epoch != in->buttonEpoch))
        return AES_INPUT_LOST;
    return AES_OK;
}

/* The caller holds the decision guard. Result scratch is context-owned upper
 * memory and survives cancellation waits without rereading later pointer state. */
void ExecAESInputResult(struct ExecAESContext *c, UWORD ready)
{
    struct AESInputInbox *in = c->endpoint->input;
    struct AESInputRecord *sample = &in->latest;
    if (ready & AES_MU_KEYBD) sample = &in->selectedKey;
    if (ready & AES_MU_BUTTON) sample = &in->selectedButton;
    c->intout[1] = sample->x;
    c->intout[2] = sample->y;
    c->intout[3] = sample->buttons;
    c->intout[4] = sample->qualifiers;
    if (ready & AES_MU_KEYBD) {
        c->intout[4] |= in->selectedKey.qualifiers;
        c->intout[5] = in->selectedKey.key;
    }
    c->intout[6] = (ready & AES_MU_BUTTON) != 0;
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
    if (status == AES_INPUT_LOST && (lost & AES_INPUT_BUTTON)) {
        /* Recovery can expose an already observed released baseline. Ask the
         * existing presenter to refresh eligibility once, without polling. */
        Forbid();
        c->directory->changed = 1;
        Signal(c->directory->owner, c->directory->mask);
        Permit();
    }
    return status;
}
