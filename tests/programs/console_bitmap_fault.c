#include <exec/types.h>
volatile UWORD ConsoleFaultMode,ConsoleStopCount,ConsoleCopyChunks,ConsoleTextChunks,ConsoleTextFillRows;
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
/* Fail the first full text batch, or the one-cell combined text/caret list. */
void ConsoleFaultText(UWORD count,UWORD fillRows)
{
    if ((ConsoleFaultMode>=5 && ConsoleFaultMode<=6 && count==32) ||
        (ConsoleFaultMode>=7 && count==1)) {
        ++ConsoleTextChunks;
        ConsoleTextFillRows=fillRows;
    }
}
