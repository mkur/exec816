#include "clock.h"

void BenchClockClose(struct BenchClock *c)
{
    if (c->opened) { CloseDevice(&c->request->tc_Request); c->opened=0; }
    if (c->request) { DeleteIORequest(&c->request->tc_Request); c->request=NULL; }
    if (c->port) { DeleteMsgPort(c->port); c->port=NULL; }
}

WORD BenchClockOpen(struct BenchClock *c)
{
    c->port=CreateMsgPort();
    if (!c->port) return 0;
    c->request=(struct TimerClockRequest *)CreateIORequest(c->port,sizeof(*c->request));
    if (!c->request || OpenDevice("timer.device",UNIT_VBLANK,&c->request->tc_Request,0)) {
        BenchClockClose(c); return 0;
    }
    c->opened=1;
    return 1;
}

WORD BenchClockRead(struct BenchClock *c,struct BenchTick *tick)
{
    c->request->tc_Request.io_Command=TD_READCLOCK;
    if (DoIO(&c->request->tc_Request)) return 0;
    tick->high=c->request->ticks_hi;
    tick->low=c->request->ticks_lo;
    tick->rate=c->request->ticks_per_second;
    return tick->rate==50 || tick->rate==60;
}

/* Samples are bounded to less than 2^32 ticks. Reject clock reversal or a
 * changed rate, and carry the low-word borrow across the 64-bit snapshot. */
WORD BenchElapsed(const struct BenchTick *start,const struct BenchTick *end,ULONG *elapsed)
{
    ULONG borrow=end->low<start->low;
    if (end->rate!=start->rate || (end->rate!=50 && end->rate!=60) ||
        end->high<start->high || end->high-start->high!=borrow) return 0;
    *elapsed=end->low-start->low;
    return 1;
}
