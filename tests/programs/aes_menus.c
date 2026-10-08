/* Registration foundation: private transport until public input lands in AM4. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include "../../c/calypsi/aes-private.h"

ULONG AESService,AESMenuNext;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
static void check(WORD okay)
{
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
}
#define CHECK(x) check((x)!=0)
static const OBJECT source[] = {
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,16},
    {1,3,3,G_IBOX,0,0,0,8,0,424,16},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Files",0,0,64,16},
    {0,5,5,G_IBOX,0,0,0,0,16,640,224},
    {4,6,7,G_BOX,0,0,0x1100,8,0,112,32},
    {7,-1,-1,G_STRING,0,0,(ULONG)"Open",0,0,112,16},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Quit",0,16,112,16}
};
static const char launchLabel[]="Launch";
static struct Task *controller,*peer;
static ULONG wake,peerWake,peerGeneration;
static volatile WORD peerReady,peerDone;
void AESClientOne(void) {}
void AESClientTwo(void)
{
    WORD i;
    BYTE bit=AllocSignal(-1);
    OBJECT *tree=AllocMem(sizeof(source),MEMF_PUBLIC);
    peerWake=1UL<<bit;
    for (i=0;i<8;++i) tree[i]=source[i];
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    CHECK(ExecAESMenu(tree,30,1,0));
    peerGeneration=ExecAESContext()->endpoint->menuEpoch;
    peerReady=1;Signal(controller,wake);
    Wait(peerWake);
    /* Exit must withdraw even though this registration never had a window. */
    CHECK(appl_exit());
    for (i=0;i<8;++i) tree[i].ob_spec=0xffffffffUL;
    FreeMem(tree,sizeof(source));
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid();peerDone=1;Signal(controller,wake);RemTask(NULL);
}
UWORD AESRun(void)
{
    ULONG available=AvailMem(0),generation;
    struct ExecAESContext *c;
    OBJECT *tree=AllocMem(sizeof(source),MEMF_PUBLIC);
    WORD i,round,window;
    BYTE bit=AllocSignal(-1);
    OBJECT *candidate=AllocMem(sizeof(source),MEMF_PUBLIC);
    controller=FindTask(NULL);wake=1UL<<bit;
    peer=CreateTask("Menu peer",0,(APTR)AESClientTwo,1024UL);
    CHECK(peer!=0);
    while (!peerReady) Wait(wake);
    CHECK(tree!=0 && (ULONG)tree>65535);
    for (round=0;round<3;++round) {
        for (i=0;i<8;++i) tree[i]=source[i];
        CHECK(ExecAESAttach((struct MsgPort *)AESService));
        CHECK(appl_init()>0);
        c=ExecAESContext();
        CHECK(ExecAESMenu(tree,30,1,0)); /* Before a window exists. */
        generation=c->endpoint->menuEpoch;
        CHECK(generation!=0 && generation!=peerGeneration && c->menuTree==(ULONG)tree);
        CHECK(wind_update(BEG_UPDATE));
        CHECK(ExecAESMenu(tree,32,6,0));
        CHECK(tree[6].ob_state&DISABLED);
        CHECK(ExecAESMenu(tree,32,6,1));
        CHECK(!(tree[6].ob_state&DISABLED));
        CHECK(ExecAESMenu(tree,34,6,(ULONG)launchLabel));
        CHECK(tree[6].ob_spec==(ULONG)launchLabel);
        CHECK(wind_update(END_UPDATE));
        CHECK(wind_update(BEG_MCTRL));
        CHECK(ExecAESMenu(tree,33,3,0));
        CHECK(tree[3].ob_state&SELECTED);
        CHECK(ExecAESMenu(tree,33,3,1));
        CHECK(!(tree[3].ob_state&SELECTED));
        CHECK(wind_update(END_MCTRL));
        CHECK(!ExecAESMenu(tree,30,2,0));
        CHECK(c->endpoint->menuEpoch==generation);
        for (i=0;i<8;++i) candidate[i]=source[i];
        candidate[3].ob_type=G_BUTTON;
        CHECK(!ExecAESMenu(candidate,30,1,0));
        CHECK(c->endpoint->menuEpoch==generation);
        candidate[3].ob_type=G_TITLE;
        candidate[5].ob_height=225;
        CHECK(!ExecAESMenu(candidate,30,1,0));
        CHECK(c->endpoint->menuEpoch==generation);
        CHECK(ExecAESMenu(tree,30,1,0));
        CHECK(c->endpoint->menuEpoch>generation);
        generation=c->endpoint->menuEpoch;
        window=wind_create(NAME|CLOSER|MOVER,16,32,160,96);
        CHECK(window>0);
        CHECK(wind_open(window,16,32,160,96));
        CHECK(wind_close(window));
        CHECK(c->endpoint->menuEpoch==generation);
        CHECK(wind_open(window,16,32,160,96));
        CHECK(wind_close(window));
        CHECK(wind_delete(window));
        *(ULONG *)AESMenuNext=0;
        CHECK(!ExecAESMenu(tree,30,1,0));
        CHECK(ExecAESDiagnostic()==AES_OVERFLOW);
        CHECK(c->endpoint->menuEpoch==generation);
        *(ULONG *)AESMenuNext=generation+1;
        CHECK(wind_update(BEG_UPDATE));
        CHECK(ExecAESMenu(tree,30,0,0));
        CHECK(c->endpoint->menuEpoch==0 && c->menuTree==0);
        CHECK(wind_update(END_UPDATE));
        /* An invalidated tree must no longer be read even on later turns. */
        for (i=0;i<8;++i) tree[i].ob_spec=0xffffffffUL;
        CHECK(evnt_timer(20,0));
        CHECK(appl_exit());
        CHECK(ExecAESDetach());
    }
    Signal(peer,peerWake);
    while (!peerDone) Wait(wake);
    FreeSignal(bit);
    FreeMem(candidate,sizeof(source));
    FreeMem(tree,sizeof(source));
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
