/* File transactions: independent byte oracle and consumed-handle faults. */
#include "../../examples/gem-basic/files.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>
#ifndef BASIC_VOLUME
#define BASIC_VOLUME "RAM:"
#endif
#define CHECK(x) do { if (!(x)) return __LINE__; ++BasicFileChecks; } while (0)
volatile UWORD BasicFileChecks;
static struct BasicDocument document;
static struct BasicFile named;
static struct BasicFileJob job;
static UBYTE source[4096],actual[4096];
#ifdef BASIC_FILE_MOCK
struct File { char name[128];UBYTE *data;ULONG bytes,at;WORD open; };
static struct File files[16];
static LONG ioError;
static WORD fault,renameCount,allocations,failAllocation,closeCount,opened;
static UWORD maximumRead,maximumWrite;
APTR EXEC_CALL BasicFileTestAlloc(ULONG bytes,ULONG flags)
{ if (++allocations==failAllocation) return 0;return AllocMem(bytes,flags); }
static WORD node(const char *name)
{ WORD i;for (i=0;i<16;++i) if (files[i].data && !strcmp(files[i].name,name)) return i;return -1; }
BPTR EXEC_CALL Open(CONST_STRPTR path,LONG mode)
{
    WORD i=node(path);ioError=0;
    if (fault==1) { ioError=ERROR_DISK_WRITE_PROTECTED;return 0; }
    if (mode==MODE_CREATE_EXCLUSIVE && i>=0) { ioError=ERROR_OBJECT_EXISTS;return 0; }
    if (i<0 && mode==MODE_OLDFILE) { ioError=ERROR_OBJECT_NOT_FOUND;return 0; }
    if (i<0) {
        for (i=0;i<16 && files[i].data;++i) { }
        if (i==16) { ioError=ERROR_DISK_FULL;return 0; }
        files[i].data=AllocMem(65536UL,MEMF_UPPER);if (!files[i].data) { ioError=ERROR_NO_FREE_STORE;return 0; }
        strcpy(files[i].name,path);files[i].bytes=0;
    }
    if (files[i].open) { ioError=ERROR_OBJECT_IN_USE;return 0; }
    if (mode!=MODE_OLDFILE) files[i].bytes=0;
    files[i].at=0;files[i].open=1;++opened;return i+1;
}
LONG EXEC_CALL Read(BPTR file,void *data,LONG bytes)
{
    struct File *f=&files[file-1];LONG n;ioError=0;
    if (job.phase && bytes>maximumRead) maximumRead=bytes;
    if (fault==2) { ioError=ERROR_NO_DISK;return -1; }
    n=bytes;if ((ULONG)n>f->bytes-f->at) n=f->bytes-f->at;
    if (fault==3 && n>7) n=7;
    memcpy(data,f->data+f->at,n);f->at+=n;
    if (fault==4 && n) ioError=ERROR_BREAK;
    return n;
}
LONG EXEC_CALL Write(BPTR file,const void *data,LONG bytes)
{
    struct File *f=&files[file-1];LONG n=bytes;ioError=0;
    if (job.phase && bytes>maximumWrite) maximumWrite=bytes;
    if (fault==5) { ioError=ERROR_DISK_FULL;return -1; }
    if (fault==6 && n>7) n=7;
    if ((ULONG)n>65536UL-f->at) { ioError=ERROR_DISK_FULL;return -1; }
    memcpy(f->data+f->at,data,n);f->at+=n;if (f->at>f->bytes) f->bytes=f->at;
    if (fault==7) ioError=ERROR_BREAK;
    return n;
}
LONG EXEC_CALL Close(BPTR file)
{
    struct File *f=&files[file-1];++closeCount;ioError=0;
    if (!f->open) { ioError=ERROR_BAD_STREAM_NAME;return 0; }
    f->open=0;--opened;
    if (fault==8) { ioError=ERROR_NO_DISK;return 0; }
    return 1;
}
LONG EXEC_CALL Rename(CONST_STRPTR old,CONST_STRPTR next)
{
    WORD i=node(old);ioError=0;++renameCount;
    if ((fault==9 && renameCount==1) || (fault==10 && renameCount==2) || (fault==11 && renameCount==3))
        { ioError=ERROR_NO_DISK;return 0; }
    if (i<0) { ioError=ERROR_OBJECT_NOT_FOUND;return 0; }
    if (node(next)>=0) { ioError=ERROR_OBJECT_EXISTS;return 0; }
    strcpy(files[i].name,next);return 1;
}
LONG EXEC_CALL DeleteFile(CONST_STRPTR path)
{
    WORD i=node(path);ioError=0;
    if (i<0) { ioError=ERROR_OBJECT_NOT_FOUND;return 0; }
    if (fault==12) { ioError=ERROR_NO_DISK;return 0; }
    FreeMem(files[i].data,65536UL);memset(&files[i],0,sizeof(files[i]));return 1;
}
LONG EXEC_CALL IoErr(void) { return ioError; }
static void reset(void)
{
    WORD i;
    for (i=0;i<16;++i) if (files[i].data) FreeMem(files[i].data,65536UL);
    memset(files,0,sizeof(files));fault=renameCount=opened=0;
}
#endif
static WORD store(const char *path,const UBYTE *bytes,ULONG n)
{
    BPTR file=Open(path,MODE_NEWFILE);LONG written;
    if (!file) return 0;
    written=Write(file,bytes,n);if (!Close(file)) return 0;
    return written==(LONG)n;
}
static WORD equals(const char *path,const UBYTE *bytes,ULONG n)
{
    BPTR file=Open(path,MODE_OLDFILE);LONG got;
    if (!file) return 0;
    got=Read(file,actual,sizeof(actual));if (!Close(file)) return 0;
    return got==(LONG)n && !memcmp(actual,bytes,n);
}
static WORD finish(void)
{
    WORD n=0,result=0;
    while (job.phase && ++n<2048) result=BasicFileStep(&job,&document,&named);
    return n<2048 ? result:-2;
}
static WORD repeated(const char *path,UBYTE extra)
{
    BPTR file=Open(path,MODE_NEWFILE);UWORD i;WORD okay=1;
    if (!file) return 0;
    for (i=0;i<8;++i) if (Write(file,source,sizeof(source))!=sizeof(source)) okay=0;
    if (extra && Write(file,"x",1)!=1) okay=0;
    if (!Close(file)) okay=0;
    return okay;
}
LONG EXEC_CALL BasicFileProbe(ULONG unused)
{
    static const UBYTE *text[]={ (const UBYTE *)"A\tB\x9b" "C\x9b",(const UBYTE *)"A\tB\nC\n",
        (const UBYTE *)"A\tB\r\nC\r\n",(const UBYTE *)"A\tB\rC\r" };
    static const UWORD sizes[]={6,6,8,6};
    UWORD i,style;ULONG baseline,generation;
    (void)unused;
#ifndef BASIC_FILE_MOCK
    CHECK(store(BASIC_VOLUME "WARM.TMP",(const UBYTE *)"x",1) && DeleteFile(BASIC_VOLUME "WARM.TMP"));
#endif
    baseline=AvailMem(MEMF_UPPER);
    CHECK(!BasicDocumentInit(&document));
    for (style=0;style<4;++style) {
        CHECK(store(BASIC_VOLUME "IN.BAS",text[style],sizes[style]));
        CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==1);
        BasicCopy(&document,0,actual,document.bytes);
        CHECK(document.bytes==6 && document.lines==3 && !memcmp(actual,"A\tB\nC\n",6));
        CHECK(named.eol==style && !BasicDirty(&document));
        CHECK(BasicSaveBegin(&job,&document,&named,BASIC_VOLUME "OUT.BAS") && finish()==1);
        CHECK(equals(BASIC_VOLUME "OUT.BAS",text[style],sizes[style]) && !BasicDirty(&document));
        CHECK(DeleteFile(BASIC_VOLUME "OUT.BAS"));
    }
    CHECK(store(BASIC_VOLUME "IN.BAS",(const UBYTE *)"A\r\nB\n",5));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==1 && BasicDirty(&document) && named.eol==BASIC_EOL_CRLF);
    CHECK(BasicSaveBegin(&job,&document,&named,BASIC_VOLUME "OUT.BAS") && finish()==1);
    CHECK(equals(BASIC_VOLUME "OUT.BAS",(const UBYTE *)"A\r\nB\r\n",6) && !BasicDirty(&document));
    CHECK(store(BASIC_VOLUME "IN.BAS",(const UBYTE *)"",0));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==1 && !document.bytes && document.lines==1);
    CHECK(store(BASIC_VOLUME "IN.BAS",(const UBYTE *)"FINAL",5));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==1 && document.lines==1);
    CHECK(BasicSaveBegin(&job,&document,&named,BASIC_VOLUME "OUT.BAS") && finish()==1);
    CHECK(equals(BASIC_VOLUME "OUT.BAS",(const UBYTE *)"FINAL",5));
    generation=document.generation;
    CHECK(BasicSaveBegin(&job,&document,&named,BASIC_VOLUME "OUT.BAS"));
    CHECK(!BasicReplace(&document,5,0,(const UBYTE *)"!",1));
    CHECK(finish()==1 && document.saved==generation && BasicDirty(&document));
    CHECK(equals(BASIC_VOLUME "OUT.BAS",(const UBYTE *)"FINAL",5));
    CHECK(store(BASIC_VOLUME "IN.BAS",(const UBYTE *)"\x80",1));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==-1 && document.bytes==6);
    BasicCopy(&document,0,actual,6);CHECK(!memcmp(actual,"FINAL!",6));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "OUT.BAS"));BasicFileCancel(&job);
    CHECK(job.error==ERROR_BREAK && !job.phase && document.bytes==6);
    memset(actual,'n',128);actual[128]=0;
    CHECK(!BasicLoadBegin(&job,(const char *)actual) && job.error==ERROR_BAD_STREAM_NAME && document.bytes==6);
    CHECK(!BasicSaveBegin(&job,&document,&named,(const char *)actual) && !job.snapshot);
    actual[127]=0;CHECK(BasicLoadBegin(&job,(const char *)actual) && strlen(job.named.path)==127);
    BasicFileCancel(&job);CHECK(document.bytes==6 && !job.candidate.data);
    for (i=0;i<sizeof(source);++i) source[i]=i%128==127 ? 10:'x';
    CHECK(repeated(BASIC_VOLUME "IN.BAS",0));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==1 && document.bytes==BASIC_BYTES && document.lines==257);
    CHECK(repeated(BASIC_VOLUME "IN.BAS",1));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==-1 && document.bytes==BASIC_BYTES);
    memset(source,10,sizeof(source));
    CHECK(store(BASIC_VOLUME "IN.BAS",source,4095));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==1 && document.lines==4096);
    CHECK(store(BASIC_VOLUME "IN.BAS",source,4096));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==-1 && document.lines==4096);
    memset(source,'L',256);CHECK(store(BASIC_VOLUME "IN.BAS",source,256));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==-1 && document.lines==4096);
    CHECK(store(BASIC_VOLUME "IN.BAS",source,255));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==1 && document.bytes==255);
    memset(source,'p',sizeof(source));for (i=0;i<sizeof(source);i+=128) source[i]=10;
    /* Deliberately place a CR at the end of one read and LF in the next. */
    source[1022]=13;source[1023]=10;
    CHECK(store(BASIC_VOLUME "IN.BAS",source,sizeof(source)));
    CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && finish()==1 && document.bytes==4095);
    CHECK(BasicByte(&document,1022)==10 && BasicByte(&document,1023)==10);
#ifdef BASIC_FILE_MOCK
    CHECK(maximumRead<=1024 && maximumWrite<=1024);
    for (i=1;i<=3;++i) {
        allocations=0;failAllocation=i;
        CHECK(!BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS") && job.error==ERROR_NO_FREE_STORE && !job.phase);
        CHECK(document.bytes==4095 && !opened);
    }
    failAllocation=0;
    allocations=0;failAllocation=1;
    CHECK(!BasicSaveBegin(&job,&document,&named,BASIC_VOLUME "OUT.BAS") && !job.snapshot && !job.phase);
    failAllocation=0;
    for (i=2;i<=8;++i) {
        if (i>4 && i!=8) continue;
        fault=i;CHECK(BasicLoadBegin(&job,BASIC_VOLUME "IN.BAS"));
        if (i==3) CHECK(finish()==1);else CHECK(finish()==-1);
        CHECK(!opened && !job.handle && !job.candidate.data && document.bytes==4095);
        fault=0;
    }
    for (i=1;i<=11;++i) {
        reset();CHECK(store(BASIC_VOLUME "OLD.BAS",(const UBYTE *)"OLD",3));
        CHECK(BasicSaveBegin(&job,&document,&named,BASIC_VOLUME "OLD.BAS"));
        fault=i;renameCount=0;
        if (i==2 || i==3 || i==4) { BasicFileCancel(&job);fault=0;continue; }
        if (i==6) CHECK(finish()==1);else CHECK(finish()==-1);
        CHECK(!opened && !job.handle && !job.snapshot);
        fault=0;
        if (i>=9) {
            CHECK(job.complete && job.temporary[0] && node(job.temporary)>=0);
            if (i==11) CHECK(job.moved && equals(job.backup,(const UBYTE *)"OLD",3));
            else CHECK(equals(BASIC_VOLUME "OLD.BAS",(const UBYTE *)"OLD",3));
        }
        CHECK(BasicSaveBegin(&job,&document,&named,BASIC_VOLUME "OLD.BAS") && finish()==1);
        CHECK(!opened && !BasicDirty(&document));
    }
    reset();
#else
    CHECK(DeleteFile(BASIC_VOLUME "IN.BAS") && DeleteFile(BASIC_VOLUME "OUT.BAS"));
#endif
    BasicDocumentDispose(&document);CHECK(AvailMem(MEMF_UPPER)==baseline);
    return 0;
}
int main(void) { return 0; }
