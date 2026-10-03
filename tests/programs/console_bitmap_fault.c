#include <exec/types.h>
volatile UWORD ConsoleFaultMode,ConsoleStopCount,ConsoleCopyChunks;
UBYTE ConsoleFaultBusy(void)
{
    if (ConsoleFaultMode && (ConsoleFaultMode<3 || ConsoleCopyChunks)) return 3;
    return *(volatile UBYTE *)0xd653UL;
}
void ConsoleFaultStop(void)
{
    ++ConsoleStopCount;
    if (ConsoleFaultMode==1 || ConsoleFaultMode==3) ConsoleFaultMode=0;
}

void ConsoleFaultCopy(void) { ++ConsoleCopyChunks; }
