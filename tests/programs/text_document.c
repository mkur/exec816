#include "../../examples/gem-text/document.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) return __LINE__; ++TextChecks; } while (0)
volatile UWORD TextChecks;
static struct TextDocument doc;
static struct TextLoad load;
static char row[83],argument[128];
static WORD mode,fault,allocations,failAllocation;
static ULONG reads,offset,size;
static LONG error;
static WORD handles,locks;
static const char mixed[]="A\tB\r\nC\rD\n\x9b\0\x80Z";
static const char *names[]={"D1:MIX.TXT","D1:FULL.TXT","D1:LINES.TXT",
    "D1:OVER.TXT","D1:MANY.TXT","D1:SPLIT.TXT","D1:EMPTY.TXT"};
APTR EXEC_CALL TextTestAlloc(ULONG bytes,ULONG flags)
{
    if (++allocations==failAllocation) return 0;
    return AllocMem(bytes,flags);
}
#ifdef TEXT_MOCK
BPTR EXEC_CALL Lock(CONST_STRPTR name,LONG access)
{ (void)name;(void)access;error=ERROR_OBJECT_NOT_FOUND;if (fault==1) return 0;++locks;return 1; }
void EXEC_CALL UnLock(BPTR lock) { (void)lock;--locks;error=0; }
LONG EXEC_CALL Examine(BPTR lock,struct FileInfoBlock *info)
{
    (void)lock;info->fib_DirEntryType=fault==3 ? 1:-3;info->fib_Size=0;
    error=fault==2 ? ERROR_NO_DISK:0;return fault!=2;
}
BPTR EXEC_CALL Open(CONST_STRPTR name,LONG access)
{
    (void)name;if (access!=MODE_OLDFILE) return 0;
    error=fault==4 ? ERROR_OBJECT_NOT_FOUND:0;
    if (fault==4) return 0;
    offset=0;size=mode==0 ? sizeof(mixed)-1:mode==1 ? 65536UL:mode==2 ? 4096UL:
        mode==3 ? 65537UL:mode==4 ? 4097UL:mode==5 ? 1027UL:0;
    ++handles;return 2;
}
LONG EXEC_CALL Read(BPTR file,void *buffer,LONG length)
{
    UBYTE *out=buffer;LONG n=0;
    (void)file;++reads;error=0;
    if (length>1024) { error=ERROR_BAD_NUMBER;return -1; }
    while (n<length && offset<size) {
        out[n++]=mode==0 ? mixed[offset]:mode==2 || mode==4 ? 10:
            mode==5 ? (offset==1023 ? 13:offset==1024 ? 10:offset>1024 ? 'B':'A'):'A';
        ++offset;
    }
    if ((fault==5 || fault==6) && offset>1024) { error=ERROR_BREAK;return fault==5 ? -1:n; }
    return n;
}
LONG EXEC_CALL Close(BPTR file)
{ (void)file;--handles;error=fault==7 ? ERROR_NO_DISK:0;return fault!=7; }
LONG EXEC_CALL IoErr(void) { return error; }
#endif
static WORD finish(void)
{
    WORD result=0,steps=0;
    while (load.phase && steps++<75) result=TextStep(&load,&doc);
    return result;
}
LONG EXEC_CALL TextDocumentProbe(ULONG unused)
{
    WORD i,result;ULONG before,baseline;
    (void)unused;
    CHECK(TextArgument("  \"D1:MIX.TXT\"  ",argument) && !strcmp(argument,"D1:MIX.TXT"));
    CHECK(!TextArgument("a b",argument) && !TextArgument("\"a",argument));
    CHECK(TextArgument(0,argument) && !*argument);
#ifndef TEXT_MOCK
    {
        BPTR warm=Lock(names[0],SHARED_LOCK);
        CHECK(warm!=0);UnLock(warm);
    }
#endif
    baseline=AvailMem(MEMF_UPPER);
    for (mode=0;mode<7;++mode) {
        TextBegin(&load,names[mode]);result=finish();
        if (mode==3 || mode==4) {
            CHECK(result==-1 && doc.lines==(mode==3 ? 4096:4096));
            CHECK(load.error==(mode==3 ? ERROR_OBJECT_TOO_LARGE:TEXT_LINE_LIMIT));
            continue;
        }
        CHECK(result==1 && !load.phase && !load.file);
        row[0]='!';row[82]='!';before=reads;
        TextRow(&doc,0,row+1,80);
        CHECK(row[0]=='!' && row[82]=='!' && row[81]==0 && reads==before);
        if (mode==0) {
            CHECK(doc.lines==5 && doc.bytes==sizeof(mixed)-1);
            CHECK(!memcmp(doc.data,mixed,sizeof(mixed)-1));
            CHECK(!memcmp(row+1,"A       B ",10));
            TextRow(&doc,4,row+1,8);CHECK(!strcmp(row+1,"..Z     "));
        } else if (mode==1) {
            CHECK(doc.lines==1 && doc.bytes==65536UL && doc.line[1]==65536UL);
            for (i=1;i<=80;++i) CHECK(row[i]=='A');
        } else if (mode==2) CHECK(doc.lines==4096 && doc.line[4096]==4096);
        else if (mode==5) {
            CHECK(doc.lines==2 && doc.line[1]==1025);
            TextRow(&doc,1,row+1,8);CHECK(!strcmp(row+1,"BB      "));
        } else CHECK(doc.lines==0 && doc.bytes==0);
    }
    mode=0;TextBegin(&load,names[0]);CHECK(finish()==1);
    for (i=1;i<=2;++i) {
        allocations=0;failAllocation=i;
        TextBegin(&load,names[0]);CHECK(finish()==-1 && load.error==ERROR_NO_FREE_STORE);
        CHECK(doc.lines==5 && !load.file && !load.candidate.data && !load.candidate.line);
    }
    failAllocation=0;
    TextBegin(&load,names[0]);TextCancel(&load);CHECK(doc.lines==5 && !load.phase);
    TextBegin(&load,names[0]);CHECK(!TextStep(&load,&doc));CHECK(!TextStep(&load,&doc));
    CHECK(!TextStep(&load,&doc));TextCancel(&load);CHECK(doc.lines==5 && !load.file);
#ifdef TEXT_MOCK
    for (fault=1;fault<=7;++fault) {
        mode=1;TextBegin(&load,names[1]);CHECK(finish()==-1);
        CHECK(doc.lines==5 && !strcmp(doc.path,names[0]) && !handles && !locks);
        CHECK(!load.candidate.data && !load.candidate.line);
    }
    fault=0;
#endif
    TextDispose(&doc);CHECK(!doc.data && !doc.line && !handles && !locks);
    CHECK(AvailMem(MEMF_UPPER)==baseline);
    return 0;
}
int main(void) { return 0; }
