/* Public menu lifetime, physical interaction and durable delivery checks. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <proto/dos.h>
#include "../../c/calypsi/aes-private.h"

ULONG AESService,AESMenuNext,AESMenuTree,AESMenuPeerTree;
volatile WORD AESMenuPhase,AESMenuGo,AESMenuMutation;
volatile WORD AESMenuActions[2],AESMenuItem[2];
volatile ULONG AESMenuClient;
volatile UWORD AESMenuCommand,AESMenuResult;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
static void check(WORD okay,WORD line)
{
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=line; }
}
#define CHECK(x) check((x)!=0,__LINE__)
static const OBJECT source[] = {
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,16},
    {1,3,8,G_IBOX,0,0,0,8,0,424,16},
    {8,-1,-1,G_TITLE,0,0,(ULONG)"Files",0,0,64,16},
    {0,5,9,G_IBOX,0,0,0,0,16,640,224},
    {9,6,7,G_BOX,0,0,0x1100,8,0,112,32},
    {7,-1,-1,G_STRING,0,0,(ULONG)"Open",0,0,112,16},
    {5,-1,-1,G_STRING,0,0,(ULONG)"Quit",0,16,112,16},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Extra",80,0,64,16},
    {4,10,10,G_BOX,0,0,0x1100,88,0,96,16},
    {9,-1,-1,G_STRING,LASTOB,0,(ULONG)"About",0,0,96,16}
};
static WORD produce(WORD command)
{
    struct ExecAESContext *c=ExecAESContext();
    AESMenuClient=c->identity;AESMenuCommand=command;
    Signal(c->directory->owner,c->directory->mask);
    while (AESMenuCommand) Wait(1UL<<c->receiving->mp_SigBit);
    return AESMenuResult;
}
static WORD poll(WORD *words)
{
    WORD mx,my,mb,ks,kr,br;
    return evnt_multi(MU_MESAG|MU_TIMER,0,0,0,0,0,0,0,0,0,0,0,0,0,
        words,0,0,&mx,&my,&mb,&ks,&kr,&br)&MU_MESAG;
}
static void receive(WORD *words,WORD kind)
{
    for (;;) {
        CHECK(evnt_mesag(words));
        if (words[0]==kind) return;
        CHECK(words[0]==WM_REDRAW);
        if (words[0]!=WM_REDRAW) return;
    }
}
static struct Task *controller,*peer;
static ULONG wake,peerWake,peerGeneration;
static volatile WORD peerReady,peerDone,peerFinish;
static void phase(WORD value)
{
    AESMenuPhase=value;
    while (AESMenuGo<value) evnt_timer(20,0);
}
static void interact(OBJECT *tree,WORD who)
{
    WORD words[8];
    if (poll(words)) {
        if (words[0]==MN_SELECTED) {
            CHECK(words[1]==0 && words[2]==0 && words[3]==3 && words[7]==5);
            CHECK((((ULONG)(UWORD)words[5]<<16)|(UWORD)words[6])==(ULONG)tree);
            CHECK(words[4]==6 || words[4]==7);
            AESMenuItem[who]=words[4];++AESMenuActions[who];
            CHECK(menu_tnormal(tree,words[3],1));
        } else if (words[0]==WM_TOPPED) {
            CHECK(wind_set(words[3],WF_TOP,0,0,0,0));
        } else CHECK(words[0]==WM_REDRAW);
    }
    if (!who && AESMenuMutation) {
        WORD action=AESMenuMutation;
        if (action==1 || action==2) CHECK(menu_ienable(tree,6,action==2));
        else if (action==3) CHECK(menu_bar(tree,1));
        else if (action==4) { CHECK(menu_ienable(tree,6,0));CHECK(menu_ienable(tree,7,0)); }
        else if (action==5) { CHECK(menu_ienable(tree,6,1));CHECK(menu_ienable(tree,7,1)); }
        AESMenuMutation=0;
    }
    evnt_timer(20,0);
}
static void interactive(OBJECT *tree,WORD value)
{
    AESMenuPhase=value;
    while (AESMenuGo<value) interact(tree,0);
}
static void public_pb(OBJECT *tree)
{
    WORD control[5]={30,1,1,1,0},global[15],args[2]={1,0},reply[1];
    LONG address=(LONG)(ULONG)tree;
    AESPB pb={control,global,args,reply,&address,0};
    aes_call(&pb);CHECK(reply[0] && ExecAESContext()->menuTree==(ULONG)tree);
    control[1]=2;aes_call(&pb);CHECK(!reply[0] && ExecAESDiagnostic()==AES_MALFORMED);
    CHECK(ExecAESContext()->menuTree==(ULONG)tree);
}
static void visual(OBJECT *tree)
{
    WORD i;
    AESMenuTree=(ULONG)tree;
    public_pb(tree);interactive(tree,1);
    produce(3);phase(2);
    CHECK(menu_ienable(tree,6,0));
    CHECK(menu_text(tree,7,"Leave"));
    interactive(tree,3);
    CHECK(menu_bar(tree,0));
    for (i=0;i<sizeof(source)/sizeof(source[0]);++i) tree[i].ob_spec=0xffffffffUL;
    phase(4);
    Signal(peer,peerWake);
    while (peerReady<2) Wait(wake);
    interactive(tree,5);
    produce(3);phase(6);
    peerFinish=1;
    while (!peerDone) Wait(wake);
    phase(7);
    for (i=0;i<sizeof(source)/sizeof(source[0]);++i) tree[i]=source[i];
    CHECK(menu_bar(tree,1));
}
static void command(OBJECT *tree)
{
    WORD words[8],i;
    struct ExecAESContext *c=ExecAESContext();
    while (poll(words)) {}
    CHECK(produce(1));
    CHECK(!produce(1));
    CHECK(c->endpoint->menuConsumed==0);
    CHECK(menu_tnormal(tree,3,1)); /* Normalize before consumption. */
    CHECK(!produce(1));
    receive(words,MN_SELECTED);
    CHECK(words[0]==MN_SELECTED && words[1]==0 && words[2]==0);
    CHECK(words[3]==3 && words[4]==6 && words[7]==5);
    CHECK((((ULONG)(UWORD)words[5]<<16)|(UWORD)words[6])==(ULONG)tree);
    CHECK(c->endpoint->menuConsumed && c->endpoint->menuNormal);
    CHECK(produce(1));
    receive(words,MN_SELECTED); /* Consume before normalization. */
    CHECK(words[0]==MN_SELECTED);
    CHECK(c->endpoint->menuConsumed);
    CHECK(!produce(1));
    CHECK(menu_tnormal(tree,3,1));
    CHECK(c->endpoint->menuNormal);
    CHECK(produce(1));
    /* Replacement invalidates the immutable published record. */
    CHECK(menu_bar(tree,1));
    CHECK(!poll(words));
    CHECK(c->endpoint->guiFree);
    CHECK(produce(1));
    CHECK(menu_bar(tree,1));
    CHECK(produce(1)); /* Old GUI record still occupies the destination slot. */
    (void)ExecAESMessageReady(c);
    CHECK(!c->endpoint->menuConsumed); /* Recycling old cannot ack new. */
    receive(words,MN_SELECTED);
    CHECK(menu_tnormal(tree,3,1));
    for (i=0;i<16;++i) { words[0]=i;CHECK(appl_write(c->gemId,16,words)); }
    CHECK(produce(1));
    CHECK(!appl_write(c->gemId,16,words));
    CHECK(c->endpoint->freeRecords==0);
    produce(2);
    for (i=0;i<16;++i) { CHECK(evnt_mesag(words));CHECK(words[0]==i); }
    receive(words,MN_SELECTED);
    receive(words,WM_CLOSED);
    CHECK(menu_tnormal(tree,3,1));
    CHECK(produce(1));
    receive(words,MN_SELECTED);
    for (i=0;i<8;++i) c->deferredMessage[i]=words[i];
    c->deferredEpoch=c->messageEpoch;c->deferredMenuEpoch=c->messageMenuEpoch;
    c->messagePending=1;
    CHECK(menu_bar(tree,1));
    CHECK(!poll(words) && !c->messagePending);
    /* Same public words in an ordinary message are deliberately opaque. */
    CHECK(appl_write(c->gemId,16,words));
    CHECK(menu_bar(tree,1));
    CHECK(evnt_mesag(words) && words[0]==MN_SELECTED);
    CHECK(c->messageEpoch==0 && c->messageMenuEpoch==0);
    CHECK(produce(1)); /* Caller will close with this record still queued. */
}
static const char launchLabel[]="Launch";
void AESClientOne(void) {}
void AESClientTwo(void)
{
    WORD window;
    BYTE bit=AllocSignal(-1);
    OBJECT *tree;
    peerWake=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    CHECK(rsrc_load("D1:MENU.RSC"));
    CHECK(rsrc_gaddr(R_TREE,0,(void **)&tree));
    AESMenuPeerTree=(ULONG)tree;
    CHECK(menu_bar(tree,1));
    window=wind_create(NAME|CLOSER|MOVER,280,80,176,112);
    CHECK(window>0 && wind_open(window,280,80,176,112));
    peerGeneration=ExecAESContext()->endpoint->menuEpoch;
    peerReady=1;Signal(controller,wake);
    Wait(peerWake);
    CHECK(wind_set(window,WF_TOP,0,0,0,0));
    peerReady=2;Signal(controller,wake);
    while (!peerFinish) interact(tree,1);
    CHECK(wind_close(window) && wind_delete(window));
    CHECK(menu_bar(tree,0));
    CHECK(rsrc_free());
    CHECK(appl_exit());
    CHECK(ExecAESDetach());
    CHECK(ExecDOSDetach());
    FreeSignal(bit);
    Forbid();peerDone=1;Signal(controller,wake);RemTask(NULL);
}
UWORD AESRun(void)
{
    ULONG available,generation;
    BPTR file=Open("D1:MENU.RSC",MODE_OLDFILE);
    struct ExecAESContext *c;
    OBJECT *tree;
    WORD i,round,window,words[8];
    BYTE bit;
    OBJECT *candidate;
    CHECK(file && Close(file));CHECK(ExecDOSDetach());available=AvailMem(0);
    tree=AllocMem(sizeof(source),MEMF_PUBLIC);
    candidate=AllocMem(sizeof(source),MEMF_PUBLIC);bit=AllocSignal(-1);
    controller=FindTask(NULL);wake=1UL<<bit;
    peer=CreateTask("Menu peer",0,(APTR)AESClientTwo,1024UL);
    CHECK(peer!=0);
    while (!peerReady) Wait(wake);
    CHECK(tree!=0 && (ULONG)tree>65535);
    for (round=0;round<3;++round) {
        for (i=0;i<sizeof(source)/sizeof(source[0]);++i) tree[i]=source[i];
        CHECK(ExecAESAttach((struct MsgPort *)AESService));
        CHECK(appl_init()>0);
        c=ExecAESContext();
        CHECK(menu_bar(tree,1)); /* Before a window exists. */
        generation=c->endpoint->menuEpoch;
        CHECK(generation!=0 && generation!=peerGeneration && c->menuTree==(ULONG)tree);
        CHECK(wind_update(BEG_UPDATE));
        CHECK(menu_ienable(tree,6,0));
        CHECK(tree[6].ob_state&DISABLED);
        CHECK(menu_ienable(tree,6,1));
        CHECK(!(tree[6].ob_state&DISABLED));
        CHECK(menu_text(tree,6,launchLabel));
        CHECK(tree[6].ob_spec==(ULONG)launchLabel);
        CHECK(wind_update(END_UPDATE));
        CHECK(wind_update(BEG_MCTRL));
        CHECK(menu_tnormal(tree,3,0));
        CHECK(tree[3].ob_state&SELECTED);
        CHECK(menu_tnormal(tree,3,1));
        CHECK(!(tree[3].ob_state&SELECTED));
        CHECK(wind_update(END_MCTRL));
        CHECK(!menu_bar(tree,2));
        CHECK(c->endpoint->menuEpoch==generation);
        for (i=0;i<sizeof(source)/sizeof(source[0]);++i) candidate[i]=source[i];
        candidate[3].ob_type=G_BUTTON;
        CHECK(!menu_bar(candidate,1));
        CHECK(c->endpoint->menuEpoch==generation);
        candidate[3].ob_type=G_TITLE;
        candidate[5].ob_height=225;
        CHECK(!menu_bar(candidate,1));
        CHECK(c->endpoint->menuEpoch==generation);
        CHECK(menu_bar(tree,1));
        CHECK(c->endpoint->menuEpoch>generation);
        generation=c->endpoint->menuEpoch;
        window=wind_create(NAME|CLOSER|MOVER,16,32,160,96);
        CHECK(window>0);
        CHECK(wind_open(window,16,32,160,96));
        if (!round) { visual(tree);command(tree);generation=c->endpoint->menuEpoch; }
        CHECK(wind_close(window));
        CHECK(c->endpoint->menuEpoch==generation);
        CHECK(wind_open(window,16,32,160,96));
        if (!round) while (poll(words)) CHECK(words[0]!=MN_SELECTED);
        CHECK(wind_close(window));
        CHECK(wind_delete(window));
        *(ULONG *)AESMenuNext=0;
        CHECK(!menu_bar(tree,1));
        CHECK(ExecAESDiagnostic()==AES_OVERFLOW);
        CHECK(c->endpoint->menuEpoch==generation);
        *(ULONG *)AESMenuNext=generation+1;
        CHECK(wind_update(BEG_UPDATE));
        CHECK(menu_bar(tree,0));
        CHECK(c->endpoint->menuEpoch==0 && c->menuTree==0);
        CHECK(wind_update(END_UPDATE));
        /* An invalidated tree must no longer be read even on later turns. */
        for (i=0;i<sizeof(source)/sizeof(source[0]);++i) tree[i].ob_spec=0xffffffffUL;
        CHECK(evnt_timer(20,0));
        CHECK(appl_exit());
        CHECK(ExecAESDetach());
    }
    CHECK(peerDone);
    FreeSignal(bit);
    FreeMem(candidate,sizeof(source));
    FreeMem(tree,sizeof(source));
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
