/* SPDX-License-Identifier: MIT
 * Descriptors own full native identities; standard streams borrow Output().
 */
#include "qed-files.h"
#include <calypsi/stubs.h>
#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>

struct Descriptor { BPTR handle; UWORD append; LONG causal; };
static struct Descriptor files[QED_FILE_SLOTS];
static LONG firstError,lastError,lastCloseError;
static UBYTE cleaning;
/* This initializer belongs to the pinned Calypsi runtime (streamlist.c). */
extern void __call_initialize_global_streams(void);

static int error_code(LONG native)
{
    switch (native) {
    case ERROR_NO_FREE_STORE: return ENOMEM;
    case ERROR_OBJECT_NOT_FOUND: case ERROR_DIR_NOT_FOUND: return ENOENT;
    case ERROR_OBJECT_IN_USE: return EBUSY;
    case ERROR_OBJECT_EXISTS: return EEXIST;
    case ERROR_OBJECT_WRONG_TYPE: return EISDIR;
    case ERROR_DISK_WRITE_PROTECTED: return EROFS;
    case ERROR_WRITE_PROTECTED: case ERROR_DELETE_PROTECTED: return EACCES;
    case ERROR_RENAME_ACROSS_DEVICES: return EXDEV;
    case ERROR_DIR_NOT_EMPTY: return ENOTEMPTY;
    case ERROR_DISK_FULL: return ENOSPC;
    case ERROR_SEEK_ERROR: case ERROR_BAD_ARGUMENTS: return EINVAL;
    case ERROR_BAD_NUMBER: return EBADF;
    case ERROR_ACTION_NOT_KNOWN: return ENOSYS;
    case ERROR_BREAK: return EINTR;
    case ERROR_NO_MORE_ENTRIES: return EMFILE;
    default: return EIO;
    }
}
static LONG fail(LONG native)
{
    lastError=native;
    if (cleaning && !firstError) firstError=native;
    SetIoErr(native);
    return -error_code(native);
}
static LONG gem_error(LONG result)
{
    if (result>=0) return result;
    switch (error_code(lastError)) {
    case ENOENT: return -33;
    case EMFILE: return -35;
    case EBADF: return -37;
    case ENOMEM: return -39;
    case ENOSYS: return -32;
    case EINVAL: return -64;
    case EACCES: case EROFS: case EBUSY: case EEXIST: return -36;
    default: return -1;
    }
}
static BPTR handle(int fd)
{
    if (fd==1 || fd==2) return Output();
    if (fd>=3 && fd<3+QED_FILE_SLOTS) return files[fd-3].handle;
    return 0;
}
static int opened(const char *path,LONG mode,int append)
{
    BPTR native;
    int index;
    /* Admit the descriptor before a mode that may create a filesystem object. */
    for(index=0;index<QED_FILE_SLOTS && files[index].handle;index++){}
    if(index==QED_FILE_SLOTS)return fail(ERROR_NO_MORE_ENTRIES);
    native=Open(path,mode);
    if(!native)return fail(IoErr());
    files[index].handle=native;files[index].append=append;files[index].causal=0;
    return index+3;
}

int _Stub_open(const char *path,int flags,...)
{
    LONG mode;
    if (flags&~(O_ACCMODE|O_CREAT|O_TRUNC|O_EXCL|O_APPEND|O_BINARY))
        return fail(ERROR_ACTION_NOT_KNOWN);
    if ((flags&O_ACCMODE)==O_RDONLY && !(flags&(O_CREAT|O_TRUNC|O_APPEND))) mode=MODE_OLDFILE;
    else if (flags&O_WRONLY) {
        if ((flags&(O_CREAT|O_EXCL))==(O_CREAT|O_EXCL)) mode=MODE_CREATE_EXCLUSIVE;
        else if ((flags&(O_CREAT|O_TRUNC))==(O_CREAT|O_TRUNC)) mode=MODE_NEWFILE;
        else if (flags&O_TRUNC) return fail(ERROR_ACTION_NOT_KNOWN);
        else mode=(flags&O_CREAT) ? MODE_READWRITE:MODE_UPDATE_EXISTING;
    } else return fail(ERROR_BAD_ARGUMENTS);
    return opened(path,mode,flags&O_APPEND);
}
int _Stub_close(int fd)
{
    BPTR native;
    LONG causal;
    if (fd>=0 && fd<=2) return 0;
    lastCloseError=0;native=handle(fd);
    if (!native) return fail(ERROR_BAD_NUMBER);
    /* Idle terminal Close consumes the native identity on either result. */
    causal=files[fd-3].causal;
    files[fd-3].handle=0;files[fd-3].append=0;files[fd-3].causal=0;
    if (!Close(native)) {
        lastCloseError=IoErr();return fail(causal ? causal:lastCloseError);
    }
    if (causal) SetIoErr(causal);
    return 0;
}
long _Stub_lseek(int fd,long offset,int origin)
{
    BPTR native=handle(fd);
    LONG mode,old;
    if (!native) return fail(ERROR_BAD_NUMBER);
    if (origin==SEEK_SET) mode=OFFSET_BEGINNING;
    else if (origin==SEEK_CUR) mode=OFFSET_CURRENT;
    else if (origin==SEEK_END) mode=OFFSET_END;
    else return fail(ERROR_BAD_ARGUMENTS);
    old=Seek(native,offset,mode);
    if (old<0) return fail(IoErr());
    if (origin==SEEK_SET) return offset;
    if (origin==SEEK_CUR) return old+offset;
    old=Seek(native,0,OFFSET_CURRENT);
    return old<0 ? fail(IoErr()):old;
}
int _Stub_fgetpos(int fd,fpos_t *position)
{
    LONG value=_Stub_lseek(fd,0,SEEK_CUR);
    if (value<0) return value;
    *position=value;return 0;
}
int _Stub_fsetpos(int fd,const fpos_t *position)
{
    LONG value=_Stub_lseek(fd,*position,SEEK_SET);
    return value<0 ? value:0;
}
static LONG read_native(int fd,void *buffer,LONG bytes)
{
    BPTR native=handle(fd);
    LONG result,error;
    if (!native) return fail(fd==0 ? ERROR_ACTION_NOT_KNOWN:ERROR_BAD_NUMBER);
    if (bytes<0) return fail(ERROR_BAD_ARGUMENTS);
    result=Read(native,buffer,(LONG)bytes);error=IoErr();
    if (fd>=3) files[fd-3].causal=error;
    if (result<0) return fail(error);
    if (error) fail(error);
    return result;
}
static LONG write_native(int fd,const void *buffer,LONG bytes)
{
    BPTR native=handle(fd);
    LONG result,error;
    if (!native) return fail(ERROR_BAD_NUMBER);
    if (bytes<0) return fail(ERROR_BAD_ARGUMENTS);
    if (fd>=3 && files[fd-3].append && _Stub_lseek(fd,0,SEEK_END)<0)
        return -error_code(lastError);
    result=Write(native,buffer,(LONG)bytes);error=IoErr();
    if (fd>=3) files[fd-3].causal=error;
    if (result<0) return fail(error);
    if (error) fail(error);
    return result;
}
size_t _Stub_read(int fd,void *buffer,size_t bytes)
{ return (size_t)read_native(fd,buffer,bytes>32767U ? 32767L:(LONG)bytes); }
size_t _Stub_write(int fd,const void *buffer,size_t bytes)
{ return (size_t)write_native(fd,buffer,bytes>32767U ? 32767L:(LONG)bytes); }
int _Stub_rename(const char *before,const char *after)
{ return Rename(before,after) ? 0:fail(IoErr()); }
int _Stub_remove(const char *path)
{ return DeleteFile(path) ? 0:fail(IoErr()); }
LONG Fopen(const char *path,WORD mode)
{
    if (mode<0 || mode>2) return gem_error(fail(ERROR_ACTION_NOT_KNOWN));
    return gem_error(opened(path,mode ? MODE_UPDATE_EXISTING:MODE_OLDFILE,0));
}
LONG Fcreate(const char *path,WORD attributes)
{ return attributes ? gem_error(fail(ERROR_ACTION_NOT_KNOWN)):gem_error(opened(path,MODE_NEWFILE,0)); }
LONG QedFileExclusive(const char *path)
{ return gem_error(opened(path,MODE_CREATE_EXCLUSIVE,0)); }
LONG QedFileCloseError(void) { return lastCloseError; }
LONG Fclose(WORD fd) { return gem_error(_Stub_close(fd)); }
LONG Fread(WORD fd,LONG bytes,void *buffer)
{ return bytes<0 ? gem_error(fail(ERROR_BAD_ARGUMENTS)):gem_error(read_native(fd,buffer,bytes)); }
LONG Fwrite(WORD fd,LONG bytes,const void *buffer)
{ return bytes<0 ? gem_error(fail(ERROR_BAD_ARGUMENTS)):gem_error(write_native(fd,buffer,bytes)); }
LONG Fseek(LONG offset,WORD fd,WORD origin)
{ return gem_error(_Stub_lseek(fd,offset,origin)); }
LONG Fdelete(const char *path) { return gem_error(_Stub_remove(path)); }
LONG Frename(WORD zero,const char *before,const char *after)
{ return zero ? gem_error(fail(ERROR_BAD_ARGUMENTS)):gem_error(_Stub_rename(before,after)); }
LONG QedFileError(void) { return lastError; }
UWORD QedFileCount(void)
{
    UWORD index,count=0;
    for (index=0;index<QED_FILE_SLOTS;++index) if (files[index].handle) ++count;
    return count;
}
void QedFilesBegin(void)
{
    firstError=lastError=lastCloseError=0;
    if (!stdout) __call_initialize_global_streams();
}
LONG QedFilesCleanup(LONG cause)
{
    int index;
    firstError=cause;cleaning=1;
    /* fclose removes/free its stream even after a flush or terminal Close error. */
    while (__global_streams.sl_head) fclose(__global_streams.sl_head);
    fflush(stdout);fflush(stderr);
    for (index=0;index<QED_FILE_SLOTS;++index) if (files[index].handle) _Stub_close(index+3);
    cleaning=0;SetIoErr(firstError);
    return firstError;
}
int QedFileInfo(const char *path,struct QedFileInfo *info)
{
    BPTR lock=Lock(path,SHARED_LOCK);
    struct FileInfoBlock *fib;
    LONG error;
    if (!lock) { fail(IoErr());return 0; }
    fib=malloc(sizeof(*fib));
    if (!fib) { UnLock(lock);fail(ERROR_NO_FREE_STORE);return 0; }
    if (!ExamineExact(lock,fib)) {
        error=IoErr();free(fib);UnLock(lock);fail(error);return 0;
    }
    info->size=fib->fib_Size;info->protection=fib->fib_Protection;
    info->kind=fib->fib_DirEntryType;info->date=fib->fib_Date;
    info->sizeKnown=(fib->fib_InfoFlags&FIB_SIZE_EXACT)!=0;
    info->dateKnown=(fib->fib_Date.ds_Days || fib->fib_Date.ds_Minute || fib->fib_Date.ds_Tick) &&
        fib->fib_Date.ds_Days>=0 && fib->fib_Date.ds_Minute>=0 && fib->fib_Date.ds_Minute<1440 &&
        fib->fib_Date.ds_Tick>=0 && fib->fib_Date.ds_Tick<3000;
    free(fib);UnLock(lock);return 1;
}
