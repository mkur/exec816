#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
volatile UWORD AESPhysical,AESPhysicalGo;
ULONG AESMouse;
static struct Task *controller,*peer;
static ULONG wake,peerWake;
static volatile ULONG heartbeat;
static volatile UWORD heartbeatStop,heartbeatDone;

static void check(BOOL okay,UWORD line)
{
    Forbid();++AESChecks;
    if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=line; }
    Permit();
}
#define CHECK(t) check((t)!=0,__LINE__)

static void observe(UWORD phase)
{
    AESPhysical=phase;
    while (AESPhysicalGo!=phase) ExecYield();
}

void AESClientOne(void)
{
    BYTE bit=AllocSignal(-1);
    peerWake=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    CHECK(graf_mouse(M_OFF,NULL));
    AESReady=1;Signal(controller,wake);
    Wait(peerWake);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid();AESDone=1;Signal(controller,wake);RemTask(NULL);
}
void AESClientTwo(void)
{
    /* No voluntary yield: ordinary VBI preemption must keep the GUI running. */
    while (!heartbeatStop) ++heartbeat;
    Forbid();heartbeatDone=1;Signal(controller,wake);RemTask(NULL);
}

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct AESMouseState *mouse;
    struct Task *counter;
    ULONG available=AvailMem(0),revision,sequence;
    WORD x,y,buttons,qualifiers,h=0,window,i;
    WORD input[11],output[57],control[5]={78,1,1,1,0},global[15],in[1],out[1];
    LONG address[1]={0};
    AESPB pb={control,global,in,out,address,NULL};
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);controller=FindTask(NULL);wake=1UL<<bit;
    CHECK(!graf_mouse(M_OFF,NULL));
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);c=ExecAESContext();mouse=&c->directory->mouse;
    AESMouse=(ULONG)mouse;
    CHECK(sizeof(MFORM)==74);
    /* A context's filtered/frozen sample is not the shared query source. */
    Forbid();
    mouse->x=121;mouse->y=89;mouse->buttons=1;mouse->qualifiers=4;
    c->endpoint->input->latest.x=5;c->endpoint->input->latest.y=6;
    c->endpoint->input->selectedPointer.x=7;
    Permit();
    CHECK(graf_mkstate(&x,&y,&buttons,&qualifiers));
    CHECK(x==121 && y==89 && buttons==1 && qualifiers==4);
    CHECK(c->endpoint->input->latest.x==5 && c->endpoint->input->selectedPointer.x==7);
    Forbid();mouse->buttons=0;Permit();
    sequence=c->request.sequence;
    CHECK(graf_mouse(M_OFF,NULL));
    CHECK(mouse->depth==1 && !mouse->visible && mouse->completed==mouse->revision);
    observe(1);
    revision=mouse->revision;
    CHECK(graf_mouse(M_OFF,NULL));CHECK(mouse->revision==revision && mouse->depth==1);
    CHECK(graf_mouse((WORD)(M_FORCE|M_ON),NULL));CHECK(mouse->revision==revision && !mouse->visible);
    CHECK(graf_mouse(M_ON,NULL));CHECK(mouse->visible && !mouse->depth);
    observe(2);
    CHECK(graf_mouse(M_ON,NULL));CHECK(!mouse->depth);
    CHECK(c->request.sequence==sequence);
    revision=mouse->revision;
    CHECK(!graf_mouse(TEXT_CRSR,NULL) && ExecAESDiagnostic()==AES_UNSUPPORTED);
    CHECK(mouse->revision==revision);
    CHECK(graf_mouse(ARROW,NULL));
    in[0]=M_OFF;aes_call(&pb);CHECK(out[0]==1 && !mouse->visible);
    in[0]=M_ON;aes_call(&pb);CHECK(out[0]==1 && mouse->visible);
    control[3]=0;in[0]=M_OFF;aes_call(&pb);
    CHECK(out[0]==0 && ExecAESDiagnostic()==AES_MALFORMED && mouse->visible);
    control[3]=1;
    counter=CreateTask("Cursor background counter",1,(APTR)AESClientTwo,1024UL);
    CHECK(counter!=NULL);
    while (!heartbeat) ExecYield();
    peer=CreateTask("Mouse hide peer",1,(APTR)AESClientOne,1024UL);
    CHECK(peer!=NULL);while (!AESReady) Wait(wake);
    CHECK(!mouse->visible && mouse->depth==1);
    CHECK(graf_mouse(M_OFF,NULL));CHECK(graf_mouse(M_ON,NULL));
    CHECK(!mouse->visible && mouse->depth==1);
    CHECK(graf_mouse(M_ON,NULL));CHECK(!mouse->visible);
    Signal(peer,peerWake);while (!AESDone) Wait(wake);
    CHECK(mouse->visible && mouse->depth==0 && mouse->revision==mouse->completed);
    window=wind_create(NAME|CLOSER|MOVER,32,32,240,120);
    CHECK(window>0);CHECK(wind_open(window,32,32,240,120));
    /* Cold physical completion must not depend on releasing our own UPDATE. */
    CHECK(wind_update(BEG_UPDATE));
    CHECK(graf_mouse(M_OFF,NULL));CHECK(graf_mouse(M_ON,NULL));
    CHECK(wind_update(END_UPDATE));
    for (i=0;i<10;++i) input[i]=1;
    h=graf_handle(&x,&y,&buttons,&qualifiers);CHECK(h>0);
    input[10]=2;v_opnvwk(input,&h,output);CHECK(h>0);
    CHECK(wind_update(BEG_UPDATE));
    sequence=c->request.sequence;
    v_hide_c(h);CHECK(ExecAESDiagnostic()==AES_OK && mouse->depth==1);
    v_hide_c(h);CHECK(mouse->depth==2);
    CHECK(graf_mouse(M_OFF,NULL));CHECK(mouse->depth==3);
    v_show_c(h,1);CHECK(mouse->depth==2);
    CHECK(graf_mouse(M_ON,NULL));CHECK(mouse->depth==1);
    v_show_c(h,1);CHECK(mouse->depth==0 && mouse->visible);
    CHECK(graf_mouse(M_OFF,NULL));
    v_show_c(h,0);CHECK(mouse->visible && mouse->depth==0);
    CHECK(graf_mouse(M_ON,NULL));CHECK(mouse->visible && !mouse->depth);
    v_hide_c(h);Forbid();mouse->depth=0xffffffffUL;Permit();
    revision=mouse->revision;
    v_hide_c(h);CHECK(ExecAESDiagnostic()==AES_OVERFLOW);
    CHECK(mouse->depth==0xffffffffUL && mouse->revision==revision);
    Forbid();mouse->depth=1;Permit();v_show_c(h,1);
    CHECK(mouse->visible && ExecAESDiagnostic()==AES_OK);
    vq_mouse(h,&buttons,&x,&y);CHECK(ExecAESDiagnostic()==AES_OK);
    CHECK(x==mouse->x && y==mouse->y && buttons==mouse->buttons);
    CHECK(c->request.sequence==sequence);
    v_hide_c(h+1);CHECK(ExecAESDiagnostic()==AES_IDENTITY && mouse->visible);
    {
        WORD box[4]={80,64,199,119},strip[4]={80,64,199,71};
        WORD pxy[8]={80,64,199,111,80,72,199,119};
        MFDB screen={0};
        ULONG before=heartbeat;
        CHECK(graf_mouse(M_OFF,NULL));
        vsf_color(h,4);v_bar(h,box);
        vsf_color(h,3);v_bar(h,strip);
        vro_cpyfm(h,S_ONLY,pxy,&screen,&screen);
        vsf_color(h,2);v_bar(h,strip);
        CHECK(ExecAESDiagnostic()==AES_OK);
        observe(3);
        CHECK(graf_mouse(M_ON,NULL));
        observe(4);
        CHECK(heartbeat!=before);
    }
    CHECK(wind_update(END_UPDATE));
    CHECK(graf_mouse(M_OFF,NULL));
    v_clsvwk(h);CHECK(!mouse->visible && mouse->depth==1);
    CHECK(appl_exit());CHECK(mouse->visible && mouse->depth==0);
    CHECK(appl_init()>0);CHECK(graf_mouse(M_ON,NULL));
    heartbeatStop=1;while (!heartbeatDone) Wait(wake);
    CHECK(ExecAESDetach());FreeSignal(bit);
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
