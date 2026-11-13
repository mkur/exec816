/* Independent explicit pixel definitions exercise the selected donor C. */
#include "core.h"
#include "geometry.h"
volatile uint16_t RasterChecks;
static uint8_t source[322],destination[322],expected[322];
#define CHECK(c) do { ++RasterChecks; if (!(c)) return __LINE__; } while (0)

static uint16_t operation(uint16_t m,uint16_t s,uint16_t d)
{
    switch (m) {
    case 0:return 0; case 1:return s&d; case 2:return s&~d; case 3:return s;
    case 4:return ~s&d; case 5:return d; case 6:return s^d; case 7:return s|d;
    case 8:return ~(s|d); case 9:return ~(s^d); case 10:return ~d; case 11:return s|~d;
    case 12:return ~s; case 13:return ~s|d; case 14:return ~(s&d); default:return 15;
    }
}

int32_t RasterProbe(void)
{
    uint16_t m,s,d,i,j,w,n,v,b;
    const uint16_t widths[]={1,2,3,23,46,47,79,80,239,640};
    int16_t corners[8]={32767,32767,-32768,-32768,32767,32767,-32768,-32768};
    struct GemRasterRect r;
    GemRasterNormalize(&r,corners);
    CHECK(r.sx==-32768 && r.sy==-32768 && r.width==65536L && r.height==65536L);
    CHECK(GemRasterClip(&r,0,0,640,240,0,0,640,240));
    CHECK(r.sx==0 && r.dx==0 && r.width==640 && r.height==240);
    r.sx=-3;r.sy=-4;r.dx=20;r.dy=30;r.width=12;r.height=16;
    CHECK(GemRasterClip(&r,0,0,640,240,22,32,640,240));
    CHECK(r.sx==0 && r.sy==0 && r.dx==23 && r.dy==34 && r.width==9 && r.height==12);
    for (m=0;m<16;++m) for (s=0;s<2;++s) for (d=0;d<2;++d)
        for (w=0;w<sizeof(widths)/sizeof(widths[0]);++w) {
            n=widths[w];
            for (i=0;i<322;++i) {
                source[i]=(uint8_t)(i*37+i/7);
                destination[i]=expected[i]=(uint8_t)(i*13+27);
            }
            for (i=0;i<n;++i) {
                j=s+i;v=source[j>>1];v=j&1 ? v&15:v>>4;
                j=d+i;b=expected[j>>1];
                v=operation(m,v,j&1 ? b&15:b>>4)&15;
                expected[j>>1]=(uint8_t)(j&1 ? (b&240)|v:(b&15)|(v<<4));
            }
            GemRasterMerge(destination,source,s,d,n,m);
            for (i=0;i<322;++i) CHECK(destination[i]==expected[i]);
        }
    return 0;
}

int main(void) { return (int)RasterProbe(); }
