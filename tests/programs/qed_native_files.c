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

int main(int argc,char **argv)
{
    FILE *stream;
    LONG fd;
    int result;
    time_t unavailable;
    if (argc!=2 || argv[1][1]) return 223;
    if (argv[1][0]=='E') {
        stream=fopen("SYS:LATEERR.BIN","wb");
        if (!stream || fwrite(bytes,1,9,stream)!=9) return 224;
        closeFailure=1;
        return 0;
    }
    if ((result=roundtrip("RAM:SPACE.BIN","RAM:RENAMED")) ||
        (result=roundtrip("ROUND.BIN","RENAMED.BIN"))) return result;
    fd=Fcreate("SYS:SAVED.BIN",0);
    if (fd<3 || Fwrite(fd,9,bytes)!=9 || Fclose(fd)) return 237;
    if (_Stub_environ()[0] || getenv("QED_EDITOR") ||
        fprintf(stdout,"qed:%u",42)!=6 || ferror(stdout) ||
        time(&unavailable)!=(time_t)-1 || unavailable!=(time_t)-1 || errno!=ENOSYS) return 225;
    return -321;
}
