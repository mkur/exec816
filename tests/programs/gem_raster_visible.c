/* In-place fragment execution must match an independent whole-copy snapshot. */
#include <stdint.h>
struct AESRect { int16_t left,top,right,bottom; };
#include "visible.h"
static uint8_t pixels[128*80],original[128*80],expected[128*80];
volatile uint16_t RasterChecks;
#define CHECK(c) do { ++RasterChecks;if (!(c)) return __LINE__; } while (0)
static int16_t apply(void *context,const struct GemRasterRect *r)
{
    int16_t x,y,xx,yy;
    (void)context;
    for (y=0;y<r->height;++y) {
        yy=r->dy>r->sy ? r->height-1-y:y;
        for (x=0;x<r->width;++x) {
            xx=r->dx>r->sx ? r->width-1-x:x;
            pixels[(r->dy+yy)*128+r->dx+xx]=pixels[(r->sy+yy)*128+r->sx+xx];
        }
    }
    return 1;
}
int32_t RasterProbe(void)
{
    struct AESRect visible[4]={{20,12,76,22},{20,22,44,45},{58,22,76,45},{20,45,76,58}},swap;
    struct GemRasterRect r;
    int16_t dx,dy,i,j,x,y,order;
    for (order=0;order<4;++order) {
        swap=visible[0];visible[0]=visible[order];visible[order]=swap;
        for (dx=-8;dx<=8;dx+=8) for (dy=-8;dy<=8;dy+=8) {
            r.sx=20-dx;r.sy=12-dy;r.dx=20;r.dy=12;r.width=56;r.height=46;
            for (i=0;i<128*80;++i) pixels[i]=original[i]=expected[i]=(uint8_t)((i*37+i/128*11)&255);
            for (j=0;j<4;++j) for (y=visible[j].top;y<visible[j].bottom;++y)
                for (x=visible[j].left;x<visible[j].right;++x)
                    expected[y*128+x]=original[(y-dy)*128+x-dx];
            CHECK(GemRasterVisible(&r,visible,4,apply,0));
            for (i=0;i<128*80;++i) CHECK(pixels[i]==expected[i]);
        }
    }
    return 0;
}
int main(void) { return (int)RasterProbe(); }
