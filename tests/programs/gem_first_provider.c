/* SPDX-License-Identifier: MIT */
#include <exec816/program.h>
#include <proto/dos.h>

ULONG GFChildren[2];
UWORD GFFailure;

/* Real Program/Process loading owns private code/data and break scopes. */
LONG EXEC_CALL GFStart(ULONG variant)
{
    struct ExecProgramStart spec={0};
    spec.arguments="1";spec.length=1;
    GFChildren[0]=ExecStartProgram("D1:C/COUNTER.APP",&spec);
    if (!GFChildren[0]) { GFFailure=(UWORD)IoErr();return 0; }
    spec.arguments=variant==2 ? "i":variant==3 ? "u":variant==4 ? "c":"2";
    GFChildren[1]=ExecStartProgram("D1:C/COUNTER.APP",&spec);
    if (!GFChildren[1]) { GFFailure=(UWORD)IoErr();return 0; }
    return 1;
}

LONG EXEC_CALL GFAbort(ULONG unused)
{
    (void)unused;
    return GFChildren[1] && ExecBreakProgram(GFChildren[1]);
}

LONG EXEC_CALL GFStop(ULONG unused)
{
    struct ExecProgramResult result;
    UWORD i;
    (void)unused;
    for (i=0;i<2;++i) if (GFChildren[i])
        if (!ExecBreakProgram(GFChildren[i])) return 0;
    for (i=0;i<2;++i) if (GFChildren[i]) {
        if (!ExecWaitProgram(GFChildren[i],&result)) return 0;
        if (result.primary) GFFailure=(UWORD)result.primary;
        GFChildren[i]=0;
    }
    return !GFFailure;
}
