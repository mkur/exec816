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
static volatile UWORD formPeer,formStage;
static MFORM peerForm;

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
    if (formPeer) {
        CHECK(graf_mouse(USER_DEF,&peerForm));
        CHECK(graf_mouse(M_SAVE,NULL));CHECK(graf_mouse(TEXT_CRSR,NULL));
        CHECK(graf_mouse(M_PREVIOUS,NULL));CHECK(graf_mouse(M_RESTORE,NULL));
        formStage=1;Signal(controller,wake);Wait(peerWake);
        CHECK(wind_update(BEG_MCTRL));
        CHECK(graf_mouse(USER_DEF,&peerForm));
        formStage=2;Signal(controller,wake);Wait(peerWake);
        CHECK(ExecAESDetach());
        FreeSignal(bit);
        Forbid();formStage=3;Signal(controller,wake);RemTask(NULL);
    }
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
    CHECK(!graf_mouse(8,NULL) && ExecAESDiagnostic()==AES_UNSUPPORTED);
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
    {
        static const WORD positions[8][2]={{0,0},{1,0},{639,0},{0,239},
            {639,239},{321,121},{320,120},{638,238}};
        ULONG allocation=(ULONG)AllocMem(65610UL,MEMF_PUBLIC|MEMF_LINEAR);
        MFORM *form=(MFORM *)(((allocation+65536UL)&0xffff0000UL)-32);
        WORD pen,pos,row,phase=6;
        ULONG prior;
        if ((ULONG)form<allocation) form=(MFORM *)((ULONG)form+65536UL);
        CHECK(allocation!=0);
        if (!allocation) return AESFailures;
        CHECK(((ULONG)form&65535UL)+sizeof(MFORM)>65536UL);
        CHECK(wind_update(BEG_UPDATE));CHECK(wind_update(BEG_MCTRL));
        CHECK(graf_mouse(M_OFF,NULL));observe(5);
        for (pen=0;pen<16;++pen) for (pos=0;pos<8;++pos) {
            form->mf_xhot=(pen+pos)&15;form->mf_yhot=(15-pen+pos)&15;
            form->mf_nplanes=1;form->mf_bg=pen;form->mf_fg=(pen+5)&15;
            for (row=0;row<16;++row) {
                form->mf_mask[row]=(WORD)((row&1) ? 0xaaaa:0x5555);
                form->mf_data[row]=(WORD)((pos&1) ? 0xcccc:0x3333);
            }
            Forbid();mouse->x=positions[pos][0];mouse->y=positions[pos][1];Permit();
            CHECK(graf_mouse(USER_DEF,form));
            /* Reuse the source before scanout; only the owned copy may survive. */
            for (row=0;row<37;++row) ((WORD *)form)[row]=0;
            if (phase==6) CHECK(graf_mouse(M_ON,NULL));
            CHECK(mouse->form.kind==USER_DEF && mouse->form.words[3]==pen);
            observe(phase++);
        }
        prior=mouse->revision;
        CHECK(!graf_mouse(USER_DEF,NULL) && ExecAESDiagnostic()==AES_MALFORMED);
        form->mf_nplanes=2;
        CHECK(!graf_mouse(USER_DEF,form) && ExecAESDiagnostic()==AES_UNSUPPORTED);
        CHECK(mouse->revision==prior);
        form->mf_nplanes=1;form->mf_xhot=16;
        CHECK(!graf_mouse(USER_DEF,form));CHECK(mouse->revision==prior);
        form->mf_xhot=0;form->mf_fg=-1;
        CHECK(!graf_mouse(USER_DEF,form));CHECK(mouse->revision==prior);
        form->mf_fg=1;form->mf_bg=9;form->mf_yhot=0;
        for (row=0;row<16;++row) { form->mf_mask[row]=-1;form->mf_data[row]=0; }
        vsc_form(h,(const WORD *)form);
        CHECK(ExecAESDiagnostic()==AES_OK && mouse->form.words[3]==9);
        observe(134);
        Forbid();mouse->x=121;mouse->y=89;++mouse->revision;Permit();
        CHECK(graf_mouse(M_ON,NULL));CHECK(mouse->form.words[3]==9);
        observe(135);
        CHECK(graf_mouse(ARROW,NULL));CHECK(mouse->form.kind==ARROW);
        observe(136);
        CHECK(graf_mouse(M_OFF,NULL));observe(137);
        CHECK(graf_mouse(M_ON,NULL));
        for (i=ARROW;i<=OUTLN_CROSS;++i) {
            CHECK(graf_mouse(i,NULL));CHECK(mouse->form.kind==i);
            observe(138+i);
        }
        prior=mouse->revision;
        CHECK(graf_mouse((WORD)(M_FORCE|OUTLN_CROSS),NULL));
        CHECK(mouse->revision==prior);
        CHECK(graf_mouse(BUSYBEE,NULL));CHECK(mouse->form.kind==HOURGLASS);
        observe(146);
        CHECK(graf_mouse(BUSY_BEE,NULL));CHECK(mouse->form.kind==HOURGLASS);
        CHECK(graf_mouse(ARROW,NULL));
        prior=mouse->revision;
        in[0]=M_SAVE;aes_call(&pb);CHECK(out[0]==1);
        CHECK(mouse->revision==prior);
        /* Save is metadata only: previous remains HOURGLASS, not ARROW. */
        in[0]=M_PREVIOUS;aes_call(&pb);CHECK(out[0]==1);
        CHECK(mouse->form.kind==HOURGLASS);observe(147);
        CHECK(graf_mouse(M_PREVIOUS,NULL));CHECK(mouse->form.kind==ARROW);
        observe(148);
        CHECK(graf_mouse(POINT_HAND,NULL));CHECK(graf_mouse(M_PREVIOUS,NULL));
        CHECK(mouse->form.kind==ARROW);
        CHECK(graf_mouse(M_PREVIOUS,NULL));CHECK(mouse->form.kind==POINT_HAND);
        observe(149);
        in[0]=M_RESTORE;aes_call(&pb);CHECK(out[0]==1);
        CHECK(mouse->form.kind==ARROW);observe(150);
        CHECK(graf_mouse(USER_DEF,form));CHECK(graf_mouse(M_SAVE,NULL));
        CHECK(graf_mouse(ARROW,NULL));
        form->mf_bg=6;vsc_form(h,(const WORD *)form);
        CHECK(mouse->form.words[3]==6);
        CHECK(graf_mouse(M_PREVIOUS,NULL));
        CHECK(mouse->form.kind==USER_DEF && mouse->form.words[3]==9);
        observe(151);
        CHECK(graf_mouse(M_RESTORE,NULL));CHECK(graf_mouse(ARROW,NULL));
        CHECK(graf_mouse(M_RESTORE,NULL));
        CHECK(mouse->form.kind==USER_DEF && mouse->form.words[3]==9);
        CHECK(graf_mouse(ARROW,NULL));
        FreeMem((APTR)allocation,65610UL);
        peerForm.mf_xhot=7;peerForm.mf_yhot=6;peerForm.mf_nplanes=1;
        peerForm.mf_fg=1;peerForm.mf_bg=9;
        for (row=0;row<16;++row) { peerForm.mf_mask[row]=-1;peerForm.mf_data[row]=0; }
        formPeer=1;
        peer=CreateTask("Inactive cursor peer",1,(APTR)AESClientOne,1024UL);
        CHECK(peer!=NULL);while (formStage<1) Wait(wake);
        CHECK(mouse->form.kind==ARROW);
        CHECK(wind_update(END_MCTRL));CHECK(wind_update(END_UPDATE));
        Signal(peer,peerWake);while (formStage<2) Wait(wake);
        CHECK(mouse->form.kind==USER_DEF && mouse->form.words[3]==9);
        CHECK(graf_mouse(TEXT_CRSR,NULL));
        CHECK(mouse->form.kind==USER_DEF && mouse->form.words[3]==9);
        CHECK(graf_mouse(M_SAVE,NULL));
        CHECK(graf_mouse((WORD)(M_FORCE|HOURGLASS),NULL));
        CHECK(mouse->form.kind==USER_DEF && mouse->form.words[3]==9);
        CHECK(graf_mouse(M_RESTORE,NULL));
        CHECK(mouse->form.kind==USER_DEF && mouse->form.words[3]==9);
        Signal(peer,peerWake);while (formStage<3) Wait(wake);
        CHECK(mouse->form.kind==ARROW);
    }
    CHECK(graf_mouse(M_OFF,NULL));
    v_clsvwk(h);CHECK(!mouse->visible && mouse->depth==1);
    CHECK(appl_exit());CHECK(mouse->visible && mouse->depth==0);
    CHECK(appl_init()>0);CHECK(graf_mouse(M_ON,NULL));
    CHECK(wind_update(BEG_MCTRL));
    CHECK(graf_mouse(M_RESTORE,NULL));CHECK(mouse->form.kind==ARROW);
    CHECK(graf_mouse(M_PREVIOUS,NULL));CHECK(mouse->form.kind==ARROW);
    CHECK(wind_update(END_MCTRL));
    heartbeatStop=1;while (!heartbeatDone) Wait(wake);
    CHECK(ExecAESDetach());FreeSignal(bit);
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
