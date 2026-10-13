/* Independent display checkpoints around the production donor workload. */
#define main ClockChecks
#include "g4bench_clock.c"
#undef main
#include <gem.h>
#include <exec816/aes.h>
#include "../../ports/gem4xe/apps/g4bench/workload.h"

WORD g4p_ready,g4p_stage;
static WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57],work[4];

static WORD paint(WORD vdi,WORD window,WORD row)
{
    WORD i,p[4],okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(window,WF_WORKXYWH,&work[0],&work[1],&work[2],&work[3]);
    if (okay) {
        BenchSetup(vdi,work,output[13]);
        p[0]=work[0];p[1]=work[1];p[2]=work[0]+479;p[3]=work[1]+159;
        vs_clip(vdi,1,p);vsf_color(vdi,0);v_bar(vdi,p);
        BenchClip(row,p);vs_clip(vdi,1,p);
        for (i=0;i<(row==4 ? 20:50);++i) {
            BenchDraw(row,i);
            if (ExecAESDiagnostic()) { okay=0;break; }
        }
    }
    if (!wind_update(END_UPDATE)) okay=0;
    return okay;
}

int main(void)
{
    WORD result=ClockChecks(),window=-1,vdi=0,cw,ch,bw,bh,x,y,w,h,row,ev;
    WORD msg[8],mx,my,mb,ks,kr,br,opened=0;
    if (result) return result;
    if (appl_init()<0) return 11;
    vdi=graf_handle(&cw,&ch,&bw,&bh);v_opnvwk(input,&vdi,output);
    if (!vdi) { result=12;goto finish; }
    if (!wind_calc(WC_BORDER,NAME|CLOSER|MOVER,80,56,480,160,&x,&y,&w,&h)) { result=13;goto finish; }
    window=wind_create(NAME|CLOSER|MOVER,x,y,w,h);
    if (window<0 || !wind_open(window,x,y,w,h)) { result=14;goto finish; }
    opened=1;
    for (row=0;row<5;++row) {
        if (!paint(vdi,window,row)) { result=15;break; }
        g4p_stage=row+1;g4p_ready=1;
        for (;;) {
            ev=evnt_multi_moblk(MU_MESAG|MU_KEYBD,0,0,0,NULL,NULL,msg,0,0,
                               &mx,&my,&mb,&ks,&kr,&br);
            if (!ev) { result=16;break; }
            if ((ev&MU_KEYBD) && (kr&255)==13) break;
            if ((ev&MU_MESAG) && msg[0]==WM_REDRAW && !paint(vdi,window,row)) { result=17;break; }
        }
        if (result) break;
    }
finish:
    g4p_ready=0;
    if (opened) wind_close(window);
    if (window>0) wind_delete(window);
    if (vdi) v_clsvwk(vdi);
    if (!appl_exit()) result=18;
    return result;
}
