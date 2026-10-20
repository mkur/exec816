#include "aes-private.h"
#include <proto/exec.h>
#include <string.h>
#include <stddef.h>

/* Called exactly once at a public direct-call boundary. Helpers use the
 * admitted context instead of looking it up or entering it recursively. */
BOOL ExecAESEnter(struct ExecAESContext *c)
{
    if (c->busy) { c->diagnostic = AES_BUSY; return FALSE; }
    if (c->identity == 0) { c->diagnostic = AES_IDENTITY; return FALSE; }
    /* Registration pins the endpoint until this Task's appl_exit. Admission
     * needs only caller-local state; event publication and snapshots retain
     * their own synchronization below. */
    c->busy = 1;
    c->diagnostic = AES_OK;
    return TRUE;
}

/* Same checked rational conversion as TIMER.Deadline. Every intermediate
 * fits in 32 bits, including the full unsigned GEM millisecond interval. */
BOOL ExecAESTimerDeadline(struct TimerClockRequest *clock, ULONG milliseconds)
{
    ULONG whole, fraction, delta, low, high = clock->ticks_hi;
    if (clock->ticks_per_second == 50) {
        whole = milliseconds / 20;
        fraction = milliseconds - whole * 20;
        delta = whole + 1 + (fraction != 0);
    } else if (clock->ticks_per_second == 60) {
        whole = milliseconds / 1000;
        fraction = milliseconds - whole * 1000;
        delta = whole * 60 + (fraction * 3 + 49) / 50 + 1;
    } else return FALSE;
    low = clock->ticks_lo + delta;
    if (low < clock->ticks_lo) {
        if (high == 0xffffffffUL) return FALSE;
        ++high;
    }
    clock->ticks_hi = high;
    clock->ticks_lo = low;
    return TRUE;
}

/* Collect exactly our alarm. Cancellation racing expiry still owns one
 * terminal reply. A mismatched private reply leaves the binding unretired. */
BOOL ExecAESTimerCollect(struct ExecAESContext *c, BOOL cancel)
{
    struct ExecAESTimer *t = &c->timer;
    struct Message *message;
    if (t->state == AES_ALARM_IDLE) return TRUE;
    if (cancel) {
        t->state = AES_ALARM_RETIRING;
        if (CheckIO(&t->alarm->tc_Request) == NULL)
            AbortIO(&t->alarm->tc_Request);
    }
    while ((message = GetMsg(t->port)) == NULL)
        Wait(1UL << t->port->mp_SigBit);
    if (message != &t->alarm->tc_Request.io_Message) {
        t->error = AES_TIMER_ERROR;
        return FALSE;
    }
    if (t->alarm->tc_Request.io_Error != 0 &&
        !(t->state == AES_ALARM_RETIRING &&
          t->alarm->tc_Request.io_Error == IOERR_ABORTED))
        t->error = AES_TIMER_ERROR;
    t->state = AES_ALARM_IDLE;
    return TRUE;
}

BOOL ExecAESTimerClose(struct ExecAESContext *c)
{
    struct ExecAESTimer *t = &c->timer;
    if (!ExecAESTimerCollect(c, TRUE)) return FALSE;
    if (t->alarm != NULL) {
        t->alarm->tc_Request.io_Device = NULL;
        t->alarm->tc_Request.io_Unit = NULL;
        DeleteIORequest(&t->alarm->tc_Request);
        t->alarm = NULL;
    }
    if (t->query != NULL) {
        if (t->opened) CloseDevice(&t->query->tc_Request);
        t->opened = 0;
        DeleteIORequest(&t->query->tc_Request);
        t->query = NULL;
    }
    if (t->port != NULL) { DeleteMsgPort(t->port); t->port = NULL; }
    return TRUE;
}

BOOL ExecAESTimerRead(struct ExecAESContext *c)
{
    struct ExecAESTimer *t = &c->timer;
    if (t->error) return FALSE;
    if (!t->opened) {
        t->port = CreateMsgPort();
        if (t->port == NULL) goto failure;
        t->query = (struct TimerClockRequest *)CreateIORequest(t->port, sizeof(*t->query));
        t->alarm = (struct TimerClockRequest *)CreateIORequest(t->port, sizeof(*t->alarm));
        if (t->query == NULL || t->alarm == NULL) goto failure;
        if (OpenDevice("timer.device", UNIT_VBLANK, &t->query->tc_Request, 0)) goto failure;
        t->opened = 1;
        t->alarm->tc_Request.io_Device = t->query->tc_Request.io_Device;
        t->alarm->tc_Request.io_Unit = t->query->tc_Request.io_Unit;
    }
    t->query->tc_Request.io_Command = TD_READCLOCK;
    if (DoIO(&t->query->tc_Request) ||
        (t->query->ticks_per_second != 50 && t->query->ticks_per_second != 60))
        goto failure;
    return TRUE;
failure:
    t->error = AES_TIMER_ERROR;
    /* Read is called only with an idle alarm or by its owning wait. Close
     * must retire a live alarm before releasing any of the original open. */
    ExecAESTimerClose(c);
    return FALSE;
}

void ExecAESTimerSend(struct ExecAESContext *c, ULONG high, ULONG low)
{
    struct ExecAESTimer *t = &c->timer;
    t->alarm->tc_Request.io_Command = TD_WAITUNTIL;
    t->alarm->ticks_hi = high;
    t->alarm->ticks_lo = low;
    t->state = AES_ALARM_OUTSTANDING;
    SendIO(&t->alarm->tc_Request);
}

WORD ExecAESTimerWait(struct ExecAESContext *c, ULONG milliseconds)
{
    UWORD status = AES_OK;
    if (!ExecAESEnter(c)) return 0;
    if (!ExecAESTimerRead(c)) status = AES_TIMER_ERROR;
    else if (!ExecAESTimerDeadline(c->timer.query, milliseconds)) status = AES_OVERFLOW;
    else {
        ExecAESTimerSend(c, c->timer.query->ticks_hi, c->timer.query->ticks_lo);
        if (!ExecAESTimerCollect(c, FALSE) || c->timer.error) status = AES_TIMER_ERROR;
    }
    c->diagnostic = status;
    c->busy = 0;
    return status == AES_OK;
}

/* Only this Task removes messages from its receive port. A nonempty hint
 * remains true until GetMsg below; concurrent publishers can only add work.
 * Empty is not a reason to clear a signal before Wait. */
static BOOL port_ready(struct MsgPort *port)
{
    return (struct Node *)port->mp_MsgList.lh_Head !=
           (struct Node *)&port->mp_MsgList.lh_Tail;
}

static WORD events(struct ExecAESContext *c, UWORD flags, ULONG milliseconds,
                   WORD *message, BOOL blocking,ULONG externalMask,ULONG *received)
{
    ULONG high = 0, low = 0, mask = 0,seen = 0,fresh,privateMask;
    UWORD ready = 0, status = AES_OK, inputFlags, i;
    BOOL submitted = FALSE, armed = FALSE, timerReady = FALSE;
    struct AESDelivery *record = NULL;
    struct AESInputInbox *input;
    if (!ExecAESEnter(c)) return 0;
    for (i = 0; i < AES_INTOUT_WORDS; ++i) c->intout[i] = 0;
    inputFlags = flags & (AES_MU_KEYBD | AES_MU_BUTTON | AES_MU_M1);
    input = c->endpoint->input;
    if ((!flags && !externalMask) || (flags & ~(AES_MU_KEYBD | AES_MU_BUTTON | AES_MU_M1 | AES_MU_MESAG | AES_MU_TIMER))) {
        status = AES_UNSUPPORTED;
        goto done;
    }
    if ((flags & AES_MU_BUTTON) &&
        ((c->intin[1] != 1 && c->intin[1] != 2 && c->intin[1] != 0x101) ||
         c->intin[2] != 1 || (c->intin[3] != 0 && c->intin[3] != 1))) {
        status = AES_UNSUPPORTED;
        goto done;
    }
    if (flags & AES_MU_MESAG) {
        if (!ExecAESPointer(message, 16)) { status = AES_MALFORMED; goto done; }
    }
    if ((flags & AES_MU_M1) && (c->intin[4] < 0 || c->intin[4] > 1 ||
        c->intin[7] <= 0 || c->intin[8] <= 0)) {
        status = AES_MALFORMED;
        goto done;
    }
    if (inputFlags) {
        status = ExecAESInputArm(c, inputFlags);
        if (status != AES_OK) goto done;
        armed = TRUE;
    }
    if (inputFlags || (flags & AES_MU_MESAG))
        mask = 1UL << c->receiving->mp_SigBit;
    if (flags & AES_MU_TIMER) {
        if (!ExecAESTimerRead(c)) { status = AES_TIMER_ERROR; goto done; }
        if (milliseconds && !ExecAESTimerDeadline(c->timer.query, milliseconds)) {
            status = AES_OVERFLOW;
            goto done;
        }
        high = c->timer.query->ticks_hi;
        low = c->timer.query->ticks_lo;
        mask |= 1UL << c->timer.port->mp_SigBit;
        timerReady = milliseconds == 0;
    }
    /* These signals belong to the registered AES binding, including retained
     * timer resources from an earlier call. External masks are caller-owned. */
    privateMask=(1UL<<c->receiving->mp_SigBit)|(1UL<<c->replies->mp_SigBit);
    if (c->timer.port) privateMask|=1UL<<c->timer.port->mp_SigBit;
    if (externalMask&privateMask) { status=AES_MALFORMED;goto done; }
    mask|=externalMask;
decide:
    for (;;) {
        if (externalMask) seen|=SetSignal(0,externalMask)&externalMask;
        ready = ExecAESInputSelect(c, inputFlags);
        if (c->diagnostic != AES_OK) { status = c->diagnostic; goto done; }
        if (seen) ready|=MU_EXEC;
        if ((flags & AES_MU_MESAG) && ExecAESMessageReady(c)) ready |= AES_MU_MESAG;
        if ((flags & AES_MU_TIMER) && !timerReady) {
            if (submitted && port_ready(c->timer.port)) {
                /* A successful absolute alarm proves expiry. Its terminal
                 * error is known before committing any selected payload. */
                if (!ExecAESTimerCollect(c, FALSE) || c->timer.error) {
                    status = AES_TIMER_ERROR;
                    goto done;
                }
                timerReady = TRUE;
            } else if (ready) {
                /* Any other readiness can race a due, unpublished alarm. */
                if (!ExecAESTimerRead(c)) { status = AES_TIMER_ERROR; goto done; }
                timerReady = c->timer.query->ticks_hi > high ||
                    (c->timer.query->ticks_hi == high && c->timer.query->ticks_lo >= low);
            }
        }
        if (timerReady) ready |= AES_MU_TIMER;
        Forbid();
        fresh=externalMask ? SetSignal(0,externalMask)&externalMask:0;
        seen|=fresh;
        if (seen) ready|=MU_EXEC;
        if (fresh && (flags&AES_MU_TIMER) && !timerReady) {
            Permit();continue; /* Include a due clock in the new decision. */
        }
        status = ExecAESInputCommitState(c, inputFlags);
        if (status != AES_OK) { Permit(); goto done; }
        if (!ExecAESInputStable(c, inputFlags) ||
            ((flags & AES_MU_MESAG) &&
             (ExecAESMessageReady(c) != ((ready & AES_MU_MESAG) != 0)))) {
            Permit();
            continue;
        }
        i = ready;
        if (inputFlags) ready = ExecAESInputLevel(c, ready, inputFlags);
        if ((ready & ~i & (AES_MU_BUTTON | AES_MU_M1)) &&
            (flags & AES_MU_TIMER) && !timerReady) {
            Permit();
            continue; /* New pointer readiness also needs the clock decision. */
        }
        if (ready) {
            record = (ready & AES_MU_MESAG) && !c->messagePending ?
                (struct AESDelivery *)c->receiving->mp_MsgList.lh_Head : NULL;
            ExecAESInputResult(c, ready);
            Permit();
            break;
        }
        Permit();
        if (!blocking) goto done;
        if ((flags & AES_MU_TIMER) && !submitted) {
            ExecAESTimerSend(c, high, low);
            submitted = TRUE;
            continue; /* Recheck immediate reply/arrival before sleeping. */
        }
        seen|=Wait(mask)&externalMask;
    }
    /* Readiness and result snapshots are now frozen. Later publication stays
     * queued for the following decision, including arrivals during AbortIO. */
    if (submitted && (!ExecAESTimerCollect(c, TRUE) || c->timer.error)) {
        status = AES_TIMER_ERROR;
        goto done;
    }
    submitted = FALSE;
    Forbid();
    /* Withdrawal may have completed during timer retirement. Do not commit a
       stale command; take a new event decision against the same deadline. */
    if ((ready & AES_MU_MESAG) && (!ExecAESMessageReady(c) ||
        (record ? record != (struct AESDelivery *)c->receiving->mp_MsgList.lh_Head :
                  !c->messagePending))) {
        Permit();
        goto decide;
    }
    status = ExecAESInputCommitState(c, inputFlags);
    if (status == AES_OK) {
        if ((ready & AES_MU_MESAG) && !c->messagePending) {
            record = (struct AESDelivery *)GetMsg(c->receiving);
            if (record == NULL) status = AES_MALFORMED;
        }
        if (status == AES_OK) {
            if (ready & AES_MU_KEYBD) input->keyHead = input->nextKey;
            if (ready & AES_MU_BUTTON) input->buttonHead = input->nextButton;
        }
    }
    Permit();
    if (status != AES_OK) goto done;
    if (ready & AES_MU_MESAG) {
        if (c->messagePending) {
            for (i=0;i<AES_MESSAGE_WORDS;++i) message[i]=c->deferredMessage[i];
            c->messageEpoch=c->deferredEpoch;
            c->messageMenuEpoch=c->deferredMenuEpoch;
            c->messagePending=0;
        } else {
            if (record == NULL) { status = AES_MALFORMED; goto done; }
            c->messageEpoch=c->messageMenuEpoch=0;
            if (record == &c->endpoint->gui->delivery) {
                c->messageEpoch=c->endpoint->gui->epoch;
                c->messageMenuEpoch=c->endpoint->gui->menuEpoch;
            }
            for (i = 0; i < AES_MESSAGE_WORDS; ++i) message[i] = record->words[i];
            ExecAESRecycle(c, record);
        }
    }
done:
    if (submitted && c->timer.state != AES_ALARM_IDLE &&
        (!ExecAESTimerCollect(c, TRUE) || c->timer.error)) status = AES_TIMER_ERROR;
    if (armed) {
        if (status == AES_INPUT_LOST && c->timer.state == AES_ALARM_IDLE) {
            i = ExecAESInputRecover(c, inputFlags);
            if (i != AES_OK) status = i;
        }
        if (blocking || status!=AES_OK) ExecAESInputDisarm(c);
    }
    if (status != AES_OK)
        for (i = 0; i < AES_INTOUT_WORDS; ++i) c->intout[i] = 0;
    /* An aborted GUI decision must not consume a caller's notification. New
     * arrivals during timer retirement already remain pending for next time. */
    if (status!=AES_OK && seen) { SetSignal(seen,seen);seen=0; }
    if (received) *received=seen;
    c->diagnostic = status;
    c->busy = 0;
    return status == AES_OK ? (WORD)ready : 0;
}

/* Poll retains input interest between DOS reads; its owner disarms at scan end.
 * It shares exactly the blocking path's selection and atomic payload commit. */
WORD ExecAESPoll(struct ExecAESContext *c,UWORD flags,WORD *message)
{
    return events(c,flags,0,message,FALSE,0,NULL);
}

WORD ExecAESEvents(struct ExecAESContext *c,UWORD flags,ULONG milliseconds,WORD *message)
{
    return events(c,flags,milliseconds,message,TRUE,0,NULL);
}

WORD ExecAESWait(struct ExecAESWaitSpec *spec)
{
    struct ExecAESContext *c=ExecAESContext();WORD result;
    if (!c) return 0;
    if (!ExecAESPointer(spec,sizeof(*spec))) { c->diagnostic=AES_MALFORMED;return 0; }
    memset(&spec->received,0,sizeof(*spec)-offsetof(struct ExecAESWaitSpec,received));
    if (c->busy) { c->diagnostic=AES_BUSY;return 0; }
    c->intin[0]=spec->flags;c->intin[1]=spec->buttonClicks;
    c->intin[2]=spec->buttonMask;c->intin[3]=spec->buttonState;
    c->intin[4]=spec->m1Flags;c->intin[5]=spec->m1X;c->intin[6]=spec->m1Y;
    c->intin[7]=spec->m1Width;c->intin[8]=spec->m1Height;
    result=events(c,spec->flags,spec->milliseconds,spec->message,TRUE,spec->signalMask,&spec->received);
    if (result) {
        spec->mouseX=c->intout[1];spec->mouseY=c->intout[2];spec->mouseButtons=c->intout[3];
        spec->keyState=c->intout[4];spec->key=c->intout[5];spec->clicks=c->intout[6];
    }
    return result;
}
