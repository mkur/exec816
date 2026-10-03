#include <exec/types.h>
volatile UWORD ConsoleFaultMode,ConsoleStopCount,ConsoleCopyChunks,ConsoleTextChunks;
UBYTE ConsoleFaultBusy(void)
{
    if (ConsoleFaultMode>=5) {
        if (ConsoleTextChunks) return 3;
    } else if (ConsoleFaultMode && (ConsoleFaultMode<3 || ConsoleCopyChunks)) return 3;
    return *(volatile UBYTE *)0xd653UL;
}
void ConsoleFaultStop(void)
{
    ++ConsoleStopCount;
    if (ConsoleFaultMode&1) ConsoleFaultMode=0;
}

void ConsoleFaultCopy(void) { ++ConsoleCopyChunks; }
/* Ignore initialization and one-cell caret restoration. Fail the first full
 * text batch so the test can reject a following batch after terminal failure. */
void ConsoleFaultText(UWORD count)
{
    if (ConsoleFaultMode>=5 && count==32) ++ConsoleTextChunks;
}
