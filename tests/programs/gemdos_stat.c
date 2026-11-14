/* SPDX-License-Identifier: MIT. FSTAT composes the real owned file operation. */
#include <compat/gemdos.h>
#include <proto/dos.h>
#include <proto/exec.h>
#include "internal.h"
#include <string.h>
#include <errno.h>

static WORD executions,budget=-1,malformed;
static LONG readLimit=-1;
static XATTR info,before;
APTR ExecCRTTestAllocMem(ULONG bytes,ULONG flags)
{
    if (!budget) return NULL;
    if (budget>0) --budget;
    return AllocMem(bytes,flags);
}
BPTR ExecCRTTestOpen(const char *path,LONG mode) { return Open(path,mode); }
LONG ExecCRTTestClose(BPTR file) { return Close(file); }
LONG ExecCRTTestWrite(BPTR file,const void *buffer,LONG bytes)
{ return Write(file,buffer,bytes); }
LONG ExecCRTTestRead(BPTR file,void *buffer,LONG bytes)
{
    LONG result;
    if (readLimit<0) return Read(file,buffer,bytes);
    result=Read(file,buffer,readLimit);readLimit=-1;
    if (result>=0) SetIoErr(0x0000c219L);
    return result;
}
LONG EXEC_CALL ExecCRTTestExamineFH(BPTR file,struct FileInfoBlock *fib)
{
    LONG result=ExamineFH(file,fib);
    if (result) {
        if (malformed==1) fib->fib_InfoFlags=FIB_SIZE_BOUND;
        if (malformed==2) fib->fib_Size=-1;
        if (malformed==3) fib->fib_DirEntryType=ST_USERDIR;
    }
    return result;
}
static LONG stat(WORD fd) { return Fcntl(fd,(LONG)&info,FSTAT); }
static void poison(void)
{ memset(&info,0xa5,sizeof(info));memcpy(&before,&info,sizeof(info)); }

int main(void)
{
    WORD fd,kind;
    unsigned char bytes[8];
    XATTR expected;
    fd=(WORD)Fopen("SYS:FHDATA.DAT",0);
    if (fd<3) return 101;
    memset(&expected,0,sizeof(expected));
    expected.size=513;expected.mode=GEMDOS_S_IFREG;
    poison();
    if (stat(fd) || memcmp(&info,&expected,sizeof(info)) || Fseek(0,fd,1)!=0) return 102;
#ifndef GEMDOS_ABI_ONLY
    if (Fseek(7,fd,0)!=7 || stat(fd) || Fseek(0,fd,1)!=7) return 103;
    readLimit=2;
    if (Fread(fd,8,bytes)!=2 || stat(fd) || Fread(fd,8,bytes)!=-1 ||
        IoErr()!=0x0000c219L || Fread(fd,1,bytes)!=1 || bytes[0]!=9) return 104;
    poison();budget=0;
    if (stat(fd)!=GEMDOS_ENSMEM || IoErr()!=ERROR_NO_FREE_STORE ||
        memcmp(&info,&before,sizeof(info))) return 105;
    budget=-1;
    for (kind=1;kind<=3;++kind) {
        malformed=kind;poison();
        if (stat(fd)!=GEMDOS_EINVFN || memcmp(&info,&before,sizeof(info)) ||
            Fseek(0,fd,1)!=10) return 106;
    }
    malformed=0;poison();
    if (Fcntl(fd,(LONG)&info,0)!=GEMDOS_EINVFN ||
        memcmp(&info,&before,sizeof(info)) || Fclose(fd)) return 107;
    if (stat(fd)!=GEMDOS_EBADF || memcmp(&info,&before,sizeof(info))) return 108;
    fd=(WORD)Fopen("NIL:",0);
    if (fd<3 || stat(fd)!=GEMDOS_EINVFN || memcmp(&info,&before,sizeof(info)) || Fclose(fd)) return 109;
    fd=(WORD)Fopen("SYS:EMPTY.DAT",0);
    expected.size=0;
    if (fd<3 || stat(fd) || memcmp(&info,&expected,sizeof(info)) || Fclose(fd)) return 110;
    if (stat(0) || info.size!=513 || Fseek(0,0,1)!=11) return 111;
#else
    if (Fclose(fd)) return 112;
#endif
    ++executions;SetIoErr(0);
    return -320-executions;
}
