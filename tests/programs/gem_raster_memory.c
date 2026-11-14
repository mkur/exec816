/* Execute the production row transfer across real CPU banks, without MEMAC. */
#include <proto/exec.h>
#include <hardware/vbxe.h>
#include <hardware/vbxe-snapshots.h>
#include <exec816/vdi-unit.h>
#include <string.h>
#include "drawing.h"
#include "core.h"
static struct VbxeDisplay display;
static ULONG GemScreenRows[240];
static UWORD fault,unexpected;
static UWORD packing;
static UBYTE recorded[21];
static UBYTE scratch[642],original[1408],expected[1408];
volatile UWORD RasterChecks;
volatile UWORD ShiftFailure[5];
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
UWORD VbxeOwnerMapPage(struct VbxeDisplay *d,ULONG a,void (*f)(UBYTE *,void *),void *p)
{ (void)d;(void)a;(void)f;(void)p;++unexpected;return DISPLAY_DEVICE_FAULT; }
static void blit_mask(ULONG a,UWORD b,ULONG c,UWORD d,UWORD e,UWORD f,UBYTE g,UBYTE h,UBYTE i)
{ (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)h;(void)i;++unexpected; }
static void blit_and(ULONG a,UWORD b,UWORD c,UWORD d,UBYTE e)
{ (void)a;(void)b;(void)c;(void)d;(void)e;++unexpected; }
UWORD VbxeOwnerSubmit(struct VbxeDisplay *d,const UBYTE *p,UWORD n)
{
    UWORD i;(void)d;
    if (packing && n==1) { for (i=0;i<21;++i) recorded[i]=p[i];return DISPLAY_OK; }
    ++unexpected;return DISPLAY_DEVICE_FAULT;
}
#include "raster-backend.inc"
#define CHECK(c) do { ++RasterChecks;if (!(c)) return __LINE__; } while (0)
static UWORD pixel(const UBYTE *p,UWORD x,UWORD y)
{ UWORD v=p[y*40+(x>>1)];return x&1 ? v&15:v>>4; }
static void put(UBYTE *p,UWORD x,UWORD y,UWORD v)
{ UWORD at=y*40+(x>>1),old=p[at];p[at]=(UBYTE)(x&1 ? (old&240)|v:(old&15)|(v<<4)); }
static UWORD operation(UWORD m,UWORD s,UWORD d)
{
    switch (m) {
    case 0:return 0;case 1:return s&d;case 2:return s&~d;case 3:return s;
    case 4:return ~s&d;case 5:return d;case 6:return s^d;case 7:return s|d;
    case 8:return ~(s|d);case 9:return ~(s^d);case 10:return ~d;case 11:return s|~d;
    case 12:return ~s;case 13:return ~s|d;case 14:return ~(s&d);default:return 15;
    }
}
LONG RasterPackingProbe(void)
{
    UWORD i;
    const UBYTE wanted[21]={0x6f,0x69,0,0xc0,0xfe,0xff,0x7b,0x78,0,0xc0,0xfe,0xff,6,0,7,0,0,0,0,0,0};
    for (i=0;i<240;++i) GemScreenRows[i]=(ULONG)i*320;
    packing=1;
    CHECK(raster_move(210,77,234,89,7,8,GemRasterRecipes[0])==DISPLAY_OK);
    for (i=0;i<21;++i) CHECK(recorded[i]==wanted[i]);
    packing=0;
    return 0;
}

LONG RasterShiftProbe(void)
{
    UBYTE *allocation,*source,*destination;
    ULONG boundary;
    UWORD i,n,k,place,wanted;
    const UWORD counts[]={0,1,2,3,17,257,320};
    GemRasterShift(NULL,NULL,0);
    allocation=AllocMem(196608UL,MEMF_PUBLIC|MEMF_LINEAR);
    CHECK(allocation!=NULL);
    boundary=((ULONG)allocation+65536UL)&0xffff0000UL;
    if (boundary-3<(ULONG)allocation) boundary+=65536UL;
    /* The first 16-bit load crosses at $xx:ffff. Both independent far
     * addresses must carry banks; count 257 also exercises Y's high byte. */
    for (place=0;place<2;++place) for (k=0;k<7;++k) {
        source=(UBYTE *)(boundary-1-place);
        destination=(UBYTE *)(boundary+65536UL-3+place);
        n=counts[k];
        for (i=0;i<321;++i) { source[i]=(UBYTE)(i*37+i/7);destination[i]=0xa7; }
        GemRasterShift(destination,source,n);
        for (i=0;i<321;++i) {
            wanted=0xa7;
            if (i<n) wanted=(((UWORD)source[i]<<4)|((UWORD)source[i+1]>>4))&255;
            if (destination[i]!=wanted) {
                ShiftFailure[0]=place;ShiftFailure[1]=n;ShiftFailure[2]=i;
                ShiftFailure[3]=destination[i];ShiftFailure[4]=wanted;
                CHECK(0);
            }
            CHECK(destination[i]==wanted);
            CHECK(source[i]==(UBYTE)(i*37+i/7));
        }
    }
    FreeMem(allocation,196608UL);
    return 0;
}

LONG RasterMappedProbe(void)
{
    UBYTE *page=AllocMem(4096UL,MEMF_PUBLIC|MEMF_LINEAR);
    void (*volatile operation)(UBYTE *,void *)=raster_shift_page;
    struct RasterMappedShift shift;
    UWORD i,k,right,rows,row,offset,value,nibble,half;
    WORD sourcePixel;
    const UWORD counts[]={1,2,17,319,320};
    CHECK(page!=NULL);
    for (right=0;right<2;++right) for (rows=1;rows<=4;rows+=3)
        for (k=0;k<5;++k) {
            shift.bytes=counts[k];shift.rows=rows;shift.right=right;
            for (i=0;i<4096;++i) page[i]=(UBYTE)(i*37+i/97);
            operation(page,&shift);
            for (i=0;i<4096;++i) {
                row=i/1024;offset=i&1023;value=(UBYTE)(i*37+i/97);
                if (row<rows && offset>=512 && offset<512+shift.bytes) {
                    value=0;
                    for (half=0;half<2;++half) {
                        sourcePixel=(WORD)((offset-512)*2+half)+(right ? -1:1);
                        nibble=0;
                        if (sourcePixel>=0) {
                            UWORD at=row*1024+(UWORD)sourcePixel/2;
                            nibble=(UBYTE)(at*37+at/97);
                            nibble=sourcePixel&1 ? nibble&15:nibble>>4;
                        }
                        value=(value<<4)|nibble;
                    }
                }
                CHECK(page[i]==value);
            }
        }
    FreeMem(page,4096UL);
    CHECK(!unexpected);
    return 0;
}

LONG RasterProbe(void)
{
    UBYTE *allocation,*source,*destination;
    ULONG boundary;
    struct GemRasterCopy p;
    UWORD i,x,y,same,mode,value,s,d,back,width;
    const UWORD widths[]={1,2,3,47,77};
    LONG result=RasterPackingProbe();
    if (result) return result;
    result=RasterMappedProbe();
    if (result) return result;
    result=RasterShiftProbe();
    if (result) return result;
    allocation=AllocMem(196608UL,MEMF_PUBLIC|MEMF_LINEAR);
    CHECK(allocation!=NULL);
    boundary=((ULONG)allocation+65536UL)&0xffff0000UL;
    if (boundary-17<(ULONG)allocation) boundary+=65536UL;
    source=(UBYTE *)(boundary-17);destination=(UBYTE *)(boundary+65536UL-11);
    p.source.pitch=p.destination.pitch=40;
    p.source.width=p.destination.width=80;p.source.height=p.destination.height=4;
    p.source.address=source;
    p.rect.sx=1;p.rect.sy=0;p.rect.dx=2;p.rect.dy=1;p.rect.width=77;p.rect.height=3;p.mode=3;
    for (mode=0;mode<16;++mode) for (same=0;same<2;++same) {
        p.mode=mode;
        p.destination.address=same ? source:destination;
        for (i=0;i<160;++i) {
            original[i]=source[i]=(UBYTE)(i*37+i/7);
            expected[i]=(UBYTE)(same ? original[i]:255-original[i]);
            p.destination.address[i]=expected[i];
        }
        for (y=0;y<3;++y) for (x=0;x<77;++x) {
            value=operation(mode,pixel(original,x+1,y),pixel(expected,x+2,y+1))&15;
            put(expected,x+2,y+1,value);
        }
        CHECK(GemDrawingRasterBorrow(NULL,&p,scratch)==DISPLAY_OK);
        for (i=0;i<160;++i) CHECK(p.destination.address[i]==expected[i]);
    }
    p.mode=S_ONLY;
    for (same=0;same<2;++same) for (s=0;s<2;++s) for (d=0;d<2;++d)
        for (back=0;back<2;++back) for (width=0;width<5;++width) {
            p.destination.address=same ? source:destination;
            p.rect.sx=s;p.rect.dx=d;p.rect.sy=back;p.rect.dy=1-back;
            p.rect.width=widths[width];p.rect.height=3;
            for (i=0;i<160;++i) {
                original[i]=source[i]=(UBYTE)(i*37+i/7);
                expected[i]=(UBYTE)(same ? original[i]:255-original[i]);
                p.destination.address[i]=expected[i];
            }
            for (y=0;y<3;++y) for (x=0;x<p.rect.width;++x)
                put(expected,x+d,y+1-back,pixel(original,x+s,y+back));
            CHECK(GemDrawingRasterBorrow(NULL,&p,scratch)==DISPLAY_OK);
            for (i=0;i<160;++i) CHECK(p.destination.address[i]==expected[i]);
        }
    /* Wider than the private 640-pixel row chunk: either overlap direction,
     * opposite parity and real CPU banks, including unchanged row padding. */
    p.source.pitch=p.destination.pitch=352;p.source.width=p.destination.width=704;
    p.rect.width=699;
    for (same=0;same<2;++same) for (back=0;back<2;++back) {
        p.destination.address=same ? source:destination;
        p.rect.sx=1+back;p.rect.dx=2-back;p.rect.sy=back;p.rect.dy=1-back;
        for (i=0;i<1408;++i) {
            original[i]=source[i]=(UBYTE)(i*37+i/7);
            expected[i]=(UBYTE)(same ? original[i]:255-original[i]);
            p.destination.address[i]=expected[i];
        }
        for (y=0;y<3;++y) for (x=0;x<699;++x) {
            i=(y+back)*352+((x+1+back)>>1);value=original[i];
            value=(x+1+back)&1 ? value&15:value>>4;
            i=(y+1-back)*352+((x+2-back)>>1);
            expected[i]=(UBYTE)((x+2-back)&1 ? (expected[i]&240)|value:(expected[i]&15)|(value<<4));
        }
        CHECK(GemDrawingRasterBorrow(NULL,&p,scratch)==DISPLAY_OK);
        for (i=0;i<1408;++i) CHECK(p.destination.address[i]==expected[i]);
    }
    CHECK(!unexpected && !fault);
    FreeMem(allocation,196608UL);
    return 0;
}
int main(void) { return 0; }
