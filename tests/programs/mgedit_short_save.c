/* SPDX-License-Identifier: MIT */
#include <proto/dos.h>

volatile UWORD shortSave;

BPTR ExecCRTTestOpen(const char *path,LONG mode) { return Open(path,mode); }
LONG ExecCRTTestRead(BPTR file,void *buffer,LONG bytes) { return Read(file,buffer,bytes); }
LONG ExecCRTTestClose(BPTR file) { return Close(file); }

LONG ExecCRTTestWrite(BPTR file,const void *buffer,LONG bytes)
{
    LONG result;
    if (!shortSave) return Write(file,buffer,bytes);
    result=Write(file,buffer,bytes-1);
    SetIoErr(ERROR_DISK_FULL);
    shortSave=2;
    return result;
}
