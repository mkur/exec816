/* SPDX-License-Identifier: MIT. Emitted tests use real native operations;
 * injection changes one transfer/finalization result at the adapter boundary. */
#include "internal.h"
#include <calypsi/stubs.h>
#include <exec816/runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#include <proto/dos.h>
#include "libc.h"

static int budget=-1,closeFailure,executions,firstRand;
static LONG readLimit=-1,writeLimit=-1;
static UWORD opens,closes;
static BPTR lastHandle,lastWrite;
static unsigned char buffer[32],big[700];
static const unsigned char bytes[10]={'a',128,255,13,10,155,0,'c',10,13};
static char token[]="first,second";
APTR ExecCRTTestAllocMem(ULONG size,ULONG flags)
{
    APTR p;
    if (!budget) return NULL;
    if (budget>0) --budget;
    p=AllocMem(size,flags);
    if (p) memset(p,0xa5,(size_t)size);
    return p;
}
BPTR ExecCRTTestOpen(const char *path,LONG mode)
{ ++opens;lastHandle=Open(path,mode);return lastHandle; }
LONG ExecCRTTestClose(BPTR fd)
{
    LONG result=Close(fd);
    ++closes;
    if (result && closeFailure) {
        SetIoErr(closeFailure--==2 ? 0x0000c219L:ERROR_DISK_FULL);return 0;
    }
    return result;
}
LONG ExecCRTTestRead(BPTR fd,void *data,LONG count)
{
    LONG result;
    if (readLimit>=0 && count>readLimit) {
        if (!readLimit) { readLimit=-1;SetIoErr(0x0000c219L);return -1; }
        result=Read(fd,data,readLimit);readLimit=-1;
        if (result>=0) SetIoErr(0x0000c219L);
        return result;
    }
    return Read(fd,data,count);
}
LONG ExecCRTTestWrite(BPTR fd,const void *data,LONG count)
{
    LONG result;
    lastWrite=fd;
    if (writeLimit>=0 && count>writeLimit) {
        if (!writeLimit) { SetIoErr(ERROR_DISK_FULL);return -1; }
        result=Write(fd,data,writeLimit);writeLimit=0;
        if (result>=0) SetIoErr(ERROR_DISK_FULL);
        return result;
    }
    return Write(fd,data,count);
}
static int roundtrip(const char *path)
{
    FILE *stream,*other;
    fpos_t position;
    int fd,n;
    stream=fopen(path,"w+b");
    if (!stream || !((ULONG)lastHandle>>16) || fwrite(bytes,1,10,stream)!=10 || fflush(stream) ||
        fseek(stream,3,SEEK_SET) || fgetpos(stream,&position) || position!=3 ||
        fread(buffer,1,2,stream)!=2 || memcmp(buffer,bytes+3,2) ||
        fsetpos(stream,&position) || ftell(stream)!=3 || fclose(stream)) return 1;
    stream=fopen(path,"r+b");
    if (!stream || fread(buffer,1,1,stream)!=1 || buffer[0]!='a' ||
        fseek(stream,0,SEEK_SET) || fwrite("z",1,1,stream)!=1 || fclose(stream)) return 2;
    stream=fopen(path,"a+b");
    if (!stream || fseek(stream,0,SEEK_SET) || fread(buffer,1,1,stream)!=1 || buffer[0]!='z' ||
        fseek(stream,0,SEEK_SET) || fwrite("!",1,1,stream)!=1 || fclose(stream)) return 3;
    stream=fopen(path,"rb");
    if (!stream || fread(buffer,1,32,stream)!=11 || buffer[0]!='z' || buffer[10]!='!' ||
        memcmp(buffer+1,bytes+1,9) || !feof(stream) || ferror(stream)) return 4;
    clearerr(stream);
    if (feof(stream) || fseek(stream,1000,SEEK_SET)!=-1 || errno!=EINVAL || fclose(stream)) return 5;
    if ((fd=_Stub_open(path,O_WRONLY|O_CREAT|O_EXCL))!=-EEXIST || errno!=EEXIST ||
        fopen(path,"wbx") || errno!=EEXIST) return 6;
    for (n=0;n<2;++n) {
        UWORD before=closes;
        budget=n;other=fopen("NIL:","wb");budget=-1;
        if (other || errno!=ENOMEM || closes!=before+1 || ExecCRuntimeFileCount() ||
            __global_streams.sl_head || __global_streams.sl_tail) return 7+n;
    }
    if (remove(path)) return 9;
    stream=fopen(path,"w+bx");
    if (!stream || fwrite(bytes,1,10,stream)!=10 || fseek(stream,0,SEEK_SET) ||
        fread(buffer,1,10,stream)!=10 || memcmp(buffer,bytes,10) || fclose(stream) || remove(path)) return 35;
    return 0;
}
static int integer_format(const char *path)
{
    FILE *stream=fopen(path,"wb");
    if (!stream || fprintf(stream,"%ld,%u,%x",123456789L,65535U,0xabcdU)!=20 || fclose(stream)) return 1;
    stream=fopen(path,"rb");
    if (!stream || fread(buffer,1,32,stream)!=20 || memcmp(buffer,"123456789,65535,abcd",20) ||
        fclose(stream) || remove(path)) return 2;
    return 0;
}

static int failures(const char *path)
{
    FILE *stream;
    int fd,n,descriptors[EXEC_CRT_FILE_SLOTS];
    UWORD before;
    for (n=0;n<EXEC_CRT_FILE_SLOTS;++n) {
        descriptors[n]=_Stub_open("NIL:",O_WRONLY|O_CREAT|O_TRUNC);
        if (descriptors[n]!=3+n) return 10;
    }
    before=opens;
    if (_Stub_open(path,O_WRONLY|O_CREAT|O_TRUNC)!=-EMFILE || errno!=EMFILE || opens!=before) return 11;
    for (n=0;n<EXEC_CRT_FILE_SLOTS;++n) if (_Stub_close(descriptors[n])) return 12;
    /* Exhaustion did not admit Open/create; the name must still be absent. */
    if (Open(path,MODE_OLDFILE) || IoErr()!=ERROR_OBJECT_NOT_FOUND) return 13;
    stream=fopen(path,"wb");
    if (!stream || fwrite(bytes,1,10,stream)!=10) return 14;
    writeLimit=3;
    if (fflush(stream)!=EOF || errno!=ENOSPC || !ferror(stream)) return 15;
    writeLimit=-1;clearerr(stream);
    if (fflush(stream) || fclose(stream)) return 16;
    stream=fopen(path,"rb");
    if (!stream || fread(buffer,1,32,stream)!=10 || memcmp(buffer,bytes,10) || fclose(stream)) return 17;
    stream=fopen(path,"wb");
    if (!stream) return 29;
    memset(big,0x9b,sizeof(big));writeLimit=3;
    n=fwrite(big,1,sizeof(big),stream);
    if (n<=3 || n>=sizeof(big) || errno!=ENOSPC || !ferror(stream)) return 30;
    writeLimit=-1;clearerr(stream);
    if (fwrite(big+n,1,sizeof(big)-n,stream)!=sizeof(big)-n || fclose(stream)) return 31;
    stream=fopen(path,"rb");
    if (!stream || fread(big,1,sizeof(big),stream)!=sizeof(big) || fclose(stream)) return 32;
    for (n=0;n<sizeof(big);++n) if (big[n]!=0x9b) return 33;
    stream=fopen(path,"wb");
    if (!stream || fwrite(bytes,1,10,stream)!=10 || fclose(stream)) return 34;
    stream=fopen(path,"rb");readLimit=0;
    if (!stream || fread(buffer,1,10,stream) || errno!=EIO || !ferror(stream) || feof(stream) ||
        IoErr()!=0x0000c219L) return 18;
    clearerr(stream);
    if (fread(buffer,1,10,stream)!=10 || memcmp(buffer,bytes,10) || fclose(stream)) return 19;
    stream=fopen(path,"rb");readLimit=3;
    if (!stream || fread(buffer,1,10,stream)!=3 || errno!=EIO || !ferror(stream) || feof(stream) ||
        memcmp(buffer,bytes,3)) return 20;
    clearerr(stream);
    if (fread(buffer,1,7,stream)!=7 || memcmp(buffer,bytes+3,7) || fclose(stream)) return 21;
    stream=fopen(path,"wb");
    if (!stream || setvbuf(stream,NULL,_IONBF,0)) return 22;
    writeLimit=3;
    if (fwrite(bytes,1,10,stream)!=3 || errno!=ENOSPC || !ferror(stream)) return 23;
    writeLimit=-1;clearerr(stream);
    if (fclose(stream)) return 24;
    stream=fopen(path,"wb");fd=stream ? stream->fs_fd:-1;
    if (!stream || fwrite(bytes,1,10,stream)!=10) return 25;
    before=closes;closeFailure=1;
    if (fclose(stream)!=EOF || errno!=ENOSPC || closes!=before+1 || ExecCRuntimeFileCount()) return 26;
    if (_Stub_close(fd)!=-EBADF || closes!=before+1) return 27;
    if (remove(path)) return 28;
    return 0;
}
static int wide_transfer(const char *path)
{
    unsigned char *one=malloc(40000U),*two=malloc(40000U);
    FILE *stream;
    unsigned int i;
    if (!one || !two) return 1;
    for (i=0;i<40000U;++i) one[i]=(unsigned char)(i^(i>>8));
    stream=fopen(path,"wb");
    if (!stream || fwrite(one,2,20000U,stream)!=20000U || fclose(stream)) return 2;
    stream=fopen(path,"rb");
    if (!stream || fread(two,2,20000U,stream)!=20000U || memcmp(one,two,40000U) || fclose(stream)) return 3;
    stream=fopen(path,"wb");
    errno=91;
    if (!stream || fwrite(one,0,65535U,stream) || errno!=91 ||
        fwrite(one,65535U,2,stream) || errno!=EOVERFLOW || !ferror(stream)) return 4;
    clearerr(stream);
    if (fclose(stream) || remove(path)) return 5;
    free(one);free(two);
    return 0;
}

int main(void)
{
    char path[16]="RAM:CRT00.DAT";
    const char hex[]="0123456789ABCDEF";
    ULONG bank=(ULONG)&executions>>16;
    int result,n;
    FILE *stream;
    struct ExecCRuntimeHeapStats stats;
    ++executions;
    ExecCRuntimeHeapSnapshot(&stats);
    if (stats.blocks!=1 || errno || __global_streams.sl_head) return 101;
    ExecCRuntimeHeapRelease();
    ExecCRuntimeHeapBegin();ExecCRuntimeFilesBegin();
    memset(stdin,0xa5,sizeof(FILE));memset(stdout,0xa5,sizeof(FILE));memset(stderr,0xa5,sizeof(FILE));
    ExecCRuntimeStdioBegin();ExecCRuntimeLibraryBegin();
    n=rand();
    if (executions==1) firstRand=n;
    if (errno || n!=firstRand || strtok(NULL,",") || ferror(stdout) || feof(stdin)) return 102;
    for (n=0;n<128;++n) if (rand()<0) return 104;
    if (!strtok(token,",")) return 103;
    token[5]=',';
    path[7]=hex[bank>>4];path[8]=hex[bank&15];
    if ((result=integer_format(path))) return 210+result;
    if ((result=roundtrip(path))) return 110+result;
    path[0]='S';path[1]='Y';path[2]='S';
    if ((result=roundtrip(path))) return 130+result;
    path[0]='R';path[1]='A';path[2]='M';
    if ((result=failures(path))) return 150+result;
    if ((result=wide_transfer(path))) return 190+result;
    if (fprintf(stdout,"%s","") || fprintf(stderr,"%s","") || fread(buffer,1,1,stdin)) return 181;
    if ((int)_Stub_write(1," ",1)!=1 || lastWrite!=Output() ||
        (int)_Stub_write(2," ",1)!=1 || lastWrite!=Output()) return 186;
    if (_Stub_close(0) || _Stub_close(1) || _Stub_close(2) || Write(Output(),"",0)) return 182;
    path[0]='S';path[1]='Y';path[2]='S';
    stream=fopen(path,"wb");
    if (!stream || fwrite(bytes,1,10,stream)!=10 || fclose(stream)) return 187;
    /* Independent terminal failures continue cleanup and retain the first 32-bit cause. */
    if (!fopen("NIL:","wb") || !fopen("NIL:","wb")) return 183;
    closeFailure=2;
    if (ExecCRuntimeStdioFinish(0)!=0x0000c219L || closeFailure || ExecCRuntimeFileCount() ||
        __global_streams.sl_head || __global_streams.sl_tail) return 184;
    ExecCRuntimeHeapRelease();ExecCRuntimeHeapSnapshot(&stats);
    if (stats.blocks || stats.payload || stats.backing) return 185;
    errno=ERANGE;
    return -320-executions;
}
