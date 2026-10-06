#include "aes-private.h"
#include <proto/exec.h>

/* Called exactly once at a public direct-call boundary. Helpers use the
 * admitted context instead of looking it up or entering it recursively. */
BOOL ExecAESEnter(struct ExecAESContext *c)
{
    if (c->busy) { c->diagnostic = AES_BUSY; return FALSE; }
    if (c->identity == 0) { c->diagnostic = AES_IDENTITY; return FALSE; }
    Forbid();
    if (c->endpoint == NULL || c->endpoint->state != AES_ENDPOINT_ACCEPTING ||
        c->endpoint->id != c->identity || c->endpoint->owner != c->request.owner) {
        Permit();
        c->diagnostic = AES_IDENTITY;
        return FALSE;
    }
    c->busy = 1;
    Permit();
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
