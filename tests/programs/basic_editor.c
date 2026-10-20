/* Logical key/selection oracle using the application's actual editing code. */
#include "../../examples/gem-basic/editor.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) return __LINE__; ++BasicEditorChecks; } while (0)
volatile UWORD BasicEditorChecks;
static struct BasicEditor e;
static UBYTE bytes[512];
static WORD text(const char *wanted)
{
    ULONG size=strlen(wanted);
    if (e.document.bytes!=size) return 0;
    BasicCopy(&e.document,0,bytes,size);return !memcmp(bytes,wanted,size);
}
LONG EXEC_CALL BasicEditorProbe(ULONG unused)
{
    ULONG before=AvailMem(MEMF_UPPER),generation;
    (void)unused;CHECK(!BasicDocumentInit(&e.document));
    e.rows=8;e.columns=16;e.app.cellw=e.app.cellh=8;e.app.work[0]=10;e.app.work[1]=20;
    CHECK(!BasicEditorKey(&e,'a',0) && !BasicEditorKey(&e,9,0) && !BasicEditorKey(&e,'b',0));
    CHECK(e.caret==3 && BasicColumn(&e.document,e.caret)==9);
    CHECK(!BasicEditorKey(&e,13,0) && !BasicEditorKey(&e,'c',0) && text("a\tb\nc"));
    CHECK(!BasicEditorKey(&e,0x4b00,1) && e.caret==4 && e.anchor==5);
    CHECK(!BasicEditorKey(&e,'x',0) && text("a\tb\nx") && e.caret==5 && e.anchor==5);
    CHECK(!BasicEditorKey(&e,26,4) && text("a\tb\nc"));
    CHECK(!BasicEditorKey(&e,25,4) && text("a\tb\nx"));
    CHECK(!BasicEditorKey(&e,0x4700,0) && e.caret==4);
    CHECK(!BasicEditorKey(&e,0x4800,0) && e.caret==0);
    CHECK(!BasicEditorKey(&e,0x4d00,0) && e.caret==1);
    CHECK(!BasicEditorKey(&e,0x4d00,0) && e.caret==2 && BasicColumn(&e.document,e.caret)==8);
    CHECK(!BasicEditorKey(&e,0x5000,0) && e.caret==5);
    CHECK(!BasicEditorKey(&e,0x4700,1) && e.caret==4 && e.anchor==5);
    CHECK(!BasicEditorKey(&e,127,0) && text("a\tb\n") && e.caret==4);
    CHECK(!BasicEditorKey(&e,26,4) && text("a\tb\nx"));
    CHECK(!BasicEditorKey(&e,1,4) && e.anchor==0 && e.caret==5);
    CHECK(!BasicEditorKey(&e,'Z',1) && text("Z") && e.caret==1);
    CHECK(!BasicEditorKey(&e,26,4) && text("a\tb\nx"));
    CHECK(BasicEditorPosition(&e,10+4+9*8,20)==3);
    CHECK(BasicEditorPosition(&e,10+4+7*8,20)==1);
    CHECK(BasicEditorPosition(&e,10+4,28)==4);
    CHECK(BasicEditorPosition(&e,10,20+1000)==5);
    CHECK(!BasicEditorKey(&e,1,4) && !BasicEditorKey(&e,'A',1));
    memset(bytes,'k',255);CHECK(!BasicReplace(&e.document,0,e.document.bytes,bytes,255));
    e.caret=e.anchor=255;BasicEditorReveal(&e);generation=e.document.generation;
    CHECK(e.left==240 && e.caret==255);
    CHECK(BasicEditorKey(&e,'x',0)==BASIC_LINE_LENGTH && e.document.bytes==255 && e.document.generation==generation && e.caret==255);
    CHECK(!BasicEditorKey(&e,8,0) && e.document.bytes==254 && e.caret==254);
    BasicDocumentDispose(&e.document);CHECK(AvailMem(MEMF_UPPER)==before);
    return 0;
}
int main(void) { return 0; }
