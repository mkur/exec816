/* Exec window/event adapter for G4BENCH; GPL-2.0-or-later. */
#include <gem.h>
#include <exec816/aes.h>
#include <proto/dos.h>
#include "clock.h"

WORD g4b_ready,g4b_done,g4b_window,g4b_vdi,g4b_work[4];
ULONG g4b_reads;
struct BenchTick g4b_clock;
static struct BenchClock clock;
static WORD work_in[11]={1,1,1,1,1,1,1,1,1,1,2},work_out[57],message[8];

static WORD report(void)
{
    WORD x,y,w,h,clip[4],okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(g4b_window,WF_WORKXYWH,&g4b_work[0],&g4b_work[1],&g4b_work[2],&g4b_work[3]);
    if (okay) okay=wind_get(g4b_window,WF_FIRSTXYWH,&x,&y,&w,&h);
    while (okay && w && h) {
        clip[0]=x;clip[1]=y;clip[2]=x+w-1;clip[3]=y+h-1;
        vs_clip(g4b_vdi,1,clip);vsf_color(g4b_vdi,0);v_bar(g4b_vdi,clip);
        vst_color(g4b_vdi,1);
        v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+14,"G4BENCH - Exec816 subset");
        v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+30,"Clock ready; measurement cases pending.");
        v_gtext(g4b_vdi,g4b_work[0]+8,g4b_work[1]+46,"Return reads clock. Escape closes.");
        okay=ExecAESDiagnostic()==0 && wind_get(g4b_window,WF_NEXTXYWH,&x,&y,&w,&h);
    }
    if (!wind_update(END_UPDATE)) okay=0;
    return okay;
}

int main(void)
{
    WORD cw,ch,bw,bh,x,y,w,h,mx,my,mb,ks,kr,br,ev,quit=0,opened=0,result=1;
    g4b_window=-1;
    if (appl_init()<0) return 1;
    g4b_vdi=graf_handle(&cw,&ch,&bw,&bh);
    v_opnvwk(work_in,&g4b_vdi,work_out);
    if (!g4b_vdi) goto finish;
    if (!wind_calc(WC_BORDER,NAME|CLOSER|MOVER,80,56,480,160,&x,&y,&w,&h)) goto finish;
    g4b_window=wind_create(NAME|CLOSER|MOVER,x,y,w,h);
    if (g4b_window<0 || !wind_set_str(g4b_window,WF_NAME,"G4BENCH")) goto finish;
    if (!wind_open(g4b_window,x,y,w,h)) goto finish;
    opened=1;
    if (!BenchClockOpen(&clock) || !BenchClockRead(&clock,&g4b_clock)) goto finish;
    g4b_reads=1;g4b_ready=1;result=0;
    while (!quit) {
        ev=evnt_multi_moblk(MU_MESAG|MU_KEYBD,0,0,0,NULL,NULL,message,0,0,
                           &mx,&my,&mb,&ks,&kr,&br);
        if (!ev) { result=2;break; }
        if (ev&MU_KEYBD) {
            if ((kr&255)==27) quit=1;
            else if ((kr&255)==13) {
                if (!BenchClockRead(&clock,&g4b_clock)) { result=2;break; }
                ++g4b_reads;
            }
        }
        if ((ev&MU_MESAG) && message[3]==g4b_window) {
            switch (message[0]) {
            case WM_CLOSED:quit=1;break;
            case WM_TOPPED:
                if (!wind_set(g4b_window,WF_TOP,0,0,0,0)) result=2;
                break;
            case WM_MOVED:
                if (!wind_set(g4b_window,WF_CURRXYWH,message[4],message[5],message[6],message[7])) result=2;
                break;
            case WM_REDRAW:if (!report()) result=2;break;
            }
        }
        if (result) break;
    }
finish:
    g4b_ready=0;
    BenchClockClose(&clock);
    if (opened && wind_close(g4b_window)) opened=0;
    if (g4b_window>0 && !opened) wind_delete(g4b_window);
    if (g4b_vdi) v_clsvwk(g4b_vdi);
    if (!appl_exit()) result=3;
    if (result) {
        static const char failed[]="G4BENCH: could not open or complete the benchmark.\n";
        Write(Output(),failed,sizeof(failed)-1);
    }
    return result;
}
