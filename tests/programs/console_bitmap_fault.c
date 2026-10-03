#include <exec/types.h>
volatile UWORD ConsoleFaultMode,ConsoleStopCount;
UBYTE ConsoleFaultBusy(void)
{
    if (ConsoleFaultMode) return 3;
    return *(volatile UBYTE *)0xd653UL;
}
void ConsoleFaultStop(void)
{
    ++ConsoleStopCount;
    if (ConsoleFaultMode==1) ConsoleFaultMode=0;
}
