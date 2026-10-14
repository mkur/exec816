#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService,AESLockCount;
static struct Task *scopeCaller;
static ULONG scopeWake;
static volatile UWORD scopeDone;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
volatile UWORD AESCachePhase,AESCacheGo,AESCacheRedraws;
WORD AESCacheWork[4];
static WORD window,vdi;
static UWORD otherRedraws;

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
    CHECK(ExecAESBeginUpdate(window));
    CHECK(wind_get(window,WF_WXYWH,&r[0],&r[1],&r[2],&r[3]));
    r[2]+=r[0]-1; r[3]+=r[1]-1;
    vs_clip(vdi,1,r); vsf_color(vdi,3); v_bar(vdi,r);
    CHECK(ExecAESDiagnostic()==AES_OK);
    if (!ExecAESContext()->view->pixelsReady) {
        CHECK(ExecAESPaintedChanges(window));
        CHECK(ExecAESContext()->request.paintCount==0);
    }
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
        if ((events&MU_MESAG) && message[0]==WM_REDRAW) {
            if (message[3]==window) ++redraws;
            else ++otherRedraws;
        }
    } while (events&MU_MESAG);
    return redraws;
}

static void patch(WORD dx,WORD pen,BOOL complete)
{
    WORD r[4],x,y,width,height;
    CHECK(ExecAESBeginUpdate(window));
    CHECK(wind_get(window,WF_WXYWH,&x,&y,&width,&height));
    x+=dx;y+=8;
    r[0]=x;r[1]=y;r[2]=x+15;r[3]=y+7;
    vs_clip(vdi,1,r);vsf_color(vdi,pen);v_bar(vdi,r);
    CHECK(ExecAESContext()->view->change.left==x &&
          ExecAESContext()->view->change.top==y &&
          ExecAESContext()->view->change.right==x+16 &&
          ExecAESContext()->view->change.bottom==y+8);
    CHECK(ExecAESDiagnostic()==AES_OK);
    if (complete) {
        CHECK(ExecAESContext()->view->pixelsReady);
        CHECK(ExecAESPaintedChanges(window));
    } else CHECK(ExecAESPainted(window,r[0],r[1],8,8));
    CHECK(wind_update(END_UPDATE));
}

static void wait_redraw(void)
{
    WORD message[8];
    do { evnt_mesag(message); }
    while (message[0]!=WM_REDRAW || message[3]!=window);
}

/* Make a scoped UPDATE wait behind a real mouse owner, then release it. */
void AESClientOne(void)
{
    CHECK(ExecAESAttach((struct MsgPort *)AESService)); CHECK(appl_init()>0);
    CHECK(wind_update(BEG_MCTRL)); Signal(scopeCaller,scopeWake);
    while (!*(volatile UBYTE *)AESLockCount) ExecYield();
    CHECK(wind_update(END_MCTRL)); CHECK(ExecAESDetach());
    scopeDone=1;RemTask(NULL);
}
void AESClientTwo(void) { RemTask(NULL); }

UWORD AESRun(void)
{
    WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57];
    WORD kind=NAME|CLOSER|MOVER|INFO|SIZER|UPARROW|DNARROW|VSLIDE,sibling,source,third;
    BYTE bit;
    struct AESWindowView *original,*other;
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
    /* A completed pure move preserves client pixels without a redraw. */
    AESCacheRedraws=drain(); CHECK(AESCacheRedraws==0);
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
    original=ExecAESContext()->view;
    sibling=wind_create(kind,320,32,128,96);CHECK(sibling>0);
    other=ExecAESContext()->view;
    bit=AllocSignal(-1);CHECK(bit>=0);scopeWake=1UL<<bit;scopeCaller=FindTask(NULL);
    CHECK(CreateTask("Scoped update blocker",0,(APTR)AESClientOne,1024UL)!=NULL);
    Wait(scopeWake);
    CHECK(ExecAESBeginUpdate(sibling));
    CHECK(!original->updates && other->updates==1);
    CHECK(wind_update(BEG_UPDATE));
    CHECK(!original->updates && other->updates==2);
    CHECK(wind_update(END_UPDATE)); CHECK(other->updates==1);
    CHECK(wind_update(END_UPDATE)); CHECK(!other->updates);
    while (!scopeDone) ExecYield();
    FreeSignal(bit);
    phase(15); /* An empty hidden sibling update must preserve our saved image. */
    CHECK(ExecAESBeginUpdate(window));CHECK(wind_update(END_UPDATE));
    phase(16); /* The same empty update still invalidates its own target. */
    /* Genuine exposure still requires an application repaint. */
    CHECK(wind_open(sibling,96,64,128,96));
    CHECK(wind_close(sibling));
    wait_redraw(); AESCacheRedraws=1+drain(); CHECK(AESCacheRedraws>0);
    paint();phase(17);
    CHECK(wind_close(window)); CHECK(wind_delete(window));
    window=wind_create(kind,64,48,248,152);CHECK(window>0);
    CHECK(wind_set(window,AES_WF_EXEC_PRESERVE,1,0,0,0));
    CHECK(wind_set_str(window,WF_NAME,"Preserved source"));
    CHECK(wind_open(window,64,48,248,152));wait_redraw();paint();phase(18);
    drain();CHECK(wind_open(sibling,96,64,128,96));CHECK(wind_close(sibling));
    phase(19);AESCacheRedraws=drain();CHECK(AESCacheRedraws==0);
    /* A fully hidden, model-only change must defeat preservation. */
    CHECK(wind_open(sibling,64,48,248,152));
    CHECK(ExecAESBeginUpdate(window));CHECK(ExecAESContext()->view->visibleCount==0);
    CHECK(wind_update(END_UPDATE));phase(20);
    CHECK(wind_close(sibling));wait_redraw();CHECK(drain()==0);paint();phase(21);
    /* Fill both fixed slots with other actual clients, then expose the miss. */
    source=window;window=sibling;
    CHECK(wind_open(window,320,24,128,96));wait_redraw();paint();phase(22);
    third=wind_create(kind,480,24,128,96);CHECK(third>0);window=third;
    CHECK(wind_open(window,480,24,128,96));wait_redraw();paint();phase(23);
    window=source;CHECK(wind_set(window,WF_TOP,0,0,0,0));
    wait_redraw();paint();phase(24);
    CHECK(wind_set(window,WF_CXYWH,360,48,248,152));drain();otherRedraws=0;phase(25);
    /* The host opens/closes Windows over both this preserved client and the
     * conventional third client. Only the latter receives menu exposure. */
    CHECK(drain()==0);CHECK(otherRedraws>0);
    CHECK(wind_close(third));CHECK(wind_delete(third));CHECK(wind_close(sibling));
    CHECK(wind_delete(sibling));
    CHECK(wind_close(window));
    /* Closed and iconified views have no drawing clips. Both bindings must
     * accept the logical change without publishing any painted pixels. */
    CHECK(ExecAESBeginUpdate(window));
    CHECK(!ExecAESContext()->view->shown && !ExecAESContext()->view->visibleCount);
    {
        WORD r[4]={AESCacheWork[0],AESCacheWork[1],AESCacheWork[0]+15,AESCacheWork[1]+7};
        OBJECT box={NIL,NIL,NIL,G_BOX,LASTOB,0,0x1170,0,0,16,8};
        box.ob_x=r[0];box.ob_y=r[1];
        vs_clip(vdi,1,r);v_bar(vdi,r);
        CHECK(ExecAESDiagnostic()==AES_OK && ExecAESContext()->view->changed);
        CHECK(objc_draw(&box,0,0,r[0],r[1],16,8));
        CHECK(ExecAESPaintedChanges(window));
        CHECK(ExecAESContext()->request.paintCount==0);
        CHECK(ExecAESPainted(window,r[0],r[1],16,8));
        CHECK(ExecAESContext()->request.paintCount==0);
    }
    CHECK(wind_update(END_UPDATE));
    CHECK(wind_open(window,360,48,248,152));wait_redraw();paint();phase(26);
    CHECK(wind_set_str(window,WF_INFO,"Frame saved"));phase(27);
    CHECK(wind_set_str(window,WF_INFO,"Frame saved"));phase(28);
    CHECK(wind_set(window,WF_VSLIDE,250,0,0,0));
    CHECK(wind_set(window,WF_VSLSIZE,400,0,0,0));phase(29);
    CHECK(wind_set(window,WF_VSLIDE,250,0,0,0));
    CHECK(wind_set(window,WF_VSLSIZE,400,0,0,0));phase(30);
    drain();sibling=wind_create(kind,360,48,248,152);CHECK(sibling>0);
    CHECK(wind_open(sibling,360,48,248,152));CHECK(wind_close(sibling));
    CHECK(wind_delete(sibling));phase(31);CHECK(drain()==0);
    CHECK(wind_close(window));CHECK(wind_delete(window));
    v_clsvwk(vdi); CHECK(appl_exit()); CHECK(ExecAESDetach());
    return AESFailures;
}
