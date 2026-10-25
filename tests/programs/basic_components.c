/* Isolated CPU attribution. Physical desktop latency is measured separately. */
#include "editor.h"
#include "assist-ui.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>
#include "component-source.h"
#include "component-row.h"
extern void ComponentColorBegin(void),ComponentColorEnd(void);
extern void ComponentFarBegin(void),ComponentFarEnd(void);
extern void ComponentTinyBegin(void),ComponentTinyEnd(void);
volatile UWORD ComponentChecks;
static struct BasicEditor e;
#define CHECK(c) do {++ComponentChecks;if(!(c))return __LINE__;} while(0)
static void reset_source(void)
{
    UWORD i,line=0;
    memcpy(e.document.data,componentSource,sizeof(componentSource));
    e.document.gap=e.document.bytes=sizeof(componentSource);e.document.end=BASIC_BYTES;
    e.document.used=e.document.cursor=0;e.document.generation=e.document.saved=e.document.serial=1;
    e.document.line[0]=0;
    for(i=0;i<sizeof(componentSource);++i) if(componentSource[i]==10)e.document.line[++line]=i+1;
    e.document.lines=line+1;e.document.line[line+1]=sizeof(componentSource);
}
LONG EXEC_CALL ComponentProbe(ULONG unused)
{
    ULONG baseline=AvailMem(MEMF_UPPER);UWORD sample,row;UBYTE q='q';
    (void)unused;CHECK(!BasicDocumentInit(&e.document));reset_source();
    e.rows=19;e.columns=56;e.left=20;BasicAssistanceInit(&e);
    for(sample=0;sample<20;++sample) {
        ComponentColorBegin();
        for(row=1;row<=19;++row) {
#ifdef COMPONENT_COMPOSE
            BasicAssistanceCompose(&e,row);
#else
            ComponentRowText(&e,row);
            BasicAssistanceColors(&e,row,e.colors);
#endif
        }
        ComponentColorEnd();CHECK(e.colors[0]==3);
    }
    for(sample=0;sample<20;++sample) {
        reset_source();ComponentFarBegin();
        CHECK(BasicReplace(&e.document,0,0,&q,1)==BASIC_OK);
        ComponentFarEnd();CHECK(e.document.bytes==32768 && e.document.gap==1);
        ComponentTinyBegin();
        CHECK(BasicReplace(&e.document,0,1,NULL,0)==BASIC_OK);
        ComponentTinyEnd();CHECK(e.document.bytes==32767 && e.document.gap==0);
    }
    BasicAssistanceDispose();BasicDocumentDispose(&e.document);
    CHECK(AvailMem(MEMF_UPPER)==baseline);return 0;
}
int main(void) {return 0;}
