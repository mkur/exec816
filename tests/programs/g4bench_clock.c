/* Emitted clock adapter regression, including eight-binding exhaustion. */
#include "../../ports/gem4xe/apps/g4bench/clock.h"
static struct BenchClock clocks[9];
static struct BenchTick start,end;

int main(void)
{
    WORD i,result=0;
    ULONG elapsed;
    start.high=7;start.low=0xfffffff0UL;start.rate=50;
    end.high=8;end.low=0x20;end.rate=50;
    if (!BenchElapsed(&start,&end,&elapsed) || elapsed!=48) return 1;
    end.rate=60;
    if (BenchElapsed(&start,&end,&elapsed)) return 2;
    end.rate=50;end.high=7;
    if (BenchElapsed(&start,&end,&elapsed)) return 3;
    end.high=9;
    if (BenchElapsed(&start,&end,&elapsed)) return 4;
    end=start;
    if (!BenchElapsed(&start,&end,&elapsed) || elapsed) return 5;
    for (i=0;i<8;++i) {
        if (!BenchClockOpen(&clocks[i])) { result=6;goto finish; }
        if (!BenchClockRead(&clocks[i],&start) ||
            !BenchClockRead(&clocks[i],&end) || !BenchElapsed(&start,&end,&elapsed)) {
            result=7;goto finish;
        }
    }
    if (BenchClockOpen(&clocks[8])) { result=8;goto finish; }
    if (clocks[8].port || clocks[8].request || clocks[8].opened) { result=9;goto finish; }
    BenchClockClose(&clocks[0]);
    if (!BenchClockOpen(&clocks[8]) || !BenchClockRead(&clocks[8],&end)) result=10;
finish:
    for (i=0;i<9;++i) BenchClockClose(&clocks[i]);
    return result;
}
