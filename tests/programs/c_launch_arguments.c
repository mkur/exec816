/* SPDX-License-Identifier: MIT */
#include <exec816/program.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <exec/memory.h>
#include <string.h>

volatile UBYTE LaunchRelease;
UWORD LaunchChecks;
#define CHECK(test) do { ++LaunchChecks;if (!(test)) return __LINE__; } while (0)

static LONG launch(UWORD length,LONG expected)
{
    struct ExecProgramResult result;
    char *args=AllocMem(256,MEMF_UPPER);
    ULONG child;
    CHECK(args);
    memset(args,'A',255);args[255]=0;
    LaunchRelease=0;
    child=ExecStartProgram("D1:ARGS",length ? args:NULL,length);
    memset(args,'Z',256);FreeMem(args,256);
    LaunchRelease=1;
    CHECK(child);
    CHECK(ExecWaitProgram(child,&result));
    CHECK(result.primary==expected);
    return 0;
}

LONG EXEC_CALL LaunchProbe(ULONG unused)
{
    LONG failed;
    (void)unused;
    ULONG baseline;
    failed=launch(0,7);if (failed) return failed;
    baseline=AvailMem(0);
    failed=launch(1,8);if (failed) return failed;
    CHECK(AvailMem(0)==baseline);
    failed=launch(255,9);if (failed) return failed;
    CHECK(AvailMem(0)==baseline);
    CHECK(!ExecStartProgram("D1:ARGS","A",256));
    CHECK(IoErr()==ERROR_BAD_NUMBER);
    CHECK(AvailMem(0)==baseline);
    CHECK(!ExecStartProgram("D1:ARGS","A\0B",3));
    CHECK(IoErr()==ERROR_BAD_NUMBER);
    CHECK(AvailMem(0)==baseline);
    CHECK(!ExecStartProgram("D1:MISSING","A",1));
    CHECK(AvailMem(0)==baseline);
    return 0;
}

int main(void) { return 0; }
