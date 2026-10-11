#ifndef PROTO_DOS_H
#define PROTO_DOS_H

#include <dos/dos.h>

BPTR EXEC_CALL Output(void);
LONG EXEC_CALL Write(BPTR file, const void *buffer, LONG length);

BPTR EXEC_CALL Open(CONST_STRPTR name,LONG mode);
LONG EXEC_CALL Close(BPTR file);
LONG EXEC_CALL Read(BPTR file,void *buffer,LONG length);
BPTR EXEC_CALL Lock(CONST_STRPTR name,LONG mode);
void EXEC_CALL UnLock(BPTR lock);
LONG EXEC_CALL Examine(BPTR lock,struct FileInfoBlock *info);
LONG EXEC_CALL ExNext(BPTR lock,struct FileInfoBlock *info);
LONG EXEC_CALL IoErr(void);
BPTR EXEC_CALL CreateDir(CONST_STRPTR name);
LONG EXEC_CALL Rename(CONST_STRPTR oldName,CONST_STRPTR newName);
LONG EXEC_CALL Seek(BPTR file,LONG position,LONG mode);
/* Release an idle caller context after all handles/locks/selections retire. */
LONG EXEC_CALL ExecDOSDetach(void);
#endif
