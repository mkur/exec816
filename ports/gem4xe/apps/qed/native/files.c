/* SPDX-License-Identifier: MIT. Thin GEMDOS compatibility over the common CRT. */
#include "qed-files.h"
#include "internal.h"
#include <calypsi/stubs.h>
#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
static LONG gem_error(LONG result)
{
    if (result>=0) return result;
    switch (ExecCRuntimeErrorCode(ExecCRuntimeFileError())) {
    case ENOENT:return -33;
    case EMFILE:return -35;
    case EBADF:return -37;
    case ENOMEM:return -39;
    case ENOSYS:return -32;
    case EINVAL:return -64;
    case EACCES:case EROFS:case EBUSY:case EEXIST:return -36;
    default:return -1;
    }
}
LONG Fopen(const char *path,WORD mode)
{
    if (mode<0 || mode>2) return gem_error(ExecCRuntimeFail(ERROR_ACTION_NOT_KNOWN));
    return gem_error(_Stub_open(path,mode==0 ? O_RDONLY:mode==1 ? O_WRONLY:O_RDWR));
}
LONG Fcreate(const char *path,WORD attributes)
{
    return attributes ? gem_error(ExecCRuntimeFail(ERROR_ACTION_NOT_KNOWN)):
        gem_error(_Stub_open(path,O_WRONLY|O_CREAT|O_TRUNC));
}
LONG QedFileExclusive(const char *path)
{ return gem_error(_Stub_open(path,O_WRONLY|O_CREAT|O_EXCL)); }
LONG QedFileCloseError(void) { return ExecCRuntimeCloseError(); }
LONG Fclose(WORD fd) { return gem_error(_Stub_close(fd)); }
LONG Fread(WORD fd,LONG bytes,void *buffer)
{ return gem_error(ExecCRuntimeRead(fd,buffer,bytes)); }
LONG Fwrite(WORD fd,LONG bytes,const void *buffer)
{ return gem_error(ExecCRuntimeWrite(fd,buffer,bytes)); }
LONG Fseek(LONG offset,WORD fd,WORD origin) { return gem_error(_Stub_lseek(fd,offset,origin)); }
LONG Fdelete(const char *path) { return gem_error(_Stub_remove(path)); }
LONG Frename(WORD zero,const char *before,const char *after)
{ return zero ? gem_error(ExecCRuntimeFail(ERROR_BAD_ARGUMENTS)):gem_error(_Stub_rename(before,after)); }
LONG QedFileError(void) { return ExecCRuntimeFileError(); }
UWORD QedFileCount(void) { return ExecCRuntimeFileCount(); }
int QedFileInfo(const char *path,struct QedFileInfo *info)
{
    BPTR lock=Lock(path,SHARED_LOCK);
    struct FileInfoBlock *fib;
    LONG error;
    if (!lock) { ExecCRuntimeFail(IoErr());return 0; }
    fib=malloc(sizeof(*fib));
    if (!fib) { UnLock(lock);ExecCRuntimeFail(ERROR_NO_FREE_STORE);return 0; }
    if (!ExamineExact(lock,fib)) {
        error=IoErr();free(fib);UnLock(lock);ExecCRuntimeFail(error);return 0;
    }
    info->size=fib->fib_Size;info->protection=fib->fib_Protection;
    info->kind=fib->fib_DirEntryType;info->date=fib->fib_Date;
    info->sizeKnown=(fib->fib_InfoFlags&FIB_SIZE_EXACT)!=0;
    info->dateKnown=(fib->fib_Date.ds_Days || fib->fib_Date.ds_Minute || fib->fib_Date.ds_Tick) &&
        fib->fib_Date.ds_Days>=0 && fib->fib_Date.ds_Minute>=0 && fib->fib_Date.ds_Minute<1440 &&
        fib->fib_Date.ds_Tick>=0 && fib->fib_Date.ds_Tick<3000;
    free(fib);UnLock(lock);return 1;
}
