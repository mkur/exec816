/* SPDX-License-Identifier: MIT */
#include <exec816/console.h>

/* Bound by the platform's console library, above the Exec gateway. */
void EXEC_PTR *ExecConsoleEntries[5];
struct ConsoleArgs { ULONG a,b,c; };
ULONG EXEC_CALL _ConsoleCall(UWORD,const struct ConsoleArgs *);

ULONG EXEC_CALL ExecConsoleCreate(UWORD width,UWORD height)
{
    struct ConsoleArgs args={width,height,0};
    return _ConsoleCall(sizeof(ExecConsoleEntries[0]),&args);
}

LONG EXEC_CALL ExecConsoleDestroy(ULONG unit)
{
    struct ConsoleArgs args={unit,0,0};
    return _ConsoleCall(2*sizeof(ExecConsoleEntries[0]),&args);
}

LONG EXEC_CALL ExecConsoleMode(BPTR console,UWORD mode)
{
    struct ConsoleArgs args={console,mode,0};
    return _ConsoleCall(3*sizeof(ExecConsoleEntries[0]),&args);
}

LONG EXEC_CALL ExecConsoleGetMode(BPTR console)
{
    struct ConsoleArgs args={console,0,0};
    return _ConsoleCall(4*sizeof(ExecConsoleEntries[0]),&args);
}
