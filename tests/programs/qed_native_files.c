/* Emitted file/runtime checks. Failure hooks call real native operations. */
#include "qed-files.h"
#include <calypsi/stubs.h>
#include <exec816/program.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>

__attribute__((section("exec_layout"))) const UWORD FileLayout[]={
    sizeof(size_t),sizeof(fpos_t),sizeof(time_t),sizeof(BPTR)};
static int budget=-1,closeFailure;
static LONG writeLimit=-1;
static UWORD closes;
static unsigned char buffer[32];
static const unsigned char bytes[9]={'a',128,255,13,10,'b',0,'c',10};
APTR EXEC_CALL QedFixtureAlloc(ULONG size,ULONG flags)
{
    void *pointer;
    if (!budget) return NULL;
    if (budget>0) --budget;
    pointer=AllocMem(size,flags);
    if (pointer) memset(pointer,0xa5,(size_t)size);
    return pointer;
}
LONG EXEC_CALL QedFixtureClose(BPTR file)
{
    LONG result=Close(file);
    ++closes;
    if (result && closeFailure) {
        closeFailure=0;SetIoErr(ERROR_DISK_FULL);return 0;
    }
    return result;
}
LONG EXEC_CALL QedFixtureWrite(BPTR file,const void *data,LONG length)
{
    LONG result;
    if (writeLimit>=0 && length>writeLimit) {
        if (!writeLimit) { SetIoErr(ERROR_DISK_FULL);return -1; }
        result=Write(file,data,writeLimit);writeLimit=0;
        if (result>=0) SetIoErr(ERROR_DISK_FULL);
        return result;
    }
    return Write(file,data,length);
}
static int roundtrip(const char *path,const char *renamed)
{
    LONG fd;
    struct QedFileInfo info;
    fd=Fcreate(path,0);
    if (fd<3) return 1000+(int)IoErr();
    if (Fwrite(fd,9,bytes)!=9) return 234;
    if (Fclose(fd)) return 235;
    fd=Fopen(path,0);
    if (fd<3 || Fseek(3,fd,SEEK_SET)!=3 || Fseek(2,fd,SEEK_CUR)!=5 ||
        Fseek(-2,fd,SEEK_END)!=7) return 202;
    if (Fseek(1000,fd,SEEK_SET)!=-64 || IoErr()!=ERROR_SEEK_ERROR ||
        Fseek(0,fd,SEEK_CUR)!=7) return 203;
    if (Fseek(0,fd,SEEK_SET) || Fread(fd,32,buffer)!=9 ||
        memcmp(buffer,bytes,9) || Fread(fd,1,buffer)!=0 || Fclose(fd)) return 204;
    if (!QedFileInfo(path,&info) || !info.sizeKnown || info.size!=9 ||
        info.kind!=ST_FILE || info.dateKnown) return 205;
    if (Frename(0,path,renamed) || Fopen(path,0)!=-33) return 206;
    fd=Fopen(renamed,2);
    if (fd<3 || Fseek(8,fd,SEEK_SET)!=8 || Fwrite(fd,1,"z")!=1 || Fclose(fd)) return 207;
    fd=Fopen(renamed,0);
    if (fd<3 || Fread(fd,9,buffer)!=9 || buffer[8]!='z' || Fclose(fd) || Fdelete(renamed)) return 208;
    return 0;
}
static int stream_cases(void)
{
    FILE *one,*two;
    fpos_t position;
    int n;
    UWORD before;
    one=fopen("RAM:STDIO","w+b");two=fopen("RAM:SECOND","wb");
    if (!one) return 1000+errno;
    if (!two) return 1200+errno;
    n=fprintf(one,"value=%ld",1234L);
    if (n!=10) return 1500+n;
    if (fwrite(bytes,1,9,two)!=9) return 239;
    if (fclose(two)) return 240;
    if (fflush(one) || fseek(one,2,SEEK_SET) || ftell(one)!=2 ||
        fgetpos(one,&position) || position!=2 || fseek(one,-1,SEEK_END) || ftell(one)!=9 ||
        fsetpos(one,&position) || ftell(one)!=2) return 210;
    if (fseek(one,0,SEEK_SET) || fread(buffer,1,32,one)!=10 ||
        memcmp(buffer,"value=1234",10) || !feof(one) || fclose(one) ||
        __global_streams.sl_head || __global_streams.sl_tail) return 211;
    for (n=0;n<2;++n) {
        budget=n;before=closes;
        one=fopen("RAM:FAILOPEN","wb");budget=-1;
        if (one || errno!=ENOMEM || closes!=before+1 || QedFileCount() ||
            __global_streams.sl_head || Fdelete("RAM:FAILOPEN")) return 212;
    }
    one=fopen("RAM:SECOND","ab");
    if (!one || fseek(one,0,SEEK_SET) || fwrite("!",1,1,one)!=1 || fclose(one)) return 213;
    one=fopen("RAM:SECOND","rb");
    if (!one || fread(buffer,1,32,one)!=10 || memcmp(buffer,bytes,9) ||
        buffer[9]!='!' || fclose(one)) return 214;
    if (Fdelete("RAM:STDIO") || Fdelete("RAM:SECOND")) return 215;
    return 0;
}
static int failures(void)
{
    LONG fd;
    FILE *stream;
    int n,descriptors[QED_FILE_SLOTS];
    UWORD before;
    for (n=0;n<QED_FILE_SLOTS;++n) {
        descriptors[n]=_Stub_open("NIL:",O_WRONLY|O_CREAT|O_TRUNC);
        if (descriptors[n]<3) return 216;
    }
    before=closes;
    if (_Stub_open("NIL:",O_WRONLY|O_CREAT|O_TRUNC)!=-EMFILE || closes!=before+1) return 217;
    for (n=0;n<QED_FILE_SLOTS;++n) if (_Stub_close(descriptors[n])) return 218;
    before=closes;
    if ((int)_Stub_read(-1,buffer,1)!=-EBADF || Fread(-1,1,buffer)!=-37 ||
        _Stub_close(descriptors[0])!=-EBADF || closes!=before || _Stub_close(1) ||
        Write(Output(),"",0)!=0) return 219;
    fd=Fcreate("RAM:SHORT",0);writeLimit=3;
    if (fd<3 || Fwrite(fd,9,bytes)!=3 || IoErr()!=ERROR_DISK_FULL ||
        Fseek(0,fd,SEEK_CUR)!=3) return 220;
    writeLimit=-1;
    if (Fclose(fd)) return 221;
    fd=Fopen("RAM:SHORT",0);
    if (fd<3 || Fread(fd,32,buffer)!=3 || memcmp(buffer,bytes,3) || Fclose(fd) ||
        Fdelete("RAM:SHORT")) return 222;
    fd=Fcreate("RAM:FULL",0);writeLimit=0;
    if (fd<3 || Fwrite(fd,9,bytes)>=0 || IoErr()!=ERROR_DISK_FULL ||
        Fseek(0,fd,SEEK_CUR)!=0) return 229;
    writeLimit=-1;
    if (Fclose(fd) || Fdelete("RAM:FULL")) return 230;
    stream=fopen("RAM:CLOSEERR","wb");
    if (!stream || fwrite(bytes,1,9,stream)!=9) return 231;
    before=closes;closeFailure=1;
    if (fclose(stream)!=EOF || errno!=ENOSPC || IoErr()!=ERROR_DISK_FULL ||
        closes!=before+1 || QedFileCount() || __global_streams.sl_head) return 232;
    fd=Fopen("RAM:CLOSEERR",0);
    if (fd<3 || Fread(fd,32,buffer)!=9 || memcmp(buffer,bytes,9) || Fclose(fd) ||
        Fdelete("RAM:CLOSEERR")) return 233;
    return 0;
}
static int body(int argc,char **argv)
{
    FILE *stream;
    int result,count;
    char **quoted;
    LONG fd;
    time_t unavailable;
    if (argc!=2 || argv[1][1]) return 223;
    if (argv[1][0]=='E') {
        stream=fopen("RAM:LATEERR","wb");
        if (!stream || fwrite(bytes,1,9,stream)!=9) return 224;
        closeFailure=1;
        /* Real stdio buffering/flush/Close runs in ordinary entry cleanup. */
        return 0;
    }
    if (!QedArguments(" \"RAM:SPACE.BIN\" ","qed",&count,&quoted) || count!=2) return 236;
    result=roundtrip(quoted[1],"RAM:RENAMED");free(quoted);
    if (result || (result=roundtrip("ROUND.BIN","RENAMED.BIN")) ||
        (result=stream_cases()) || (result=failures())) return result;
    fd=Fcreate("SYS:SAVED.BIN",0);
    if (fd<3 || Fwrite(fd,9,bytes)!=9 || Fclose(fd)) return 237;
    if (_Stub_environ()[0] || getenv("QED_EDITOR") ||
        fprintf(stdout,"qed:%u",42)!=6 || ferror(stdout) ||
        time(&unavailable)!=(time_t)-1 ||
        unavailable!=(time_t)-1 || errno!=ENOSYS) return 225;
    return 0;
}
int main(void)
{
    struct QedHeapStats stats;
    LONG cause,fd;
    int result=QedRuntimeRun(body);
    cause=IoErr();QedHeapSnapshot(&stats);
    if (QedFileCount() || __global_streams.sl_head || __global_streams.sl_tail ||
        stats.blocks || stats.payload || stats.backing) return 226;
    if (ExecGetArgStr()[0]=='E') {
        if (result!=20 || cause!=ERROR_DISK_FULL) return 227;
        fd=Fopen("RAM:LATEERR",0);
        if (fd<3 || Fread(fd,32,buffer)!=9 || memcmp(buffer,bytes,9) || Fclose(fd) ||
            Fdelete("RAM:LATEERR")) return 228;
        SetIoErr(cause);return 20;
    }
    return result ? result:-321;
}
