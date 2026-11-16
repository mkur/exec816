#include "../../c/calypsi/aes-private.h"
#include <proto/exec.h>
#include <clib/alib_protos.h>
#include <exec816/runtime.h>

ULONG AESService,AESUpdates,AESMouseHolds;
UWORD AESOwnedOffset;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,progress,phase,stopCounter;
volatile UWORD callbackReady,callbackX,callbackY;
volatile UWORD keyboardReady;
volatile ULONG keyboardInbox;
static OBJECT menu[]={
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,11},
    {1,3,3,G_IBOX,0,0,0,8,0,424,11},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Test",0,0,64,11},
    {0,5,5,G_IBOX,0,0,0,0,11,640,229},
    {4,6,6,G_BOX,0,0,0x1100,8,0,112,11},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Exit",0,0,112,11}
};
static struct Task *parent,*peer,*counter;
static struct TaskLease peerLease,counterLease;
#define DONE 0x10000UL
#define OTHER 0x80000UL
#define UPDATES (*(volatile UWORD *)AESUpdates)
#define MOUSE (*(volatile UWORD *)AESMouseHolds)

static UWORD owned(void)
{
    struct Task *task=FindTask(NULL);
    return *(UWORD *)((UBYTE *)(ULONG)task->tc_ExecPrivate+AESOwnedOffset);
}

static void Check(int okay)
{
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
}

void MigrationCounter(void)
{
    while (!stopCounter) { ++progress; ExecYield(); }
    Signal(parent,OTHER);
    Wait(0);
}

void MigrationPeer(void)
{
    struct ExecAESContext *c;
    UWORD before=owned();
    Check(AllocSignal(16)==16);
    Check(AllocSignal(19)==19);
    Check(ExecAESAttach((struct MsgPort *)AESService));
    Check(appl_init()>0);
    c=ExecAESContext();
    phase=1; Signal(parent,DONE);
    Wait(DONE);
    Check(!wind_update(BEG_CHECK|BEG_UPDATE) && c->diagnostic==AES_OK);
    phase=2; Signal(parent,DONE);
    Check(wind_update(BEG_UPDATE));
    Check(UPDATES==1 && c->updateDepth==1);
    Check(owned()==before+1);
    Check((SetSignal(0,OTHER)&OTHER)!=0);
    Check(wind_update(BEG_MCTRL));
    Check(MOUSE==1 && UPDATES==2 && c->mouseDepth==1);
    Check(wind_update(BEG_UPDATE));
    Check(wind_update(BEG_MCTRL));
    /* Cooperative departure balances nested holds in this owning Task. */
    Check(ExecAESDetach());
    Check(owned()==before);
    FreeSignal(16);FreeSignal(19);
    phase=3;Signal(parent,DONE);
    Wait(0);
}

static void nested(struct ExecAESContext *c)
{
    WORD control[5]={107,1,1,0,0},in[1],out[1],global[15]={0};
    AESPB pb={control,global,in,out,0,0};
    UWORD depth=UPDATES;
    ULONG sequence=c->sequence;
    Forbid();
    Check(wind_update(BEG_CHECK|BEG_UPDATE));
    in[0]=BEG_UPDATE;aes_call(&pb);Check(out[0]==1);
    Check(UPDATES==depth+2 && c->view->updates==depth+2);
    Check(wind_update(END_UPDATE));
    in[0]=END_UPDATE;aes_call(&pb);Check(out[0]==1);
    Check(UPDATES==depth && c->view->updates==depth);
    Check(c->sequence==sequence && FindTask(NULL)->tc_TDNestCnt==0);
    Permit();
}

WORD AESRun(void)
{
    struct ExecAESContext *c;
    UWORD previous,before;
    WORD window,message[8];
    parent=FindTask(NULL);before=owned();
    Check(AllocSignal(16)==16);Check(AllocSignal(19)==19);
    Check(ExecAESAttach((struct MsgPort *)AESService));
    Check(appl_init()>0);
    c=ExecAESContext();
    window=wind_create(NAME|CLOSER|MOVER|DNARROW|VSLIDE|HSLIDE,48,48,192,96);
    Check(window>0 && wind_open(window,48,48,192,96));
    callbackX=c->view->work.right+5;callbackY=c->view->work.bottom-5;
    callbackReady=1;
    do { Check(evnt_mesag(message)); } while (message[0]==WM_REDRAW);
    Check(message[0]==WM_ARROWED && message[3]==window);
    Check(wind_update(BEG_UPDATE));
    Check(wind_set(window,WF_VSLIDE,100,0,0,0));
    Check(wind_update(END_UPDATE));
    callbackReady=2;
    /* Ordinary key delivery must leave UPDATE free for its recipient. */
    keyboardInbox=(ULONG)c->endpoint->input;
    keyboardReady=1;
    Check((evnt_keybd()&255)=='a');
    Check(wind_update(BEG_CHECK|BEG_UPDATE));
    Check(owned()==before+1);
    Check(wind_update(END_UPDATE));
    keyboardReady=2;
    Check(wind_update(BEG_UPDATE));
    Check(UPDATES==1 && c->view->updates==1);
    Check(owned()==before+1);
    Check(wind_update(BEG_UPDATE));
    Check(UPDATES==2 && c->view->updates==2);
    Check(wind_update(END_UPDATE));
    Check(UPDATES==1 && c->view->updates==1);
    UPDATES=0xffff;
    Check(!appl_exit() && c->diagnostic==AES_OVERFLOW);
    Check(c->identity && c->endpoint->state==AES_ENDPOINT_ACCEPTING);
    Check(c->updateDepth==1 && UPDATES==0xffff);
    UPDATES=1;
    nested(c);
    Check(menu_bar(menu,1));
    Check(wind_set(window,WF_VSLIDE,250,0,0,0));
    Check(wind_set(window,WF_HSLIDE,500,0,0,0));
    Check(c->view->vslide==250 && c->view->hslide==500);
    previous=c->view->revision;
    Check(wind_set(window,WF_VSLIDE,250,0,0,0));
    Check(c->view->revision==previous && UPDATES==1);
    Check(wind_update(BEG_MCTRL));
    Check(UPDATES==2 && MOUSE==1 && c->view->updates==2);
    Check(wind_update(END_UPDATE));
    Check(UPDATES==1 && c->view->updates==1 && MOUSE==1);
    /* MCTRL by itself has the shared painting permission. */
    Check(wind_set(window,WF_HSLIDE,750,0,0,0));
    Check(c->view->hslide==750 && UPDATES==1 && c->view->updates==1);
    Forbid();
    peer=CreateTask("UPDATE contender",0,(APTR)MigrationPeer,1);
    counter=CreateTask("UPDATE counter",0,(APTR)MigrationCounter,1);
    Check(peer && counter);
    Check(RetainTask(peer,&peerLease));Check(RetainTask(counter,&counterLease));
    Permit();
    while (phase!=1) Wait(DONE);
    previous=progress;
    while (progress==previous) {} /* Actual preemption while UPDATE is owned. */
    Signal(peer,DONE);
    while (phase!=2) Wait(DONE);
    while (peer->tc_State!=TS_WAIT) ExecYield();
    Signal(peer,OTHER);
    Check(UPDATES==1 && MOUSE==1);
    Check(ExecAESDetach());
    Check(owned()==before);
    while (phase!=3) Wait(DONE);
    stopCounter=1;Wait(OTHER);
    Forbid();
    Check(ReleaseTask(&peerLease));RemTask(peer);
    Check(ReleaseTask(&counterLease));RemTask(counter);
    Permit();
    Check(!UPDATES && !MOUSE);
    FreeSignal(16);FreeSignal(19);
    return AESFailures;
}
