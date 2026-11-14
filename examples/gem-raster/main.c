/* SPDX-License-Identifier: MIT
 * Conventional GEM scrolling and screen/memory round trips. */
#include "raster.h"
#include <stdlib.h>
struct RasterApp GEMRaster;

static void paint(WORD l,WORD t,WORD r,WORD b)
{
    struct RasterApp *a=&GEMRaster;
    WORD i,y,value,n;
    WORD *p=a->points;
    p[0]=l;p[1]=t;p[2]=r-1;p[3]=b-1;vs_clip(a->vdi,1,p);
    for (i=0;i<12;++i) {
        y=a->work[1]+i*8;
        if (y>=b || y+8<=t) continue;
        value=(UWORD)(a->first+i);
        p[0]=a->work[0];p[1]=y;p[2]=a->work[0]+a->work[2]-1;p[3]=y+7;
        vsf_color(a->vdi,(UWORD)value%14+2);v_bar(a->vdi,p);
        a->label[0]='R';a->label[1]='o';a->label[2]='w';a->label[3]=' ';
        for (n=8;n>=4;--n) { a->label[n]='0'+(UWORD)value%10;value=(UWORD)value/10; }
        a->label[9]=0;vst_color(a->vdi,1);
        v_gtext(a->vdi,a->work[0]+2-a->left,y+6,a->label);
    }
}

static void transfer(WORD sx,WORD sy,WORD dx,WORD dy,WORD w,WORD h,
    const MFDB *source,const MFDB *destination)
{
    WORD *p=GEMRaster.points;
    p[0]=sx;p[1]=sy;p[2]=sx+w-1;p[3]=sy+h-1;
    p[4]=dx;p[5]=dy;p[6]=dx+w-1;p[7]=dy+h-1;
    vro_cpyfm(GEMRaster.vdi,S_ONLY,p,source,destination);
}

/* A visible fragment supplies both ends of a scroll; its exposed strip is
 * reconstructed from the same row model used by WM_REDRAW. */
static WORD render(WORD direction)
{
    struct RasterApp *a=&GEMRaster;
    WORD x,y,w,h,l,t,r,b,okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(a->window,WF_WORKXYWH,&a->work[0],&a->work[1],&a->work[2],&a->work[3]);
    if (okay) okay=wind_get(a->window,WF_FIRSTXYWH,&x,&y,&w,&h);
    while (okay && w>0 && h>0) {
        l=x>a->work[0] ? x:a->work[0];t=y>a->work[1] ? y:a->work[1];
        r=x+w;b=y+h;
        if (r>a->work[0]+a->work[2]) r=a->work[0]+a->work[2];
        if (b>a->work[1]+a->work[3]) b=a->work[1]+a->work[3];
        if (l<r && t<b) {
            a->points[0]=l;a->points[1]=t;a->points[2]=r-1;a->points[3]=b-1;
            vs_clip(a->vdi,1,a->points);
            if (direction==3) {
                transfer(l,t,l-a->work[0],t-a->work[1],r-l,b-t,NULL,&a->memory);
                transfer(l-a->work[0],t-a->work[1],l,t,r-l,b-t,&a->memory,NULL);
            } else if (direction==1 && b-t>8) {
                transfer(l,t+8,l,t,r-l,b-t-8,NULL,NULL);paint(l,b-8,r,b);
            } else if (direction==-1 && b-t>8) {
                transfer(l,t,l,t+8,r-l,b-t-8,NULL,NULL);paint(l,t,r,t+8);
            } else if (direction==2 && r-l>1) {
                transfer(l+1,t,l,t,r-l-1,b-t,NULL,NULL);paint(r-1,t,r,b);
            } else if (direction==-2 && r-l>1) {
                transfer(l,t,l+1,t,r-l-1,b-t,NULL,NULL);paint(l,t,l+1,b);
            } else paint(l,t,r,b);
        }
        if (okay) okay=wind_get(a->window,WF_NEXTXYWH,&x,&y,&w,&h);
    }
    if (!wind_update(END_UPDATE)) okay=0;
    return okay;
}

int main(int argc,char **argv)
{
    struct RasterApp *a=&GEMRaster;
    const WORD kind=NAME|CLOSER|MOVER;
    WORD i,x,y,w,h,cw,ch,bw,bh,events,mx,my,mb,ks,kr,br,quit=0,result=1;
    (void)argc;(void)argv;
    a->window=-1;a->id=appl_init();
    if (a->id<0) return 1;
    a->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) a->input[i]=1;
    a->input[9]=0;a->input[10]=2;v_opnvwk(a->input,&a->vdi,a->output);
    if (!a->vdi) goto finish;
    a->memory.fd_addr=malloc(14592);
    if (!a->memory.fd_addr) goto finish;
    a->memory.fd_w=304;a->memory.fd_h=96;a->memory.fd_wdwidth=19;
    a->memory.fd_stand=0;a->memory.fd_nplanes=4;
    a->memory.fd_r1=0;a->memory.fd_r2=0;a->memory.fd_r3=0;
    if (!wind_calc(WC_BORDER,kind,40,64,304,96,&x,&y,&w,&h)) goto finish;
    a->window=wind_create(kind,x,y,w,h);
    if (a->window<0 || !wind_set_str(a->window,WF_NAME,"Raster: Space run, M memory, Q quit")) goto finish;
    if (!wind_open(a->window,x,y,w,h)) goto finish;
    a->opened=1;
    if (!render(0)) goto finish;
    a->ready=1;result=0;
    while (!quit) {
        events=evnt_multi(MU_MESAG|MU_KEYBD|(a->running ? MU_TIMER:0),0,0,0,
            0,0,0,0,0,0,0,0,0,0,a->message,100,0,&mx,&my,&mb,&ks,&kr,&br);
        if (!events) { result=2;break; }
        if ((events&MU_MESAG) && a->message[3]==a->window) {
            switch (a->message[0]) {
            case WM_CLOSED:quit=1;break;
            case WM_TOPPED:wind_set(a->window,WF_TOP,0,0,0,0);break;
            case WM_MOVED:
                wind_set(a->window,WF_CURRXYWH,a->message[4],a->message[5],a->message[6],a->message[7]);
                if (!render(0)) result=2;
                break;
            case WM_REDRAW:if (!render(0)) result=2;break;
            }
        }
        if (!quit && (events&MU_KEYBD)) {
            if ((kr&255)=='q' || (kr&255)=='Q') quit=1;
            else if ((kr&255)==' ') a->running=!a->running;
            else if ((kr&255)=='m' || (kr&255)=='M') { if (!render(3)) result=2;++a->roundtrips; }
            else if ((kr&0xff00)==0x5000) { ++a->first;if (!render(1)) result=2;++a->scrolls; }
            else if ((kr&0xff00)==0x4800) { --a->first;if (!render(-1)) result=2;++a->scrolls; }
            else if ((kr&0xff00)==0x4d00 && a->left<64) { ++a->left;if (!render(2)) result=2;++a->shifts; }
            else if ((kr&0xff00)==0x4b00 && a->left>0) { --a->left;if (!render(-2)) result=2;++a->shifts; }
        }
        if (!quit && (events&MU_TIMER) && a->running) { ++a->first;if (!render(1)) result=2;++a->scrolls; }
        if (result) break;
    }
finish:
    a->ready=0;
    if (a->opened) wind_close(a->window);
    if (a->window>=0) wind_delete(a->window);
    if (a->memory.fd_addr) free(a->memory.fd_addr);
    if (a->vdi) v_clsvwk(a->vdi);
    appl_exit();
    return result;
}
