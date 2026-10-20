/* SPDX-License-Identifier: MIT */
#include <exec816/program.h>
#include <proto/dos.h>

/* The shell owns the desktop supervisor, or the older two-app test profile.
 * The desktop owns applications it launches; RUN jobs remain shell-owned. */
ULONG GEMDesktopChildren[3];
volatile UWORD GEMDesktopDone,GEMDesktopFailure;
static UWORD active;

/* Boot assets live in upper RAM in the XEX. Use the ordinary RAM filesystem
 * and program loader; no application code or resource relocation lives here. */
static WORD store(const char *name,const UBYTE *data,ULONG bytes)
{
    BPTR file=Open(name,MODE_NEWFILE);
    LONG written;
    WORD okay=1;
    if (!file) return 0;
    while (bytes) {
        written=Write(file,data,bytes>16384 ? 16384:(LONG)bytes);
        if (written<=0) { okay=0;break; }
        data+=written;bytes-=written;
    }
    if (!Close(file)) okay=0;
    if (!okay) DeleteFile(name);
    return okay;
}

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

LONG EXEC_CALL GEMDesktopStart(ULONG assets)
{
    if (active) return 0;
    if (assets) {
        /* Builder-owned pair: two ULONG lengths, then APP and RSC bytes. */
        const ULONG *sizes=(const ULONG *)assets;
        const UBYTE *data=(const UBYTE *)(sizes+2);
        if (!store("RAM:DESKTOP.APP",data,sizes[0])) return 0;
        if (!store("RAM:DESKTOP.RSC",data+sizes[0],sizes[1])) {
            DeleteFile("RAM:DESKTOP.APP");return 0;
        }
    }
    active=1;GEMDesktopDone=GEMDesktopFailure=0;
    GEMDesktopChildren[0]=ExecStartProgram(assets ? "RAM:DESKTOP.APP":"SYS:C/PANEL.APP",NULL);
    if (!assets) GEMDesktopChildren[1]=ExecStartProgram("SYS:C/COUNTER.APP",NULL);
    if (!GEMDesktopChildren[0] || (!assets && !GEMDesktopChildren[1])) {
        GEMDesktopStop(0);return 0;
    }
    return 1;
}
