"""Production cache code against an independent packed-pixel blitter model."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IconCache(unittest.TestCase):
    def test_pixels_mutation_and_eviction(self):
        source = (ROOT/'ports/gem4xe/adapter/gem-vbxe.c').read_text()
        declarations = source[source.index('#define ICON_CACHE_COUNT'):source.index('/* The 5120 bytes')]
        functions = source[source.index('static void icon_cache_build'):source.index('/* CICON pixels')]
        region = next(r for r in json.loads((ROOT/'platform/altirraos/vbxe-vram.json').read_text())['regions']
                      if r['name'] == 'icon_cache')
        prelude = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t UBYTE;
typedef uint16_t UWORD;
typedef int16_t WORD;
typedef uint32_t ULONG;
static UBYTE page[4096],vram[524288];
static ULONG GemScreenRows[240];
static UWORD fault,display;
static unsigned uploads;
static void flush(void) {}
static void latch(UWORD status) { assert(!status); }
static UWORD VbxeOwnerWrite(UWORD *d,ULONG at,const UBYTE *p,UWORD n)
{ (void)d;assert(at>=DESKTOP_ICON_CACHE_BASE && at+n<=sizeof(vram));
  memcpy(vram+at,p,n);++uploads;return 0; }
static void blit_mask(ULONG src,UWORD ss,ULONG dst,UWORD ds,UWORD bytes,UWORD rows,
                      UBYTE am,UBYTE xm,UBYTE mode)
{
    UWORD x,y;
    assert(src>=DESKTOP_ICON_CACHE_BASE && src+(rows-1)*ss+bytes<=sizeof(vram));
    assert(dst+(rows-1)*ds+bytes<=76800);
    for (y=0;y<rows;++y) for (x=0;x<bytes;++x) {
        UBYTE v=(vram[src+y*ss+x]&am)^xm;
        if (mode==4) vram[dst+y*ds+x]&=v;
        else { assert(mode==3);vram[dst+y*ds+x]|=v; }
    }
}
'''
        checks = r'''
static UWORD masks[18][48];
static UBYTE pixels[18][384],expected[76800];
static void check(UWORD id,UWORD w,UWORD h,WORD x,WORD y,
                  UWORD l,UWORD t,UWORD r,UWORD b)
{
    UWORD px,py,sx,sy;
    memset(vram,0x5a,76800);memcpy(expected,vram,76800);
    colour_icon_cached(masks[id],pixels[id],w,h,x,y,l,t,r,b);
    for (py=t;py<b;++py) for (px=l;px<r;++px) {
        sx=px-x;sy=py-y;
        if (masks[id][sy*(w/16)+sx/16]&(0x8000>>(sx%16))) {
            UBYTE v=pixels[id][sy*(w/2)+sx/2];
            v=(sx&1) ? v&15:v>>4;
            ULONG at=py*320+px/2;
            if (px&1) expected[at]=(expected[at]&0xf0)|v;
            else expected[at]=(expected[at]&15)|(v<<4);
        }
    }
    assert(!memcmp(vram,expected,76800));
}
int main(void)
{
    unsigned i,j,w,h,phase,before;
    for (i=0;i<240;++i) GemScreenRows[i]=i*320;
    for (i=0;i<18;++i) {
        for (j=0;j<48;++j) masks[i][j]=(j&1) ? 0xf3c0:0x83fe;
        for (j=0;j<384;++j) pixels[i][j]=(i*23+j*7)&255;
    }
    for (w=16;w<=32;w+=16) for (h=16;h<=24;h+=4) {
        before=uploads;
        for (phase=0;phase<2;++phase) {
            WORD x=40+phase;
            check(0,w,h,x,70,x,70,x+w,70+h);
            /* Both partial byte edges, a one-pixel clip and vertical clips. */
            check(0,w,h,x,70,x+3,72,x+w-3,70+h-2);
            check(0,w,h,x,70,x+4,73,x+5,74);
            check(0,w,h,-3,-2,0,0,w-3,h-2);
        }
        assert(uploads==before+1);
    }
    before=uploads;
    masks[0][0]^=0xffff;pixels[0][0]^=0xff;
    check(0,32,24,41,70,41,70,73,94);
    assert(uploads==before+1);
    for (i=1;i<18;++i) check(i,32,24,40,70,40,70,72,94);
    before=uploads;
    check(0,32,24,41,70,41,70,73,94);
    assert(uploads==before+1); /* Evicted pixels must be rebuilt. */
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'cache.c').write_text(
                f'#define DESKTOP_ICON_CACHE_BASE {region["base"]}UL\n'
                f'#define DESKTOP_ICON_CACHE_BYTES {region["capacity_bytes"]}UL\n'
                +prelude+declarations+functions+checks)
            subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                            str(p/'cache.c'),'-o',str(p/'cache')],check=True,capture_output=True)
            subprocess.run([str(p/'cache')],check=True,capture_output=True)


if __name__ == '__main__':
    unittest.main()
