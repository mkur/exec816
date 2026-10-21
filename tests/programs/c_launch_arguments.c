/* SPDX-License-Identifier: MIT */
#include <exec816/program.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <exec/memory.h>
#include <string.h>

volatile UBYTE LaunchRelease;
UWORD LaunchChecks;
ULONG LaunchBefore,LaunchAfter;
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
    LONG failed,step;UWORD i,j;
    APTR job,image;
    (void)unused;
    ULONG baseline;
    struct ExecProgramStart start={0};
    failed=launch(0,7);if (failed) return failed;
    baseline=AvailMem(0);
    LaunchBefore=baseline;
    failed=launch(1,8);if (failed) return failed;
    LaunchAfter=AvailMem(0);
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
    for (i=0;i<6;++i) {
        job=ExecLoadBegin("D1:ARGS");CHECK(job);
        for (j=0;j<i;++j) { step=ExecLoadStep(job);CHECK(step>=0); }
        ExecLoadCancel(job);CHECK(AvailMem(0)==baseline);
    }
    job=ExecLoadBegin("D1:ARGS");CHECK(job);
    CHECK(!ExecLoadTake(job));CHECK(IoErr()==ERROR_OBJECT_IN_USE);
    for (i=0;i<64;++i) { step=ExecLoadStep(job);if (step) break; }
    CHECK(step==1);CHECK(i<64);
    image=ExecLoadTake(job);CHECK(image);
    start.arguments=NULL;start.length=0;LaunchRelease=1;
    {
        struct ExecProgramResult result;
        ULONG child=ExecStartLoaded(image,&start);CHECK(child);
        ExecReleaseProgram(image);
        CHECK(ExecWaitProgram(child,&result));CHECK(result.primary==7);
    }
    CHECK(AvailMem(0)==baseline);
    job=ExecLoadBegin("D1:EMPTY");CHECK(job);
    CHECK(ExecLoadStep(job)==0);CHECK(ExecLoadStep(job)==-1);
    CHECK(IoErr()==306);ExecLoadCancel(job);
    CHECK(AvailMem(0)==baseline);
    return 0;
}

int main(void) { return 0; }
