"""Packed-edge production adapter against snapshot pixel translations."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class CopyPixels(unittest.TestCase):
    def test_overlap_edges_bounded_units_and_failure(self):
        self.check_backend(False)

    def test_raster_parity_overlap_and_failure(self):
        self.check_backend(True)

    def check_backend(self,raster):
        source=(ROOT/'ports/gem4xe/adapter/gem-vbxe.c').read_text()
        source=(source[source.index('static UWORD borrow_leave('):
                       source.index('UWORD GemDrawingMouseBorrow(')]+
                source[source.index('static UWORD raster_span(' if raster else 'UWORD GemDrawingCopyBorrow('):
                       source.index('NATIVE_UNIT(FrameBatch,')])
        prelude=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint8_t UBYTE;
typedef uint16_t UWORD;
typedef uint32_t ULONG;
typedef int32_t LONG;
struct DisplayGrant { int active; };
struct Surface { ULONG offset; UWORD pitch,width,height; };
struct VbxeCopy { struct Surface source,destination;
    UWORD sourceX,sourceY,destinationX,destinationY,width,height; };
#define DISPLAY_OK 0
#define DISPLAY_DEVICE_FAULT 5
#define EXEC_VDI_STRIP_ROWS 16
#define VBXE_LIST_WORK 8192
#define S_ONLY 3
#define D_ONLY 5
#define D_INVERT 10
static UBYTE vram[524288],original[76800],expected[76800];
static ULONG GemScreenRows[240];
static UWORD fault,display,outlineVisible,outlineDrawn;
static unsigned transfers,failAt,enters,leaves,work;
static unsigned rasterMode=3;
static UWORD DisplayEnter(struct DisplayGrant *g)
{ assert(!g->active);g->active=1;++enters;work=0;return 0; }
static UWORD DisplayLeave(struct DisplayGrant *g)
{ assert(g->active);if(RASTER)assert(work<=8192);g->active=0;++leaves;
  memset(vram+DESKTOP_RASTER_SCRATCH_BASE,0x9b,DESKTOP_RASTER_SCRATCH_BYTES);return 0; }
static void pointer_erase(UWORD l,UWORD t,UWORD r,UWORD b)
{ assert(l<r && t<b && r<=640 && b<=240); }
static void outline_toggle(void) {}
static void cursor_show(void) {}
static void latch(UWORD s) { if(s)fault=s; }
static UWORD fence_owner(void) { return fault ? 5:0; }
static int transfer(void) { if(++transfers==failAt) {fault=5;return 0;}return 1; }
static UWORD VbxeOwnerRead(UWORD *d,ULONG a,UBYTE *p,UWORD n)
{ (void)d;work+=n;if(!transfer())return 5;assert(a+n<=sizeof(vram));memcpy(p,vram+a,n);return 0; }
static UWORD VbxeOwnerWrite(UWORD *d,ULONG a,const UBYTE *p,UWORD n)
{ (void)d;work+=n;if(!transfer())return 5;assert(a+n<=sizeof(vram));memcpy(vram+a,p,n);return 0; }
static void blit_mask(ULONG s,UWORD ss,ULONG d,UWORD ds,UWORD w,UWORD h,
    UBYTE am,UBYTE xm,UBYTE mode)
{
    UWORD x,y;if(fault || !transfer())return;
    work+=w*h*(mode==0 || !am ? 2:3);
    assert(s+(h-1)*ss+w<=sizeof(vram) && d+(h-1)*ds+w<=sizeof(vram));
    for(y=0;y<h;++y)for(x=0;x<w;++x) {
        UBYTE v=(vram[s+y*ss+x]&am)^xm;
        if(mode==0)vram[d+y*ds+x]=v;
        else if(mode==3)vram[d+y*ds+x]|=v;
        else {assert(mode==4);vram[d+y*ds+x]&=v;}
    }
}
static void blit_and(ULONG d,UWORD ds,UWORD w,UWORD h,UBYTE v)
{ blit_mask(0,0,d,ds,w,h,0,v,4); }
static UWORD VbxeOwnerMapPage(UWORD *,ULONG,void (*)(UBYTE *,void *),void *);
static UWORD VbxeOwnerSubmit(UWORD *d,const UBYTE *p,UWORD count)
{
    ULONG s=p[0]|((ULONG)p[1]<<8)|((ULONG)p[2]<<16),a=p[6]|((ULONG)p[7]<<8)|((ULONG)p[8]<<16);
    int16_t ss=(int16_t)(p[3]|p[4]<<8),ds=(int16_t)(p[9]|p[10]<<8);
    int8_t sx=(int8_t)p[5],dx=(int8_t)p[11];
    UWORD bytes=(p[12]|p[13]<<8)+1,rows=p[14]+1,x,y;(void)d;
    work+=bytes*rows*(p[20] ? 3:2);
    if(!transfer())return 5;
    assert(count==1 && rows<=16 && bytes<=320);
    for(y=0;y<rows;y++)for(x=0;x<bytes;x++) {
        LONG sr=(LONG)s+y*(LONG)ss+x*(LONG)sx,dr=(LONG)a+y*(LONG)ds+x*(LONG)dx;
        UBYTE v;
        assert(sr>=0 && dr>=0 && sr<76800 && dr<76800);
        v=(vram[sr]&p[15])^p[16];
        if(p[20]==0)vram[dr]=v;
        else if(p[20]==3)vram[dr]|=v;
        else if(p[20]==4)vram[dr]&=v;
        else {assert(p[20]==5);vram[dr]^=v;}
    }
    return 0;
}
static UWORD VbxeOwnerCopyRect(UWORD *d,const struct VbxeCopy *c)
{
    UBYTE snapshot[76800];UWORD y;(void)d;
    if(!transfer())return 5;
    assert(!(c->sourceX&1) && !(c->destinationX&1) && !(c->width&1));
    assert(c->height<=16 && c->width*c->height<=8192);
    memcpy(snapshot,vram,76800);
    for(y=0;y<c->height;++y)memcpy(vram+(c->destinationY+y)*320+c->destinationX/2,
        snapshot+(c->sourceY+y)*320+c->sourceX/2,c->width/2);
    return 0;
}
'''
        checks=r'''
static UBYTE pixel(const UBYTE *p,UWORD x,UWORD y)
{ UBYTE v=p[y*320+x/2];return x&1 ? v&15:v>>4; }
static void put(UBYTE *p,UWORD x,UWORD y,UBYTE v)
{ ULONG a=y*320+x/2;if(x&1)p[a]=(p[a]&0xf0)|v;else p[a]=(p[a]&15)|(v<<4); }
static UBYTE operation(unsigned m,unsigned s,unsigned d)
{
    switch(m){case 0:return 0;case 1:return s&d;case 2:return s&~d;case 3:return s;
    case 4:return ~s&d;case 5:return d;case 6:return s^d;case 7:return s|d;
    case 8:return ~(s|d);case 9:return ~(s^d);case 10:return ~d;case 11:return s|~d;
    case 12:return ~s;case 13:return ~s|d;case 14:return ~(s&d);default:return 15;}
}
static void check(UWORD sx,UWORD sy,UWORD w,UWORD h,int dx,int dy,unsigned fail)
{
    struct DisplayGrant g={0};struct VbxeCopy c={{0,320,640,240},{0,320,640,240},sx,sy,sx+dx,sy+dy,w,h};
    UBYTE edges[644];UWORD x,y,result;
    memcpy(vram,original,76800);memcpy(expected,original,76800);
    transfers=enters=leaves=fault=0;failAt=fail;
    edges[642]=0xab;edges[643]=0xcd;
    for(y=0;y<h;++y)for(x=0;x<w;++x)put(expected,sx+dx+x,sy+dy+y,
        operation(rasterMode,pixel(original,sx+x,sy+y),pixel(original,sx+dx+x,sy+dy+y))&15);
#if RASTER
    {struct GemRasterCopy p={{0,320,640,240},{0,320,640,240},{sx,sy,sx+dx,sy+dy,w,h},rasterMode};
    result=GemDrawingRasterBorrow(&g,&p,edges);}
#else
    result=GemDrawingCopyBorrow(&g,&c,edges);
#endif
    assert(!g.active && enters==leaves && edges[642]==0xab && edges[643]==0xcd);
    if(!fail || transfers<fail) {assert(!result);if(memcmp(vram,expected,76800)) {
        fprintf(stderr,"mode=%u sx=%u sy=%u w=%u h=%u dx=%d dy=%d\n",rasterMode,sx,sy,w,h,dx,dy);abort();}}
    else assert(result==5);
}
int main(void)
{
    unsigned i,w,h,parity;int dx,dy;
    for(i=0;i<240;++i)GemScreenRows[i]=i*320;
    for(i=0;i<76800;++i)original[i]=(i*37+i/320*11+i/997)&255;
    for(parity=0;parity<2;++parity)for(w=1;w<=401;w+=20)
        for(h=1;h<=177;h+=16)for(dx=-8;dx<=8;dx+=RASTER ? 1:8)for(dy=-8;dy<=8;dy+=8)
            check(40+parity,20,w,h,dx,dy,0);
    check(1,0,638,232,0,8,0);check(1,8,638,232,0,-8,0);
#if RASTER
    /* Full-width overlap, both shift directions and all four scratch pages
     * for narrow 240-row copies; one-pixel output exercises zero-count shift. */
    check(1,0,639,239,-1,1,0);check(0,1,639,239,1,-1,0);
    check(1,0,1,240,-1,0,0);check(638,0,1,240,1,0,0);
    check(1,0,2,240,-1,0,0);check(0,0,2,240,1,0,0);
#endif
    for(i=1;i<=70;++i)check(41,20,400,177,RASTER ? 1:8,8,i);
#if RASTER
    for(rasterMode=0;rasterMode<16;rasterMode++)for(parity=0;parity<2;parity++)
        for(w=1;w<=320;w+=53)for(h=1;h<=64;h+=21)
            for(dx=-8;dx<=8;dx+=4)for(dy=-8;dy<=8;dy+=4)
                check(40+parity,20,w,h,dx,dy,0);
    for(rasterMode=0;rasterMode<16;rasterMode++)for(i=1;i<=70;++i)check(41,20,240,80,8,8,i);
#endif
    return 0;
}
'''
        mapped=r'''
static UWORD VbxeOwnerMapPage(UWORD *d,ULONG a,void (*modify)(UBYTE *,void *),void *context)
{
    struct RasterMappedShift *p=context;
    UBYTE before[4096];UWORD row,i;(void)d;
    if(!transfer())return 5;
    assert(!(a&4095) && a>=DESKTOP_RASTER_SCRATCH_BASE && a+4096<=DESKTOP_RASTER_SCRATCH_BASE+DESKTOP_RASTER_SCRATCH_BYTES);
    assert(p->rows>0 && p->rows<=4 && p->bytes>0 && p->bytes<=320);
    work+=3*p->bytes*p->rows;
    memcpy(before,vram+a,4096);modify(vram+a,context);
    for(row=0;row<4;++row)for(i=0;i<1024;++i)
        if(row>=p->rows || i<512 || i>=512+p->bytes)assert(vram[a+row*1024+i]==before[row*1024+i]);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            prelude='#include "'+str(ROOT/'c/include/hardware/vbxe-snapshots.h')+'"\n'+prelude
            prelude+='#include "'+str(ROOT/'ports/gem4xe/raster/core.h')+'"\n'
            prelude+='struct GemRasterRect {int32_t sx,sy,dx,dy,width,height;};\n'
            prelude+='struct GemRasterSurface {UBYTE *address;UWORD pitch,width,height;};\n'
            prelude+='struct GemRasterCopy {struct GemRasterSurface source,destination;struct GemRasterRect rect;UWORD mode;};\n'
            p=Path(directory);(p/'copy.c').write_text(prelude+source+(mapped if raster else '')+checks)
            subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable',
                '-I',str(ROOT/'ports/gem4xe/adapter'),'-DRASTER='+str(int(raster)),str(p/'copy.c'),'-o',str(p/'copy')],check=True,capture_output=True)
            result=subprocess.run([str(p/'copy')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
