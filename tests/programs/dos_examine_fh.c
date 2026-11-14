/* SPDX-License-Identifier: MIT. Public handle metadata and CRT composition. */
#include <compat/gemdos.h>
#include <proto/dos.h>
#include "internal.h"
#include <string.h>
#include <stdlib.h>

static WORD executions;
static struct FileInfoBlock *info;

static int query(WORD fd,LONG bytes,LONG position)
{
    if (ExecCRuntimeExamineFH(fd,info) || info->fib_Size!=bytes ||
        !(info->fib_InfoFlags&FIB_SIZE_EXACT) || info->fib_DirEntryType>=0 ||
        Fseek(0,fd,1)!=position) return 1;
    return 0;
}

int main(void)
{
    WORD fd,n;
    unsigned char bytes[16];
    struct FileInfoBlock *before;
    char path[16]="RAM:FHI00.DAT";
    static const char hex[]="0123456789ABCDEF";
    ULONG bank=(ULONG)&executions>>16;
    info=malloc(sizeof(*info));before=malloc(sizeof(*before));
    if (!info || !before) return 101;
    memset(info,0xa5,sizeof(*info));memcpy(before,info,sizeof(*info));
    fd=(WORD)Fopen("NIL:",0);
    if (fd<3 || ExecCRuntimeExamineFH(fd,info)>=0 ||
        IoErr()!=ERROR_ACTION_NOT_KNOWN || memcmp(info,before,sizeof(*info)) ||
        Fclose(fd)) return 102;
#ifdef GEMDOS_ABI_ONLY
    fd=(WORD)Fopen("SYS:FHDATA.DAT",0);
    if (fd<3 || query(fd,513,0) || Fclose(fd)) return 111;
    free(before);free(info);SetIoErr(0);return -320-++executions;
#else
    if (ExecCRuntimeExamineFH(-1,info)>=0 || IoErr()!=ERROR_BAD_NUMBER ||
        memcmp(info,before,sizeof(*info))) return 103;
    fd=(WORD)Fopen("SYS:FHDATA.DAT",0);
    if (fd<3 || query(fd,513,0) || Fseek(7,fd,0)!=7 || query(fd,513,7) ||
        Fread(fd,16,bytes)!=16) return 104;
    for (n=0;n<16;++n) if (bytes[n]!=(unsigned char)(n+7)) return 105;
    if (Fseek(513,fd,0)!=513 || query(fd,513,513) || Fclose(fd)) return 106;
    fd=(WORD)Fopen("SYS:EMPTY.DAT",0);
    if (fd<3 || query(fd,0,0) || Fclose(fd)) return 107;
    path[7]=hex[bank>>4];path[8]=hex[bank&15];
    fd=(WORD)Fcreate(path,0);
    if (fd<3 || query(fd,0,0) || Fwrite(fd,5,"abcde")!=5 ||
        query(fd,5,5) || Fclose(fd)) return 108;
    fd=(WORD)Fopen(path,0);
    if (fd<3 || Fseek(2,fd,0)!=2 || query(fd,5,2) ||
        Fread(fd,3,bytes)!=3 || memcmp(bytes,"cde",3) ||
        Fclose(fd) || Fdelete(path)) return 109;
    /* The parent and sibling hold inherited wrappers over this same cursor. */
    if (Seek(Input(),0,OFFSET_CURRENT)!=11 || !ExamineFH(Input(),info) ||
        info->fib_Size!=513 || Seek(Input(),0,OFFSET_CURRENT)!=11) return 110;
    free(before);free(info);
    ++executions;SetIoErr(0);
    return -320-executions;
#endif
}
