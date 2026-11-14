/* SPDX-License-Identifier: MIT. Extracted from the QED native adapter. */
#include "gemdos-internal.h"
#include <proto/dos.h>
#include <calypsi/stubs.h>
#include <fcntl.h>

LONG ExecGemdosResult(LONG result)
{
    if (result>=0) return result;
    switch (ExecCRuntimeFileError()) {
    case ERROR_OBJECT_NOT_FOUND:return GEMDOS_EFILNF;
    case ERROR_DIR_NOT_FOUND:return GEMDOS_EPTHNF;
    case ERROR_NO_MORE_ENTRIES:return GEMDOS_ENHNDL;
    case ERROR_BAD_NUMBER:return GEMDOS_EBADF;
    case ERROR_NO_FREE_STORE:return GEMDOS_ENSMEM;
    case ERROR_ACTION_NOT_KNOWN:return GEMDOS_EINVFN;
    case ERROR_BAD_ARGUMENTS:case ERROR_SEEK_ERROR:return GEMDOS_ERANGE;
    case ERROR_WRITE_PROTECTED:case ERROR_DELETE_PROTECTED:
    case ERROR_DISK_WRITE_PROTECTED:case ERROR_OBJECT_IN_USE:
    case ERROR_OBJECT_EXISTS:return GEMDOS_EACCDN;
    default:return -1;
    }
}
LONG Fopen(const char *path,WORD mode)
{
    if (mode<0 || mode>2) return ExecGemdosResult(ExecCRuntimeFail(ERROR_ACTION_NOT_KNOWN));
    return ExecGemdosResult(_Stub_open(path,mode==0 ? O_RDONLY:mode==1 ? O_WRONLY:O_RDWR));
}
LONG Fcreate(const char *path,WORD attributes)
{
    return attributes ? ExecGemdosResult(ExecCRuntimeFail(ERROR_ACTION_NOT_KNOWN)):
        ExecGemdosResult(_Stub_open(path,O_WRONLY|O_CREAT|O_TRUNC));
}
LONG Fclose(WORD fd) { return ExecGemdosResult(_Stub_close(fd)); }
LONG Fread(WORD fd,LONG bytes,void *buffer)
{ return ExecGemdosResult(ExecCRuntimeRead(fd,buffer,bytes)); }
LONG Fwrite(WORD fd,LONG bytes,const void *buffer)
{ return ExecGemdosResult(ExecCRuntimeWrite(fd,buffer,bytes)); }
LONG Fseek(LONG offset,WORD fd,WORD origin)
{ return ExecGemdosResult(_Stub_lseek(fd,offset,origin)); }
LONG Fdelete(const char *path) { return ExecGemdosResult(_Stub_remove(path)); }
LONG Frename(WORD zero,const char *before,const char *after)
{ return zero ? ExecGemdosResult(ExecCRuntimeFail(ERROR_BAD_ARGUMENTS)):
    ExecGemdosResult(_Stub_rename(before,after)); }
