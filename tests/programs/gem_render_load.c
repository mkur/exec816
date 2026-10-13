/* Development-only public GEM load for matched rendering/feedback traces. */
#include <gem.h>
#include <exec816/aes.h>

volatile UWORD RenderMode,RenderReady,RenderBusy,RenderPhase,RenderFailed;
volatile ULONG RenderCalls[7];
static WORD handle,window;
static char text[81];

/* Same marker name as G4BENCH; the observer reads the mode argument and pairs
 * the actual call return using the native stack. No guest clock calls. */
void BenchDraw(UWORD mode)
{
    WORD rect[4];
    if (!wind_update(BEG_UPDATE)) { RenderFailed=1;return; }
    if (mode<=4) {
        UWORD count=mode==1 || mode==3 ? 64:mode==2 ? 80:79;
        char saved=text[count];
        text[count]=0;vst_color(handle,4);
        v_gtext(handle,mode>=3 ? 9:8,230,text);
        text[count]=saved;
    } else {
        rect[0]=mode==6 ? 9:8;rect[1]=160;
        rect[2]=mode==6 ? 108:107;rect[3]=209;
        vsf_color(handle,4);v_bar(handle,rect);
    }
    if (!wind_update(END_UPDATE) || ExecAESDiagnostic()!=AES_OK) RenderFailed=2;
}

int main(void)
{
    WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57],msg[8];
    WORD events,mx,my,mb,ks,kr,br,quit=0,i,clip[4]={8,160,631,231};
    UWORD mode,last=0xffff;
    if (appl_init()<0) return 1;
    handle=1;v_opnvwk(input,&handle,output);if (!handle) return 2;
    window=wind_create(NAME|CLOSER|MOVER,0,0,640,96);
    if (window<0 || !wind_set_str(window,WF_NAME,"GEM render load") || !wind_open(window,0,144,640,96)) return 3;
    for (i=0;i<80;++i) text[i]='A'+i%26;text[80]=0;
    vs_clip(handle,1,clip);RenderReady=1;
    while (!quit && !RenderFailed) {
        events=evnt_multi(MU_MESAG|MU_TIMER,0,0,0,0,0,0,0,0,0,0,0,0,0,msg,10,0,&mx,&my,&mb,&ks,&kr,&br);
        if (!events) { RenderFailed=3;break; }
        if ((events&MU_MESAG) && msg[3]==window) {
            if (msg[0]==WM_CLOSED) quit=1;
            if (msg[0]==WM_TOPPED) wind_set(window,WF_TOP,0,0,0,0);
        }
        mode=RenderMode;
        if (!quit && mode!=last) {
            if (!wind_update(BEG_UPDATE)) { RenderFailed=4;break; }
            vsf_color(handle,0);v_bar(handle,clip);wind_update(END_UPDATE);
            last=mode;RenderPhase=mode;
        }
        if (!quit && mode) { RenderBusy=1;BenchDraw(mode);++RenderCalls[mode];RenderBusy=0; }
    }
    RenderReady=0;
    wind_close(window);wind_delete(window);v_clsvwk(handle);appl_exit();
    return RenderFailed;
}
