/* Independent source/colour/navigation expectations for the editor helper. */
#include "../../examples/gem-basic/assist.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) return __LINE__; ++BasicAssistChecks; } while (0)
volatile UWORD BasicAssistChecks;
volatile ULONG BasicAssistTrace[80];
volatile WORD BasicAssistLastResult;
volatile ULONG BasicAssistLastCount;
volatile ULONG BasicAssistSpan,BasicAssistSize,BasicAssistLength,BasicAssistFirst,BasicAssistLast,BasicAssistBytes;
volatile ULONG BasicAssistAllocationSize,BasicAssistAllocationFlags,BasicAssistAllocationResult,BasicAssistFree;
APTR EXEC_CALL BasicAssistAlloc(ULONG bytes,ULONG flags)
{
    APTR p;
    BasicAssistAllocationSize=bytes;BasicAssistAllocationFlags=flags;BasicAssistFree=AvailMem(MEMF_UPPER);
    p=AllocMem(bytes,flags);BasicAssistAllocationResult=(ULONG)p;return p;
}
static struct BasicDocument d;
static struct BasicAssist a;
static struct BasicFind f;
static struct BasicReplaceJob bulk;
static UBYTE bytes[8192],colors[257];
static WORD text(const char *s)
{ ULONG n=strlen(s);BasicCopy(&d,0,bytes,d.bytes<sizeof(bytes) ? d.bytes:sizeof(bytes));return d.bytes==n && !memcmp(bytes,s,n); }
static WORD set(const char *s) { return BasicReplace(&d,0,d.bytes,(const UBYTE *)s,strlen(s)); }
LONG EXEC_CALL BasicAssistProbe(ULONG unused)
{
    ULONG before=AvailMem(MEMF_UPPER),count,caret,generation;WORD result;UWORD steps,i;
    (void)unused;CHECK(!BasicDocumentInit(&d));
    CHECK(!set("one ONE stone one"));
    CHECK(!BasicFindBegin(&f,&d,(const UBYTE *)"ONE",3,1,1));
    CHECK(BasicFindStep(&f,&d)==1 && f.result==4);
    CHECK(!BasicFindBegin(&f,&d,(const UBYTE *)"one",3,0,0));
    CHECK(BasicFindStep(&f,&d)==1 && f.result==0);
    CHECK(!BasicFindBegin(&f,&d,(const UBYTE *)"absent",6,0,1) && BasicFindStep(&f,&d)==-1);
    CHECK(BasicFindBegin(&f,&d,(const UBYTE *)"",0,0,0)==BASIC_POSITION);
    BasicAssistLastResult=BasicReplaceBegin(&bulk,&d,(const UBYTE *)"one",3,(const UBYTE *)"x",1,1);
    i=0;do {
        result=BasicReplaceStep(&bulk,&d);
        if (i<10) {
            BasicAssistTrace[i*8]=bulk.phase;BasicAssistTrace[i*8+1]=bulk.count;
            BasicAssistTrace[i*8+2]=bulk.find.at;BasicAssistTrace[i*8+3]=bulk.find.result;
            BasicAssistTrace[i*8+4]=bulk.last;BasicAssistTrace[i*8+5]=bulk.span;
            BasicAssistTrace[i*8+6]=bulk.bytes;BasicAssistTrace[i*8+7]=bulk.find.length;
        }
        ++i;
    } while (!result);
    BasicAssistLastResult=bulk.error;count=bulk.count;BasicAssistLastCount=count;
    BasicAssistSpan=bulk.span;BasicAssistSize=bulk.size;BasicAssistLength=bulk.find.length;
    BasicAssistFirst=bulk.first;BasicAssistLast=bulk.last;BasicAssistBytes=bulk.bytes;
    CHECK(!BasicAssistLastResult && count==4 && text("x x stx x"));
    CHECK(BasicUndo(&d) && text("one ONE stone one"));
    CHECK(BasicRedo(&d) && text("x x stx x"));
    CHECK(!set("  \tPRINT 1"));caret=0;
    CHECK(!BasicIndent(&d,d.bytes,0,&caret) && text("  \tPRINT 1\n  \t") && caret==d.bytes);
    CHECK(BasicUndo(&d) && text("  \tPRINT 1"));
    CHECK(!set("pRiNt \"IF REM PROC\" ' THEN"));
    memset(colors,77,sizeof(colors));BasicLexLine(&d,0,colors);
    CHECK(colors[0]==4 && colors[4]==4 && colors[5]==1);
    CHECK(colors[6]==2 && colors[18]==2 && colors[19]==1 && colors[20]==3 && colors[26]==77);
    CHECK(!set("REMARK = 1\nrem PRINT\nPRINT \"unfinished\n\t\n"));
    BasicLexLine(&d,0,colors);CHECK(colors[0]==1 && colors[5]==1);
    BasicLexLine(&d,1,colors);CHECK(colors[0]==3 && colors[8]==3);
    BasicLexLine(&d,2,colors);CHECK(colors[0]==4 && colors[6]==2 && colors[16]==2);
    CHECK(!set("' PROC fake\nPROC Foo\n PRINT 1\nENDPROC\nproc Foobar\nENDPROC\nPROC\n\n"));
    BasicCopy(&d,0,bytes,d.bytes);generation=d.generation;
    BasicAssistBegin(&a,&d);steps=0;while (!BasicAssistStep(&a,&d)) ++steps;
    CHECK(steps>0 && a.count==2 && a.procedures[0].first==1 && a.procedures[0].last==3);
    CHECK(BasicProcedureNamed(&a,"foo")==0 && BasicProcedureNamed(&a,"FOOBAR")==1 && BasicProcedureNamed(&a,"fo")==-1);
    CHECK(BasicFold(&a,0) && !BasicHidden(&a,1) && BasicHidden(&a,2) && BasicHidden(&a,3) && !BasicHidden(&a,4));
    CHECK(BasicVisible(&a,1,1)==4);
    BasicUnfold(&a,3);CHECK(!BasicHidden(&a,2) && !BasicHidden(&a,3));
    CHECK(d.generation==generation);
    for (i=0;i<d.bytes;++i) CHECK(bytes[i]==BasicByte(&d,i));
    CHECK(BasicFold(&a,1) && BasicHidden(&a,5));BasicUnfold(&a,5);CHECK(!BasicHidden(&a,5));
    CHECK(!set("PRINT 7"));CHECK(!BasicFindBegin(&f,&d,(const UBYTE *)"7",1,0,0));
    CHECK(!BasicReplace(&d,0,0,(const UBYTE *)" ",1) && BasicFindStep(&f,&d)==-1);
    while (!BasicAssistStep(&a,&d)) {} CHECK(a.count==0 && !BasicHidden(&a,5));
    CHECK(!set(""));memset(bytes,'a',255);bytes[255]=10;
    for (i=0;i<128;++i) CHECK(!BasicReplace(&d,d.bytes,0,bytes,256));
    CHECK(d.bytes==32768);
    memset(bytes,'a',79);bytes[79]='b';CHECK(!BasicFindBegin(&f,&d,bytes,80,0,0));
    steps=0;do { result=BasicFindStep(&f,&d);++steps; } while (!result);
    CHECK(result==-1 && steps>=32 && steps<=65);
    generation=d.generation;
    CHECK(BasicReplaceMatches(&d,(const UBYTE *)"a",1,(const UBYTE *)"x",1,0,&count)==BASIC_UNDO_CAPACITY && d.generation==generation);
    CHECK(BasicReplaceMatches(&d,(const UBYTE *)"a",1,(const UBYTE *)"xx",2,0,&count)==BASIC_CAPACITY && d.bytes==32768);
    BasicDocumentDispose(&d);CHECK(!BasicDocumentInit(&d));
    CHECK(!set("abababx"));CHECK(!BasicFindBegin(&f,&d,(const UBYTE *)"ababx",5,0,0));
    CHECK(BasicFindStep(&f,&d)==1 && f.result==2);
    CHECK(!set("abab"));CHECK(!BasicReplaceMatches(&d,(const UBYTE *)"ab",2,0,0,0,&count) && count==2 && !d.bytes);
    CHECK(BasicUndo(&d) && text("abab"));
    generation=d.generation;CHECK(!BasicReplaceBegin(&bulk,&d,(const UBYTE *)"ab",2,(const UBYTE *)"x",1,0));
    CHECK(!BasicReplaceStep(&bulk,&d));BasicReplaceCancel(&bulk);CHECK(d.generation==generation && text("abab"));
    CHECK(!BasicReplaceBegin(&bulk,&d,(const UBYTE *)"ab",2,(const UBYTE *)"x",1,0));
    CHECK(!BasicReplace(&d,0,0,(const UBYTE *)" ",1));CHECK(BasicReplaceStep(&bulk,&d)==-1 && bulk.error==BASIC_GENERATION);
    CHECK(!set(""));
    for (i=0;i<256;++i) CHECK(!BasicReplace(&d,d.bytes,0,(const UBYTE *)"PROC P\nENDPROC\n",15));
    BasicAssistBegin(&a,&d);while (!BasicAssistStep(&a,&d)) {}
    CHECK(a.count==256 && !a.overflow && BasicFold(&a,255) && BasicHidden(&a,511));
    CHECK(!BasicReplace(&d,d.bytes,0,(const UBYTE *)"PROC EXTRA\nENDPROC\n",19));
    while (!BasicAssistStep(&a,&d)) {} CHECK(a.count==256 && a.overflow);
    BasicDocumentDispose(&d);CHECK(AvailMem(MEMF_UPPER)==before);return 0;
}
int main(void) { return 0; }
