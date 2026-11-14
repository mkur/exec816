/* SPDX-License-Identifier: MIT
 * Independently written MGVIEW-style loader/model consumer, without donor GUI.
 * Open -> FSTAT -> Malloc -> exact Fread -> line-pointer allocation.
 */
#include <compat/gemdos.h>
#include <exec816/c-runtime.h>
#include <exec816/program.h>
#include <proto/dos.h>
#include <proto/exec.h>
#include "internal.h"
#include <string.h>

struct Document { char *text,**lines;LONG bytes,count; };
static struct Document document;
static WORD executions,budget=-1,closeFailure,shortRead;
static UWORD closes;
static const char sample[]="one\r\ntwo\nthree\rfour\tend";
enum { D_LIMIT=-1001,D_MEMORY=-1002,D_READ=-1003,D_CLOSE=-1004,D_STAT=-1005 };

APTR ExecCRTTestAllocMem(ULONG bytes,ULONG flags)
{
    if (!budget) return NULL;
    if (budget>0) --budget;
    return AllocMem(bytes,flags);
}
BPTR ExecCRTTestOpen(const char *path,LONG mode) { return Open(path,mode); }
LONG ExecCRTTestWrite(BPTR file,const void *buffer,LONG bytes)
{ return Write(file,buffer,bytes); }
LONG ExecCRTTestRead(BPTR file,void *buffer,LONG bytes)
{
    LONG result=Read(file,buffer,shortRead ? 3:bytes);
    if (shortRead==2 && result>=0) SetIoErr(0x0000c219L);
    return result;
}
LONG ExecCRTTestClose(BPTR file)
{
    LONG result=Close(file);
    ++closes;
    if (result && closeFailure) { closeFailure=0;SetIoErr(ERROR_DISK_FULL);return 0; }
    return result;
}

static void discard(struct Document *value)
{
    Mfree(value->lines);Mfree(value->text);memset(value,0,sizeof(*value));
}

/* Keep acquisition private until both the text and index are complete. */
static int load(const char *path,struct Document *output)
{
    struct Document pending;
    XATTR info;
    WORD fd;
    LONG i,line,got,cause=0;
    int result=0;
    memset(&pending,0,sizeof(pending));
    fd=(WORD)Fopen(path,0);
    if (fd<0) return fd;
    if (Fcntl(fd,(LONG)&info,FSTAT)) { result=D_STAT;cause=IoErr();goto failed; }
    if (info.size<0 || info.size>EXEC_CRT_MAX_ALLOCATION-1) {
        result=D_LIMIT;cause=ERROR_OBJECT_TOO_LARGE;goto failed;
    }
    pending.text=Malloc(info.size+1);
    if (!pending.text) { result=D_MEMORY;cause=IoErr();goto failed; }
    got=Fread(fd,info.size,pending.text);
    if (got!=info.size) {
        result=D_READ;cause=IoErr();
        if (!cause) cause=ERROR_BAD_STREAM_NAME;
        goto failed;
    }
    pending.text[got]=0;pending.bytes=got;
    /* Close consumes the descriptor even when its terminal result fails. */
    result=(int)Fclose(fd);fd=-1;
    if (result) { result=D_CLOSE;cause=IoErr();goto failed; }
    pending.count=got ? 1:0;
    for (i=0;i<got;++i) {
        if (pending.text[i]=='\r' || pending.text[i]=='\n') {
            if (pending.text[i]=='\r' && i+1<got && pending.text[i+1]=='\n') ++i;
            if (i+1<got) ++pending.count;
        }
    }
    if (pending.count>EXEC_CRT_MAX_ALLOCATION/(LONG)sizeof(char *)) {
        result=D_LIMIT;cause=ERROR_OBJECT_TOO_LARGE;goto failed;
    }
    if (pending.count) {
        pending.lines=Malloc(pending.count*(LONG)sizeof(char *));
        if (!pending.lines) { result=D_MEMORY;cause=IoErr();goto failed; }
        pending.lines[0]=pending.text;line=1;
        for (i=0;i<got;++i) {
            if (pending.text[i]=='\r' || pending.text[i]=='\n') {
                if (pending.text[i]=='\r' && i+1<got && pending.text[i+1]=='\n') ++i;
                if (i+1<got) pending.lines[line++]=pending.text+i+1;
            }
        }
    }
    *output=pending;
    return 0;
failed:
    if (fd>=0) Fclose(fd);
    discard(&pending);SetIoErr(cause);
    return result;
}

static int failure(int expected,WORD allocation,WORD reading,WORD closing)
{
    struct Document before;
    struct ExecCRuntimeHeapStats first,last;
    UWORD files=ExecCRuntimeFileCount(),closed=closes;
    int result;
    memset(&document,0xa5,sizeof(document));before=document;
    ExecCRuntimeHeapSnapshot(&first);
    budget=allocation;shortRead=reading;closeFailure=closing;
    result=load("SYS:SMALL.TXT",&document);
    budget=-1;shortRead=0;closeFailure=0;
    ExecCRuntimeHeapSnapshot(&last);
    if (result!=expected || memcmp(&before,&document,sizeof(document)) ||
        files!=ExecCRuntimeFileCount() || first.blocks!=last.blocks ||
        first.backing!=last.backing || closes!=closed+1) return 1;
    if (reading==2 && IoErr()!=0x0000c219L) return 2;
    memset(&document,0,sizeof(document));
    return 0;
}

int main(void)
{
    WORD fd;
    char path[16]="SYS:DOC00.DAT";
    static const char hex[]="0123456789ABCDEF";
    ULONG bank=(ULONG)&document>>16;
    memset(&document,0,sizeof(document));
    if (load("SYS:SMALL.TXT",&document) || document.bytes!=23 || document.count!=4 ||
        memcmp(document.text,sample,23) || document.lines[1]!=document.text+5 ||
        document.lines[2]!=document.text+9 || document.lines[3]!=document.text+15) return 101;
    discard(&document);
    if (load("SYS:EMPTY.DAT",&document) || document.bytes || document.count ||
        !document.text || document.text[0] || document.lines) return 102;
    discard(&document);
    if (failure(D_STAT,0,0,0) || failure(D_MEMORY,1,0,0) ||
        failure(D_MEMORY,2,0,0) || failure(D_READ,-1,1,0) ||
        failure(D_READ,-1,2,0) || failure(D_CLOSE,-1,0,1)) return 103;
    if (!executions) {
        if (load("SYS:MAX.TXT",&document) || document.bytes!=65519L || document.count!=1 ||
            document.text[65519UL]) return 104;
        discard(&document);
        if (load("SYS:TOOBIG.TXT",&document)!=D_LIMIT || document.text) return 105;
        if (load("SYS:MAXLINES.TXT",&document) || document.count!=16380L ||
            document.lines[16379]!=document.text+16379) return 106;
        discard(&document);
        if (load("SYS:TALL.TXT",&document)!=D_LIMIT || document.text) return 107;
    }
    path[7]=hex[bank>>4];path[8]=hex[bank&15];
    fd=(WORD)Fcreate(path,0);
    if (fd<3 || Fwrite(fd,23,sample)!=23) return 108;
    /* Leave one document and writer for ordinary runtime FINISH/RELEASE. */
    if (load("SYS:SMALL.TXT",&document)) return 109;
    ++executions;SetIoErr(0);
    return -320-executions;
}
