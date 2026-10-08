/* SPDX-License-Identifier: MIT */
#include <exec816/program.h>

/* The shell owns these three initial children. Files owns its launched child;
 * the shell's existing RUN job owns applications launched from the prompt. */
ULONG GEMDesktopChildren[3];
volatile UWORD GEMDesktopDone,GEMDesktopFailure;
static UWORD active;

LONG EXEC_CALL GEMDesktopCollect(ULONG unused)
{
    struct ExecProgramResult result;
    ULONG mask=0;
    UWORD i;
    for (i=0;i<3;++i) if (GEMDesktopChildren[i]) {
        if (ExecCollectProgram(GEMDesktopChildren[i],&result)) {
            GEMDesktopChildren[i]=0;++GEMDesktopDone;
            if (result.primary) GEMDesktopFailure=(UWORD)result.primary;
        } else mask|=ExecProgramMask(GEMDesktopChildren[i]);
    }
    return (LONG)mask;
}

LONG EXEC_CALL GEMDesktopStop(ULONG unused)
{
    struct ExecProgramResult result;
    UWORD i;
    for (i=0;i<3;++i) if (GEMDesktopChildren[i])
        if (!ExecBreakProgram(GEMDesktopChildren[i])) return 0;
    for (i=0;i<3;++i) if (GEMDesktopChildren[i]) {
        if (!ExecWaitProgram(GEMDesktopChildren[i],&result)) return 0;
        GEMDesktopChildren[i]=0;++GEMDesktopDone;
        if (result.primary) GEMDesktopFailure=(UWORD)result.primary;
    }
    active=0;return 1;
}

LONG EXEC_CALL GEMDesktopStart(ULONG files)
{
    if (active) return 0;
    active=1;GEMDesktopDone=GEMDesktopFailure=0;
    GEMDesktopChildren[0]=ExecStartProgram("SYS:C/PANEL.APP");
    GEMDesktopChildren[1]=ExecStartProgram("SYS:C/COUNTER.APP");
    if (files) GEMDesktopChildren[2]=ExecStartProgram("SYS:C/FILES.APP");
    if (!GEMDesktopChildren[0] || !GEMDesktopChildren[1] ||
        (files && !GEMDesktopChildren[2])) {
        GEMDesktopStop(0);return 0;
    }
    return 1;
}
