#include <proto/dos.h>
#include "dos-bridge.h"
#include "dos-entries.h"
#include <exec816/program.h>
#include <exec816/fastbasic-interpreter.h>

/* The launcher installs these native entry addresses before entering C. */
void EXEC_PTR *ExecDosEntries[C_DOS_COUNT];

ULONG EXEC_CALL _DosCall(UWORD entry, const struct ExecDosWriteArgs *args);

BPTR EXEC_CALL Output(void)
{
    return (BPTR)_DosCall(C_DOS_OUTPUT*sizeof(ExecDosEntries[0]), NULL);
}

LONG EXEC_CALL Write(BPTR file, const void *buffer, LONG length)
{
    struct ExecDosWriteArgs args = {(ULONG)file, (ULONG)buffer, length};
    return (LONG)_DosCall(C_DOS_WRITE*sizeof(ExecDosEntries[0]), &args);
}

static ULONG call(UWORD entry,ULONG a,ULONG b,LONG c)
{
    struct ExecDosWriteArgs args={a,b,c};
    return _DosCall(entry*sizeof(ExecDosEntries[0]),&args);
}
BPTR EXEC_CALL Open(CONST_STRPTR name,LONG mode) { return call(C_DOS_OPEN,(ULONG)name,mode,0); }
LONG EXEC_CALL Close(BPTR file) { return call(C_DOS_CLOSE,file,0,0); }
LONG EXEC_CALL Read(BPTR file,void *buffer,LONG length) { return call(C_DOS_READ,file,(ULONG)buffer,length); }
BPTR EXEC_CALL Lock(CONST_STRPTR name,LONG mode) { return call(C_DOS_LOCK,(ULONG)name,mode,0); }
void EXEC_CALL UnLock(BPTR lock) { call(C_DOS_UNLOCK,lock,0,0); }
LONG EXEC_CALL Examine(BPTR lock,struct FileInfoBlock *info) { return call(C_DOS_EXAMINE,lock,(ULONG)info,0); }
LONG EXEC_CALL ExNext(BPTR lock,struct FileInfoBlock *info) { return call(C_DOS_EXNEXT,lock,(ULONG)info,0); }
LONG EXEC_CALL IoErr(void) { return call(C_DOS_IOERR,0,0,0); }
LONG EXEC_CALL Seek(BPTR file,LONG position,LONG mode) { return call(C_DOS_SEEK,file,position,mode); }
LONG EXEC_CALL ExecDOSDetach(void) { return call(C_DOS_EXECDOSDETACH,0,0,0); }
ULONG EXEC_CALL ExecStartProgram(CONST_STRPTR name,const struct ExecProgramStart *spec)
{ return call(C_DOS_EXECSTARTPROGRAM,(ULONG)name,(ULONG)spec,0); }
LONG EXEC_CALL ExecCollectProgram(ULONG id,struct ExecProgramResult *result) { return call(C_DOS_EXECCOLLECTPROGRAM,id,(ULONG)result,0); }
LONG EXEC_CALL ExecBreakProgram(ULONG id) { return call(C_DOS_EXECBREAKPROGRAM,id,0,0); }
LONG EXEC_CALL ExecWaitProgram(ULONG id,struct ExecProgramResult *result) { return call(C_DOS_EXECWAITPROGRAM,id,(ULONG)result,0); }
CONST_STRPTR EXEC_CALL ExecGetArgStr(void) { return (CONST_STRPTR)call(C_DOS_EXECGETARGSTR,0,0,0); }
ULONG EXEC_CALL ExecProgramMask(ULONG id) { return call(C_DOS_EXECPROGRAMMASK,id,0,0); }
BPTR EXEC_CALL CreateDir(CONST_STRPTR name) { return call(C_DOS_CREATEDIR,(ULONG)name,0,0); }
LONG EXEC_CALL Rename(CONST_STRPTR oldName,CONST_STRPTR newName) { return call(C_DOS_RENAME,(ULONG)oldName,(ULONG)newName,0); }
LONG EXEC_CALL DeleteFile(CONST_STRPTR name) { return call(C_DOS_DELETEFILE,(ULONG)name,0,0); }
LONG EXEC_CALL ExamineExact(BPTR lock,struct FileInfoBlock *info) { return call(C_DOS_EXAMINEEXACT,lock,(ULONG)info,0); }
LONG EXEC_CALL MountVolume(CONST_STRPTR name,const struct SioMountSpec *spec) { return call(C_DOS_MOUNTVOLUME,(ULONG)name,(ULONG)spec,0); }
LONG EXEC_CALL UnmountVolume(CONST_STRPTR name) { return call(C_DOS_UNMOUNTVOLUME,(ULONG)name,0,0); }
LONG EXEC_CALL ExNextBatch(BPTR lock,struct FileInfoBlock *info,struct DirBatch *batch)
{ return call(C_DOS_EXNEXTBATCH,lock,(ULONG)info,(LONG)(ULONG)batch); }

LONG EXEC_CALL SetIoErr(LONG error) { return call(C_DOS_SETIOERR,(ULONG)error,0,0); }

LONG EXEC_CALL NameFromLock(BPTR lock,STRPTR buffer,LONG length)
{ return call(C_DOS_NAMEFROMLOCK,lock,(ULONG)buffer,length); }

BPTR EXEC_CALL Input(void) { return call(C_DOS_INPUT,0,0,0); }
APTR EXEC_CALL ExecLoadProgram(CONST_STRPTR name) { return (APTR)call(C_DOS_EXECLOADPROGRAM,(ULONG)name,0,0); }
void EXEC_CALL ExecReleaseProgram(APTR image) { call(C_DOS_EXECRELEASEPROGRAM,(ULONG)image,0,0); }
ULONG EXEC_CALL ExecStartLoaded(APTR image,const struct ExecProgramStart *spec)
{ return call(C_DOS_EXECSTARTLOADED,(ULONG)image,(ULONG)spec,0); }
APTR EXEC_CALL ExecLoadBegin(CONST_STRPTR path) { return (APTR)call(C_DOS_EXECLOADBEGIN,(ULONG)path,0,0); }
LONG EXEC_CALL ExecLoadStep(APTR job) { return call(C_DOS_EXECLOADSTEP,(ULONG)job,0,0); }
APTR EXEC_CALL ExecLoadTake(APTR job) { return (APTR)call(C_DOS_EXECLOADTAKE,(ULONG)job,0,0); }
void EXEC_CALL ExecLoadCancel(APTR job) { call(C_DOS_EXECLOADCANCEL,(ULONG)job,0,0); }
LONG EXEC_CALL ExecBasicAttach(APTR image,const struct ExecBasicSource *source)
{ return call(C_DOS_EXECBASICATTACH,(ULONG)image,(ULONG)source,0); }
