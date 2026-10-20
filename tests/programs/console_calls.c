/* WB7 scalar ABI probe: raw and optimized C bindings, real native services. */
#include <exec816/console.h>
#include <proto/dos.h>
ULONG EXEC_CALL ConsoleRawCreate(UWORD,UWORD);
LONG EXEC_CALL ConsoleRawDestroy(ULONG);
LONG EXEC_CALL ConsoleRawMode(BPTR,UWORD);
LONG EXEC_CALL ConsoleRawGetMode(BPTR);
UWORD CWABIChecks;
#define CHECK(x) do { ++CWABIChecks;if (!(x)) return __LINE__; } while (0)

LONG EXEC_CALL CWABIProbe(ULONG unused)
{
    UWORD raw,i;ULONG unit;BPTR file;char path[13]="CON:00000000";
    (void)unused;
    for (raw=0;raw<2;++raw) {
        CHECK(!(raw ? ConsoleRawCreate(0xffff,20):ExecConsoleCreate(0xffff,20)));
        unit=raw ? ConsoleRawCreate(64,20):ExecConsoleCreate(64,20);CHECK(unit);
        CHECK(!(raw ? ConsoleRawDestroy(unit|0x1000000UL):ExecConsoleDestroy(unit|0x1000000UL)));
        for (i=0;i<8;++i) path[4+i]="0123456789ABCDEF"[(unit>>((7-i)*4))&15];
        file=Open(path,MODE_OLDFILE);CHECK(file);
        CHECK((raw ? ConsoleRawGetMode(file):ExecConsoleGetMode(file))==0);
        CHECK((raw ? ConsoleRawMode(file,EXEC_CONSOLE_ATASCII):ExecConsoleMode(file,EXEC_CONSOLE_ATASCII))==1);
        CHECK((raw ? ConsoleRawGetMode(file):ExecConsoleGetMode(file))==EXEC_CONSOLE_ATASCII);
        CHECK(!(raw ? ConsoleRawDestroy(unit):ExecConsoleDestroy(unit)));
        CHECK(Close(file));
        CHECK(raw ? ConsoleRawDestroy(unit):ExecConsoleDestroy(unit));
    }
    return 0;
}
