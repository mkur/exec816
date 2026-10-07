#include <proto/dos.h>
#include "dos-bridge.h"
#include <exec816/program.h>

/* The launcher installs these native entry addresses before entering C. */
void EXEC_PTR *ExecDosEntries[16];

ULONG EXEC_CALL _DosCall(UWORD entry, const struct ExecDosWriteArgs *args);

BPTR EXEC_CALL Output(void)
{
    return (BPTR)_DosCall(0, NULL);
}

LONG EXEC_CALL Write(BPTR file, const void *buffer, LONG length)
{
    struct ExecDosWriteArgs args = {(ULONG)file, (ULONG)buffer, length};
    return (LONG)_DosCall(sizeof(ExecDosEntries[0]), &args);
}

static ULONG call(UWORD entry,ULONG a,ULONG b,LONG c)
{
    struct ExecDosWriteArgs args={a,b,c};
    return _DosCall(entry*sizeof(ExecDosEntries[0]),&args);
}
BPTR EXEC_CALL Open(CONST_STRPTR name,LONG mode) { return call(2,(ULONG)name,mode,0); }
LONG EXEC_CALL Close(BPTR file) { return call(3,file,0,0); }
LONG EXEC_CALL Read(BPTR file,void *buffer,LONG length) { return call(4,file,(ULONG)buffer,length); }
BPTR EXEC_CALL Lock(CONST_STRPTR name,LONG mode) { return call(5,(ULONG)name,mode,0); }
void EXEC_CALL UnLock(BPTR lock) { call(6,lock,0,0); }
LONG EXEC_CALL Examine(BPTR lock,struct FileInfoBlock *info) { return call(7,lock,(ULONG)info,0); }
LONG EXEC_CALL ExNext(BPTR lock,struct FileInfoBlock *info) { return call(8,lock,(ULONG)info,0); }
LONG EXEC_CALL IoErr(void) { return call(9,0,0,0); }
LONG EXEC_CALL Seek(BPTR file,LONG position,LONG mode) { return call(10,file,position,mode); }
LONG EXEC_CALL ExecDOSDetach(void) { return call(11,0,0,0); }
ULONG EXEC_CALL ExecStartProgram(CONST_STRPTR name) { return call(12,(ULONG)name,0,0); }
LONG EXEC_CALL ExecCollectProgram(ULONG id,struct ExecProgramResult *result) { return call(13,id,(ULONG)result,0); }
LONG EXEC_CALL ExecBreakProgram(ULONG id) { return call(14,id,0,0); }
LONG EXEC_CALL ExecWaitProgram(ULONG id,struct ExecProgramResult *result) { return call(15,id,(ULONG)result,0); }
