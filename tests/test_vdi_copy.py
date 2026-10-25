"""Packed-edge production adapter against snapshot pixel translations."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class CopyPixels(unittest.TestCase):
    def test_overlap_edges_bounded_units_and_failure(self):
        source=(ROOT/'ports/gem4xe/adapter/gem-vbxe.c').read_text()
        source=source[source.index('static UWORD copy_leave('):source.index('NATIVE_UNIT(FrameBatch,')]
        prelude=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t UBYTE;
typedef uint16_t UWORD;
typedef uint32_t ULONG;
struct DisplayGrant { int active; };
struct Surface { ULONG offset; UWORD pitch,width,height; };
struct VbxeCopy { struct Surface source,destination;
    UWORD sourceX,sourceY,destinationX,destinationY,width,height; };
#define DISPLAY_OK 0
#define DISPLAY_DEVICE_FAULT 5
#define EXEC_VDI_STRIP_ROWS 16
#define VBXE_LIST_WORK 8192
static UBYTE vram[524288],original[76800],expected[76800];
static ULONG GemScreenRows[240];
static UWORD fault,display,outlineVisible,outlineDrawn;
static unsigned transfers,failAt,enters,leaves;
static UWORD DisplayEnter(struct DisplayGrant *g)
{ assert(!g->active);g->active=1;++enters;return 0; }
static UWORD DisplayLeave(struct DisplayGrant *g)
{ assert(g->active);g->active=0;++leaves;return 0; }
static void pointer_erase(UWORD l,UWORD t,UWORD r,UWORD b)
{ assert(l<r && t<b && r<=640 && b<=240); }
static void outline_toggle(void) {}
static void cursor_show(void) {}
static void latch(UWORD s) { if(s)fault=s; }
static UWORD fence_owner(void) { return fault ? 5:0; }
static int transfer(void) { if(++transfers==failAt) {fault=5;return 0;}return 1; }
static UWORD VbxeOwnerRead(UWORD *d,ULONG a,UBYTE *p,UWORD n)
{ (void)d;if(!transfer())return 5;assert(a+n<=sizeof(vram));memcpy(p,vram+a,n);return 0; }
static UWORD VbxeOwnerWrite(UWORD *d,ULONG a,const UBYTE *p,UWORD n)
{ (void)d;if(!transfer())return 5;assert(a+n<=sizeof(vram));memcpy(vram+a,p,n);return 0; }
static void blit_mask(ULONG s,UWORD ss,ULONG d,UWORD ds,UWORD w,UWORD h,
    UBYTE am,UBYTE xm,UBYTE mode)
{
    UWORD x,y;if(fault || !transfer())return;
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
static void check(UWORD sx,UWORD sy,UWORD w,UWORD h,int dx,int dy,unsigned fail)
{
    struct DisplayGrant g={0};struct VbxeCopy c={{0,320,640,240},{0,320,640,240},sx,sy,sx+dx,sy+dy,w,h};
    UBYTE edges[482];UWORD x,y,result;
    memcpy(vram,original,76800);memcpy(expected,original,76800);
    transfers=enters=leaves=fault=0;failAt=fail;
    edges[480]=0xab;edges[481]=0xcd;
    for(y=0;y<h;++y)for(x=0;x<w;++x)put(expected,sx+dx+x,sy+dy+y,pixel(original,sx+x,sy+y));
    result=GemDrawingCopyBorrow(&g,&c,edges);
    assert(!g.active && enters==leaves && edges[480]==0xab && edges[481]==0xcd);
    if(!fail || transfers<fail) {assert(!result);assert(!memcmp(vram,expected,76800));}
    else assert(result==5);
}
int main(void)
{
    unsigned i,w,h,parity;int dx,dy;
    for(i=0;i<240;++i)GemScreenRows[i]=i*320;
    for(i=0;i<76800;++i)original[i]=(i*37+i/320*11+i/997)&255;
    for(parity=0;parity<2;++parity)for(w=1;w<=401;w+=20)
        for(h=1;h<=177;h+=16)for(dx=-8;dx<=8;dx+=8)for(dy=-8;dy<=8;dy+=8)
            check(40+parity,20,w,h,dx,dy,0);
    check(1,0,638,232,0,8,0);check(1,8,638,232,0,-8,0);
    for(i=1;i<=70;++i)check(41,20,400,177,8,8,i);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);(p/'copy.c').write_text(prelude+source+checks)
            subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(p/'copy.c'),'-o',str(p/'copy')],check=True,capture_output=True)
            subprocess.run([str(p/'copy')],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
