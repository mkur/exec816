/* SPDX-License-Identifier: MIT
 * Extracted from the Exec816 QED adapter. Descriptors keep full native IDs.
 * Lists are private to one calling Task; standard native handles are borrowed.
 */
#include "internal.h"
#include <proto/dos.h>
#include <calypsi/stubs.h>
#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>

#ifdef EXEC_CRT_TEST
extern BPTR ExecCRTTestOpen(const char *,LONG);
extern LONG ExecCRTTestRead(BPTR,void *,LONG);
extern LONG ExecCRTTestWrite(BPTR,const void *,LONG);
extern LONG ExecCRTTestClose(BPTR);
#define NATIVE_OPEN ExecCRTTestOpen
#define NATIVE_READ ExecCRTTestRead
#define NATIVE_WRITE ExecCRTTestWrite
#define NATIVE_CLOSE ExecCRTTestClose
#else
#define NATIVE_OPEN Open
#define NATIVE_READ Read
#define NATIVE_WRITE Write
#define NATIVE_CLOSE Close
#endif

struct Descriptor { BPTR handle; LONG pending; UWORD flags; };
static struct Descriptor files[EXEC_CRT_STANDARD_FILES+EXEC_CRT_FILE_SLOTS];
static LONG firstError,lastError,lastCloseError;
static UWORD cleaning;

int ExecCRuntimeErrorCode(LONG native)
{
    switch (native) {
    case ERROR_NO_FREE_STORE:return ENOMEM;
    case ERROR_OBJECT_NOT_FOUND:case ERROR_DIR_NOT_FOUND:return ENOENT;
    case ERROR_OBJECT_IN_USE:return EBUSY;
    case ERROR_OBJECT_EXISTS:return EEXIST;
    case ERROR_OBJECT_WRONG_TYPE:return EISDIR;
    case ERROR_DISK_WRITE_PROTECTED:return EROFS;
    case ERROR_WRITE_PROTECTED:case ERROR_DELETE_PROTECTED:return EACCES;
    case ERROR_RENAME_ACROSS_DEVICES:return EXDEV;
    case ERROR_DIR_NOT_EMPTY:return ENOTEMPTY;
    case ERROR_DISK_FULL:return ENOSPC;
    case ERROR_SEEK_ERROR:case ERROR_BAD_ARGUMENTS:return EINVAL;
    case ERROR_BAD_NUMBER:return EBADF;
    case ERROR_ACTION_NOT_KNOWN:return ENOSYS;
    case ERROR_BREAK:return EINTR;
    case ERROR_BROKEN_PIPE:return EPIPE;
    case ERROR_NO_MORE_ENTRIES:return EMFILE;
    default:return EIO;
    }
}
LONG ExecCRuntimeFail(LONG native)
{
    if (!native) native=ERROR_BAD_STREAM_NAME;
    lastError=native;
    if (cleaning && !firstError) firstError=native;
    SetIoErr(native);errno=ExecCRuntimeErrorCode(native);
    return -errno;
}
LONG ExecCRuntimeFileError(void) { return lastError; }
LONG ExecCRuntimeCloseError(void) { return lastCloseError; }
UWORD ExecCRuntimeFileCount(void)
{
    UWORD index,count=0;
    for (index=3;index<3+EXEC_CRT_FILE_SLOTS;++index) if (files[index].handle) ++count;
    return count;
}
void ExecCRuntimeFilesBegin(void)
{
    memset(files,0,sizeof(files));
    firstError=lastError=lastCloseError=0;cleaning=0;
    files[0].handle=Input();files[0].flags=O_RDONLY;
    files[1].handle=files[2].handle=Output();
    files[1].flags=files[2].flags=O_WRONLY;
}
static struct Descriptor *descriptor(int fd)
{
    return fd>=0 && fd<3+EXEC_CRT_FILE_SLOTS && files[fd].handle ? files+fd:NULL;
}
void ExecCRuntimeAcknowledge(int fd)
{
    struct Descriptor *file=descriptor(fd);
    if (file) file->pending=0;
}

int _Stub_open(const char *path,int flags,...)
{
    BPTR native;
    LONG mode;
    int index,access=flags&O_ACCMODE;
    if (flags&~(O_ACCMODE|O_CREAT|O_TRUNC|O_EXCL|O_APPEND|O_BINARY))
        return ExecCRuntimeFail(ERROR_ACTION_NOT_KNOWN);
    if (!access || ((flags&O_EXCL) && !(flags&O_CREAT)) ||
        ((flags&(O_TRUNC|O_APPEND)) && !(access&O_WRONLY)))
        return ExecCRuntimeFail(ERROR_BAD_ARGUMENTS);
    if ((flags&(O_CREAT|O_EXCL))==(O_CREAT|O_EXCL)) mode=MODE_CREATE_EXCLUSIVE;
    else if (flags&O_TRUNC) {
        if (!(flags&O_CREAT)) return ExecCRuntimeFail(ERROR_ACTION_NOT_KNOWN);
        mode=MODE_NEWFILE;
    } else if (flags&O_CREAT) mode=MODE_READWRITE;
    else mode=access&O_WRONLY ? MODE_UPDATE_EXISTING:MODE_OLDFILE;
    /* Reserve capacity before Open can create or truncate anything. */
    for (index=3;index<3+EXEC_CRT_FILE_SLOTS && files[index].handle;++index) {}
    if (index==3+EXEC_CRT_FILE_SLOTS) return ExecCRuntimeFail(ERROR_NO_MORE_ENTRIES);
    native=NATIVE_OPEN(path,mode);
    if (!native) return ExecCRuntimeFail(IoErr());
    files[index].handle=native;files[index].pending=0;files[index].flags=flags;
    return index;
}
int _Stub_close(int fd)
{
    struct Descriptor *file;
    BPTR native;
    if (fd>=0 && fd<3) { files[fd].handle=0;return 0; }
    file=descriptor(fd);
    if (!file) return ExecCRuntimeFail(ERROR_BAD_NUMBER);
    lastCloseError=0;native=file->handle;
    /* Terminal Close consumes the identity on either outcome. A previously
     * delivered transfer error is not a new cleanup failure. */
    file->handle=0;file->pending=0;file->flags=0;
    if (!NATIVE_CLOSE(native)) {
        lastCloseError=IoErr();return ExecCRuntimeFail(lastCloseError);
    }
    return 0;
}
long _Stub_lseek(int fd,long offset,int origin)
{
    struct Descriptor *file=descriptor(fd);
    LONG mode,old;
    if (!file) return ExecCRuntimeFail(ERROR_BAD_NUMBER);
    if (origin==SEEK_SET) mode=OFFSET_BEGINNING;
    else if (origin==SEEK_CUR) mode=OFFSET_CURRENT;
    else if (origin==SEEK_END) mode=OFFSET_END;
    else return ExecCRuntimeFail(ERROR_BAD_ARGUMENTS);
    old=Seek(file->handle,offset,mode);
    if (old<0) return ExecCRuntimeFail(IoErr());
    file->pending=0;
    if (origin==SEEK_SET) return offset;
    if (origin==SEEK_CUR) return old+offset;
    old=Seek(file->handle,0,OFFSET_CURRENT);
    return old<0 ? ExecCRuntimeFail(IoErr()):old;
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
static LONG transfer(int fd,void *buffer,LONG bytes,int writing)
{
    struct Descriptor *file=descriptor(fd);
    LONG result,error;
    if (!file || !(file->flags&(writing ? O_WRONLY:O_RDONLY)))
        return ExecCRuntimeFail(ERROR_BAD_NUMBER);
    if (bytes<0) return ExecCRuntimeFail(ERROR_BAD_ARGUMENTS);
    if (!bytes) return 0;
    if (file->pending) {
        error=file->pending;file->pending=0;
        return ExecCRuntimeFail(error);
    }
    if (writing && (file->flags&O_APPEND) && _Stub_lseek(fd,0,SEEK_END)<0)
        return -errno;
    result=writing ? NATIVE_WRITE(file->handle,buffer,bytes):NATIVE_READ(file->handle,buffer,bytes);
    error=IoErr();
    if (result<0 || error || (writing && !result)) {
        if (!error) error=writing ? ERROR_DISK_FULL:ERROR_BAD_STREAM_NAME;
        ExecCRuntimeFail(error);ExecCRuntimeStreamError(fd);
        if (result>0) { file->pending=error;return result; }
        return -errno;
    }
    return result;
}
LONG ExecCRuntimeRead(int fd,void *buffer,LONG bytes) { return transfer(fd,buffer,bytes,0); }
LONG ExecCRuntimeWrite(int fd,const void *buffer,LONG bytes) { return transfer(fd,(void *)buffer,bytes,1); }
size_t _Stub_read(int fd,void *buffer,size_t bytes)
{ return (size_t)ExecCRuntimeRead(fd,buffer,bytes>32767U ? 32767L:(LONG)bytes); }
size_t _Stub_write(int fd,const void *buffer,size_t bytes)
{ return (size_t)ExecCRuntimeWrite(fd,buffer,bytes>32767U ? 32767L:(LONG)bytes); }
int _Stub_rename(const char *before,const char *after)
{ return Rename(before,after) ? 0:ExecCRuntimeFail(IoErr()); }
int _Stub_remove(const char *path)
{ return DeleteFile(path) ? 0:ExecCRuntimeFail(IoErr()); }

void ExecCRuntimeFilesCleaning(void) { firstError=0;cleaning=1; }
LONG ExecCRuntimeFilesFinish(void)
{
    int index;
    for (index=3;index<3+EXEC_CRT_FILE_SLOTS;++index)
        if (files[index].handle) _Stub_close(index);
    cleaning=0;return firstError;
}
