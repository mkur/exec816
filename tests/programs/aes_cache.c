#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
volatile UWORD AESCachePhase,AESCacheGo,AESCacheRedraws;
WORD AESCacheWork[4];
static WORD window,vdi;

static void check(BOOL okay)
{
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
}
#define CHECK(t) check((t)!=0)

static void phase(UWORD value)
{
    CHECK(wind_get(window,WF_WXYWH,&AESCacheWork[0],&AESCacheWork[1],
                   &AESCacheWork[2],&AESCacheWork[3]));
    AESCachePhase=value;
    while (AESCacheGo<value) ExecYield();
}

static void paint(void)
{
    WORD r[4];
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_get(window,WF_WXYWH,&r[0],&r[1],&r[2],&r[3]));
    r[2]+=r[0]-1; r[3]+=r[1]-1;
    vs_clip(vdi,1,r); vsf_color(vdi,3); v_bar(vdi,r);
    CHECK(ExecAESDiagnostic()==AES_OK);
    CHECK(ExecAESPainted(window,r[0],r[1],r[2]-r[0]+1,r[3]-r[1]+1));
    CHECK(wind_update(END_UPDATE));
}

static UWORD drain(void)
{
    WORD message[8],mx,my,buttons,mod,key,clicks,events;
    UWORD redraws=0;
    do {
        events=evnt_multi(MU_MESAG|MU_TIMER,0,0,0,
            0,0,0,0,0,0,0,0,0,0,message,0,0,&mx,&my,&buttons,&mod,&key,&clicks);
        if ((events&MU_MESAG) && message[0]==WM_REDRAW && message[3]==window) ++redraws;
    } while (events&MU_MESAG);
    return redraws;
}

static void patch(WORD dx,WORD pen,BOOL complete)
{
    WORD r[4],x,y,width,height;
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_get(window,WF_WXYWH,&x,&y,&width,&height));
    x+=dx;y+=8;
    r[0]=x;r[1]=y;r[2]=x+15;r[3]=y+7;
    vs_clip(vdi,1,r);vsf_color(vdi,pen);v_bar(vdi,r);
    CHECK(ExecAESContext()->view->change.left==x &&
          ExecAESContext()->view->change.top==y &&
          ExecAESContext()->view->change.right==x+16 &&
          ExecAESContext()->view->change.bottom==y+8);
    CHECK(ExecAESDiagnostic()==AES_OK);
    CHECK(ExecAESPainted(window,r[0],r[1],complete?16:8,8));
    CHECK(wind_update(END_UPDATE));
}

static void wait_redraw(void)
{
    WORD message[8];
    do { evnt_mesag(message); }
    while (message[0]!=WM_REDRAW || message[3]!=window);
}

void AESClientOne(void) { RemTask(NULL); }
void AESClientTwo(void) { RemTask(NULL); }

UWORD AESRun(void)
{
    WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57];
    WORD kind=NAME|CLOSER|MOVER|INFO|SIZER|UPARROW|DNARROW|VSLIDE;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    vdi=1; v_opnvwk(input,&vdi,output); CHECK(vdi>0);
    window=wind_create(kind,32,32,240,144); CHECK(window>0);
    CHECK(wind_set_str(window,WF_NAME,"Cache source"));
    CHECK(wind_open(window,32,32,240,144));
    wait_redraw();
    paint(); phase(1);
    drain();
    CHECK(wind_set_str(window,WF_NAME,"Same pixels")); phase(2);
    CHECK(wind_set(window,WF_CXYWH,48,48,240,144)); phase(3);
    /* Restored pixels must not replace the application's exposure message. */
    AESCacheRedraws=drain(); CHECK(AESCacheRedraws>0);
    paint(); phase(4);
    /* No drawing report cannot certify an invisible model change. */
    CHECK(wind_update(BEG_UPDATE)); CHECK(wind_update(END_UPDATE)); phase(5);
    paint(); phase(6);
    CHECK(wind_set(window,WF_CXYWH,49,48,240,144)); phase(7);
    CHECK(wind_set(window,WF_CXYWH,48,48,248,152)); phase(8);
    drain();paint();phase(9);
    patch(8,4,1);phase(10);
    patch(32,5,1);phase(11);
    CHECK(wind_set(window,WF_CXYWH,64,48,248,152));phase(12);
    drain();patch(56,6,0);phase(13);
    paint();phase(14);
    CHECK(wind_close(window)); CHECK(wind_delete(window));
    v_clsvwk(vdi); CHECK(appl_exit()); CHECK(ExecAESDetach());
    return AESFailures;
}
