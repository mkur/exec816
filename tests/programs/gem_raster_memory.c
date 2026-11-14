/* Execute the production row transfer across real CPU banks, without MEMAC. */
#include <proto/exec.h>
#include <hardware/vbxe.h>
#include <exec816/vdi-unit.h>
#include <string.h>
#include "drawing.h"
#include "core.h"
static struct VbxeDisplay display;
static ULONG GemScreenRows[240];
static UWORD fault,unexpected;
static UBYTE scratch[642],original[160],expected[160];
volatile UWORD RasterChecks;
UWORD DisplayEnter(struct DisplayGrant *g) { (void)g;++unexpected;return DISPLAY_DEVICE_FAULT; }
UWORD DisplayLeave(struct DisplayGrant *g) { (void)g;++unexpected;return DISPLAY_DEVICE_FAULT; }
static void pointer_erase(UWORD l,UWORD t,UWORD r,UWORD b)
{ (void)l;(void)t;(void)r;(void)b;++unexpected; }
static UWORD fence_owner(void) { ++unexpected;return DISPLAY_DEVICE_FAULT; }
static UWORD borrow_leave(struct DisplayGrant *g) { (void)g;++unexpected;return DISPLAY_DEVICE_FAULT; }
static void latch(UWORD status) { if (status) fault=status; }
UWORD VbxeOwnerRead(struct VbxeDisplay *d,ULONG a,void *p,UWORD n)
{ (void)d;(void)a;(void)p;(void)n;++unexpected;return DISPLAY_DEVICE_FAULT; }
UWORD VbxeOwnerWrite(struct VbxeDisplay *d,ULONG a,const void *p,UWORD n)
{ (void)d;(void)a;(void)p;(void)n;++unexpected;return DISPLAY_DEVICE_FAULT; }
#include "raster-backend.inc"
#define CHECK(c) do { ++RasterChecks;if (!(c)) return __LINE__; } while (0)
static UWORD pixel(const UBYTE *p,UWORD x,UWORD y)
{ UWORD v=p[y*40+(x>>1)];return x&1 ? v&15:v>>4; }
static void put(UBYTE *p,UWORD x,UWORD y,UWORD v)
{ UWORD at=y*40+(x>>1),old=p[at];p[at]=(UBYTE)(x&1 ? (old&240)|v:(old&15)|(v<<4)); }
LONG RasterProbe(void)
{
    UBYTE *allocation,*source,*destination;
    ULONG boundary;
    struct GemRasterCopy p;
    UWORD i,x,y,same;
    allocation=AllocMem(196608UL,MEMF_PUBLIC|MEMF_LINEAR);
    CHECK(allocation!=NULL);
    boundary=((ULONG)allocation+65536UL)&0xffff0000UL;
    if (boundary-17<(ULONG)allocation) boundary+=65536UL;
    source=(UBYTE *)(boundary-17);destination=(UBYTE *)(boundary+65536UL-11);
    p.source.pitch=p.destination.pitch=40;
    p.source.width=p.destination.width=80;p.source.height=p.destination.height=4;
    p.source.address=source;
    p.rect.sx=1;p.rect.sy=0;p.rect.dx=2;p.rect.dy=1;p.rect.width=77;p.rect.height=3;p.mode=3;
    for (same=0;same<2;++same) {
        p.destination.address=same ? source:destination;
        for (i=0;i<160;++i) {
            original[i]=source[i]=(UBYTE)(i*37+i/7);
            expected[i]=(UBYTE)(same ? original[i]:255-original[i]);
            p.destination.address[i]=expected[i];
        }
        for (y=0;y<3;++y) for (x=0;x<77;++x)
            put(expected,x+2,y+1,pixel(original,x+1,y));
        CHECK(GemDrawingRasterBorrow(NULL,&p,scratch)==DISPLAY_OK);
        for (i=0;i<160;++i) CHECK(p.destination.address[i]==expected[i]);
    }
    CHECK(!unexpected && !fault);
    FreeMem(allocation,196608UL);
    return 0;
}
int main(void) { return 0; }
