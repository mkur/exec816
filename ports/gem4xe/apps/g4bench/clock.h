/* Exec adapter for the donor benchmark; GPL-2.0-or-later. */
#ifndef G4BENCH_CLOCK_H
#define G4BENCH_CLOCK_H
#include <devices/timer.h>
#include <proto/exec.h>

struct BenchTick { ULONG high,low,rate; };
struct BenchClock {
    struct MsgPort *port;
    struct TimerClockRequest *request;
    WORD opened;
};
WORD BenchClockOpen(struct BenchClock *);
void BenchClockClose(struct BenchClock *);
WORD BenchClockRead(struct BenchClock *,struct BenchTick *);
WORD BenchElapsed(const struct BenchTick *,const struct BenchTick *,ULONG *);
#endif
