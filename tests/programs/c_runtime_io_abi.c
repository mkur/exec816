/* SPDX-License-Identifier: MIT: focused hook encoding and native error width. */
#include "internal.h"
#include <proto/exec.h>
#include <proto/dos.h>
#include <exec816/runtime.h>
#include <calypsi/stubs.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <fcntl.h>
static int executions,failClose;
static BPTR nativeHandle;
APTR ExecCRTTestAllocMem(ULONG bytes,ULONG flags) { return AllocMem(bytes,flags); }
BPTR ExecCRTTestOpen(const char *path,LONG mode)
{ nativeHandle=Open(path,mode);return nativeHandle; }
LONG ExecCRTTestRead(BPTR fd,void *data,LONG bytes) { return Read(fd,data,bytes); }
LONG ExecCRTTestWrite(BPTR fd,const void *data,LONG bytes) { return Write(fd,data,bytes); }
LONG ExecCRTTestClose(BPTR fd)
{
    LONG result=Close(fd);
    if (failClose) { failClose=0;SetIoErr(0x0000c219L);return 0; }
    return result;
}
int main(void)
{
    int fd;
    char byte;
    ExecCRuntimeHeapRelease();
    ExecCRuntimeHeapBegin();ExecCRuntimeFilesBegin();ExecCRuntimeStdioBegin();ExecCRuntimeLibraryBegin();
    if ((int)_Stub_read(-1,&byte,1)!=-EBADF || (int)_Stub_write(-1,&byte,1)!=-EBADF) return 1;
    fd=_Stub_open("NIL:",O_WRONLY|O_CREAT|O_TRUNC);
    if (fd!=3 || !((ULONG)nativeHandle>>16)) return 2;
    failClose=1;
    if (_Stub_close(fd)!=-EIO || IoErr()!=0x0000c219L ||
        ExecCRuntimeFileError()!=0x0000c219L || ExecCRuntimeFileCount()) return 3;
    if (ExecCRuntimeStdioFinish(0)) return 4;
    ExecCRuntimeHeapRelease();
    return -321-executions++;
}
