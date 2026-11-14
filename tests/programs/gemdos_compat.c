/* SPDX-License-Identifier: MIT. Real loaded-APP GEMDOS source calls. */
#include <compat/gemdos.h>
#include <exec816/c-runtime.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include "internal.h"
#include "gemdos-internal.h"
#include <string.h>
#include <errno.h>

static WORD executions;
static LONG readLimit=-1;
static WORD closeFailure;
static UWORD closes;

APTR ExecCRTTestAllocMem(ULONG bytes,ULONG flags) { return AllocMem(bytes,flags); }
BPTR ExecCRTTestOpen(const char *path,LONG mode) { return Open(path,mode); }
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
LONG ExecCRTTestClose(BPTR file)
{
    LONG result=Close(file);
    ++closes;
    if (result && closeFailure) {
        closeFailure=0;SetIoErr(ERROR_DISK_FULL);return 0;
    }
    return result;
}

static int file_calls(const char *path)
{
    WORD fd,n,handles[EXEC_CRT_FILE_SLOTS];
    UWORD before;
    unsigned char buffer[8];
    unsigned char *memory,*wide;
    LONG result;
    memory=AllocMem(131072UL,MEMF_UPPER|MEMF_LINEAR);
    if (!memory) return 1;
    wide=memory+65530UL;
    for (n=0;n<8;++n) buffer[n]=(unsigned char)(128+n);
    memset(wide,0x9b,40000U);
    fd=(WORD)Fcreate(path,0);
    if (fd<3 || Fwrite(fd,40000L,wide)!=40000L || Fclose(fd)) return 2;
    fd=(WORD)Fopen(path,2);
    if (fd<3 || Fseek(0,fd,0)!=0) return 2;
    memset(wide,0,40000U);
    if (Fread(fd,40000L,wide)!=40000L || Fread(fd,1,buffer)!=0) return 3;
    for (result=0;result<40000L;++result) if (wide[result]!=0x9b) return 4;
    if (Fseek(3,fd,0)!=3) return 5;
    readLimit=2;
    if (Fread(fd,8,buffer)!=2 || IoErr()!=0x0000c219L ||
        Fread(fd,8,buffer)!=-1 || IoErr()!=0x0000c219L ||
        Fread(fd,3,buffer)!=3) return 6;
    before=closes;closeFailure=1;
    if (Fclose(fd)!=-1 || IoErr()!=ERROR_DISK_FULL || closes!=before+1 ||
        Fclose(fd)!=GEMDOS_EBADF || closes!=before+1) return 7;
    for (n=0;n<EXEC_CRT_FILE_SLOTS;++n) {
        handles[n]=(WORD)Fopen("NIL:",0);
        if (handles[n]!=3+n) return 8;
    }
    if (Fcreate(path,0)!=GEMDOS_ENHNDL) return 9;
    for (n=0;n<EXEC_CRT_FILE_SLOTS;++n) if (Fclose(handles[n])) return 10;
    fd=(WORD)Fopen(path,2);
    if (fd<3 || Fseek(0,fd,2)!=40000L || Fclose(fd) || Fdelete(path)) return 11;
    FreeMem(memory,131072UL);
    return 0;
}

int main(void)
{
    void *memory;
    LONG largest;
    int result;
    char path[16]="RAM:GEM00.DAT";
    static const char hex[]="0123456789ABCDEF";
    ULONG bank=(ULONG)&executions>>16;
    largest=(LONG)Malloc(-1);
    memory=Malloc(largest);
    if (!memory || largest>65520L || largest<=0 || ((ULONG)memory&7) || Mfree(memory)) return 101;
    if (Malloc(65521L) || errno!=ENOMEM || IoErr()!=ERROR_NO_FREE_STORE ||
        Malloc(-2) || errno!=EINVAL || IoErr()!=ERROR_BAD_ARGUMENTS ||
        Malloc(0) || Mfree(NULL)) return 102;
    if (Fopen("NIL:",3)!=GEMDOS_EINVFN || Fclose(-1)!=GEMDOS_EBADF ||
        Frename(1,"NIL:","NIL:")!=GEMDOS_ERANGE) return 103;
#ifdef GEMDOS_ABI_ONLY
    Pterm(-321);
#else
    path[7]=hex[bank>>4];path[8]=hex[bank&15];
    result=file_calls(path);
    if (result) return 110+result;
    path[0]='S';path[1]='Y';path[2]='S';
    result=file_calls(path);
    if (result) return 130+result;
    if (Fopen("RAM:missing",0)!=GEMDOS_EFILNF ||
        ExecGemdosResult(ExecCRuntimeFail(ERROR_DIR_NOT_FOUND))!=GEMDOS_EPTHNF) return 151;
    if (!Malloc(37) || Fopen("NIL:",0)<3) return 152;
    ++executions;
    SetIoErr(0);
    Pterm(-320-executions);
#endif
    return 199;
}
