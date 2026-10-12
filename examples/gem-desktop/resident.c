/* SPDX-License-Identifier: MIT */
#include <exec816/program.h>

/* The shell owns the desktop supervisor, or the older two-app test profile.
 * The desktop owns applications it launches; RUN jobs remain shell-owned. */
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
    GEMDesktopChildren[0]=ExecStartProgram(files ? "SYS:C/DESKTOP.APP":"SYS:C/PANEL.APP",NULL,0);
    if (!files) GEMDesktopChildren[1]=ExecStartProgram("SYS:C/COUNTER.APP",NULL,0);
    if (!GEMDesktopChildren[0] || (!files && !GEMDesktopChildren[1])) {
        GEMDesktopStop(0);return 0;
    }
    return 1;
}
