/* Independent byte/index oracle for the production editor model. */
#include "../../examples/gem-basic/document.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) return __LINE__; ++BasicChecks; } while (0)
volatile UWORD BasicChecks;
static struct BasicDocument d;
static UBYTE block[4096],copy[4096];
static UBYTE bulk[16365];
static UWORD allocations,failAt,badGuard;
static APTR owned[3];
static ULONG sizes[3];
APTR EXEC_CALL BasicTestAlloc(ULONG size,ULONG flags)
{
    UBYTE *p;UWORD i;
    if (++allocations==failAt) return 0;
    p=AllocMem(size+32,flags);if (!p) return 0;
    memset(p,0xa7,16);memset(p+16+size,0x7a,16);
    for (i=0;i<3;++i) if (!owned[i]) { owned[i]=p;sizes[i]=size;break; }
    return p+16;
}
void EXEC_CALL BasicTestFree(APTR data,ULONG size)
{
    UBYTE *p=(UBYTE *)data-16;UWORD i,j;
    for (i=0;i<3;++i) if (owned[i]==p) {
        if (sizes[i]!=size) ++badGuard;
        for (j=0;j<16;++j) if (p[j]!=0xa7 || p[size+16+j]!=0x7a) ++badGuard;
        owned[i]=0;FreeMem(p,size+32);return;
    }
    ++badGuard;
}
static WORD valid(void)
{
    ULONG i;UWORD line=0,column=0;UBYTE c;
    if (d.gap>d.end || d.end>BASIC_BYTES || d.bytes!=BASIC_BYTES-d.end+d.gap || d.line[0]) return 0;
    for (i=0;i<d.bytes;++i) {
        c=BasicByte(&d,i);
        if (c==10) { if (d.line[++line]!=i+1) return 0;column=0; }
        else if (++column>255) return 0;
    }
    return d.lines==line+1 && d.line[d.lines]==d.bytes;
}
LONG EXEC_CALL BasicDocumentProbe(ULONG unused)
{
    ULONG before,i,generation;UWORD n;
    (void)unused;before=AvailMem(MEMF_UPPER);
    for (n=1;n<=3;++n) {
        allocations=0;failAt=n;
        CHECK(BasicDocumentInit(&d)==BASIC_MEMORY);
        CHECK(!d.data && !d.line && !d.undo && AvailMem(MEMF_UPPER)==before && !badGuard);
    }
    failAt=0;CHECK(BasicDocumentInit(&d)==BASIC_OK);
    CHECK(d.bytes==0 && d.lines==1 && !BasicDirty(&d) && valid());
    CHECK(BasicReplace(&d,0,0,(const UBYTE *)"A\tB\nC\n",6)==0 && valid());
    CHECK(d.lines==3 && d.line[1]==4 && d.line[2]==6 && d.line[3]==6);
    CHECK(BasicColumn(&d,3)==9 && BasicLine(&d,4)==1 && BasicLine(&d,6)==2);
    CHECK(BasicDirty(&d) && BasicUndo(&d) && !d.bytes && !BasicDirty(&d) && valid());
    CHECK(BasicRedo(&d) && d.bytes==6 && valid());
    d.saved=d.generation;
    CHECK(BasicReplace(&d,1,4,(const UBYTE *)"XY\n",3)==0 && valid());
    BasicCopy(&d,0,copy,d.bytes);CHECK(d.bytes==5 && !memcmp(copy,"AXY\n\n",5));
    CHECK(BasicUndo(&d) && !BasicDirty(&d) && valid());
    CHECK(BasicReplace(&d,6,0,(const UBYTE *)"Z",1)==0 && !BasicRedo(&d) && valid());
    generation=d.generation;
    CHECK(BasicReplace(&d,0,0,(const UBYTE *)"\x80",1)==BASIC_CHARACTER && d.generation==generation);
    CHECK(BasicReplace(&d,8,0,(const UBYTE *)"x",1)==BASIC_POSITION && d.generation==generation);
    CHECK(BasicReplace(&d,0,0,0,1)==BASIC_POSITION);
    BasicDocumentDispose(&d);CHECK(!badGuard && AvailMem(MEMF_UPPER)==before);
    CHECK(!BasicDocumentInit(&d));memset(block,'a',256);
    CHECK(!BasicReplace(&d,0,0,block,255) && valid());
    CHECK(BasicReplace(&d,0,0,block,1)==BASIC_LINE_LENGTH && d.bytes==255 && valid());
    CHECK(!BasicReplace(&d,128,0,(const UBYTE *)"\n",1) && d.lines==2 && valid());
    CHECK(BasicUndo(&d) && d.lines==1 && valid());
    BasicDocumentDispose(&d);CHECK(!BasicDocumentInit(&d));
    memset(block,10,sizeof(block));
    CHECK(!BasicReplace(&d,0,0,block,4095) && d.lines==4096 && valid());
    CHECK(BasicReplace(&d,d.bytes,0,block,1)==BASIC_LINE_CAPACITY && valid());
    CHECK(BasicUndo(&d) && !d.bytes && BasicRedo(&d) && valid());
    BasicDocumentDispose(&d);CHECK(!BasicDocumentInit(&d));
    for (i=0;i<sizeof(block);++i) block[i]=(i%128)==127 ? 10:'x';
    for (n=0;n<8;++n) CHECK(!BasicReplace(&d,d.bytes,0,block,sizeof(block)) && valid());
    CHECK(d.bytes==BASIC_BYTES && d.lines==257);
    generation=d.generation;
    CHECK(BasicReplace(&d,0,0,(const UBYTE *)"x",1)==BASIC_CAPACITY && d.generation==generation && valid());
    CHECK(BasicReplace(&d,0,d.bytes,0,0)==BASIC_UNDO_CAPACITY && d.bytes==BASIC_BYTES && valid());
    /* Maximum movement in both directions and complete oldest-group eviction. */
    CHECK(!BasicReplace(&d,0,1,(const UBYTE *)"A",1) && BasicByte(&d,0)=='A' && valid());
    CHECK(!BasicReplace(&d,d.bytes-2,1,(const UBYTE *)"Z",1) && BasicByte(&d,d.bytes-2)=='Z' && valid());
    CHECK(BasicUndo(&d) && BasicByte(&d,d.bytes-2)=='x' && valid());
    CHECK(BasicRedo(&d) && BasicByte(&d,d.bytes-2)=='Z' && valid());
    for (n=0;n<70;++n) {
        memset(block,n&1 ? 'a':'b',127);
        CHECK(!BasicReplace(&d,0,127,block,127));
    }
    n=0;while (BasicUndo(&d)) { ++n;if (n>70) return __LINE__; }
    CHECK(n>0 && n<70 && valid());
    while (BasicRedo(&d)) { }
    CHECK(BasicByte(&d,0)=='a' && valid());
    BasicDocumentDispose(&d);CHECK(!badGuard && AvailMem(MEMF_UPPER)==before);
    CHECK(!BasicDocumentInit(&d));
    for (i=0;i<sizeof(bulk);++i) bulk[i]=i%128==127 ? 10:'k';
    CHECK(BasicReplace(&d,0,0,bulk,16365)==BASIC_UNDO_CAPACITY && !d.bytes && !d.used && !BasicDirty(&d));
    CHECK(!BasicReplace(&d,0,0,bulk,16364) && d.used==BASIC_UNDO_BYTES && valid());
    CHECK(!BasicReplace(&d,d.bytes,0,(const UBYTE *)"x",1) && BasicUndo(&d) && !BasicUndo(&d) && valid());
    d.serial=0xffffffffUL;generation=d.generation;
    CHECK(BasicReplace(&d,0,1,(const UBYTE *)"z",1)==BASIC_GENERATION && d.generation==generation && BasicByte(&d,0)=='k');
    BasicDocumentDispose(&d);CHECK(!badGuard && AvailMem(MEMF_UPPER)==before);
    CHECK(!BasicDocumentInit(&d));memset(block,'j',255);block[255]=10;memset(block+256,'j',255);
    CHECK(!BasicReplace(&d,0,0,block,511) && valid());
    CHECK(BasicReplace(&d,255,1,0,0)==BASIC_LINE_LENGTH && d.bytes==511 && valid());
    CHECK(BasicReplace(&d,0,0,(const UBYTE *)"\0",1)==BASIC_CHARACTER && valid());
    BasicDocumentDispose(&d);CHECK(!badGuard && AvailMem(MEMF_UPPER)==before);
    return 0;
}
int main(void) { return 0; }
