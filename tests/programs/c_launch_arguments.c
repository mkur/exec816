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
    struct ExecProgramStart start={0};
    char *args=AllocMem(256,MEMF_UPPER);
    ULONG child;
    CHECK(args);
    memset(args,'A',255);args[255]=0;
    LaunchRelease=0;
    start.arguments=length ? args:NULL;start.length=length;
    child=ExecStartProgram("D1:ARGS",&start);
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
    struct ExecProgramStart start={0};
    failed=launch(0,7);if (failed) return failed;
    baseline=AvailMem(0);
    failed=launch(1,8);if (failed) return failed;
    CHECK(AvailMem(0)==baseline);
    failed=launch(255,9);if (failed) return failed;
    CHECK(AvailMem(0)==baseline);
    start.arguments="A";start.length=256;
    CHECK(!ExecStartProgram("D1:ARGS",&start));
    CHECK(IoErr()==ERROR_BAD_NUMBER);
    CHECK(AvailMem(0)==baseline);
    start.arguments="A\0B";start.length=3;
    CHECK(!ExecStartProgram("D1:ARGS",&start));
    CHECK(IoErr()==ERROR_BAD_NUMBER);
    CHECK(AvailMem(0)==baseline);
    CHECK(!ExecStartProgram("D1:MISSING",&start));
    CHECK(AvailMem(0)==baseline);
    return 0;
}

int main(void) { return 0; }
