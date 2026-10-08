#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include "../../c/calypsi/vdi-private.h"

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
volatile UWORD VDIPhase,VDIGo,VDIStage[2],VDICommand[2],VDIUnits[2];
static struct Task *root,*tasks[2];
static ULONG wake,starts[2];
static char longText[193];
static WORD wordText[2][40];
static WORD grafControl[2][5]={{77,0,5,0,0},{77,0,5,0,0}};
static WORD grafGlobal[2][15],grafOut[2][5];
static const WORD input[11]={1,1,1,1,1,1,1,1,1,1,2};

static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
    Permit();
}
#define CHECK(t) check((t)!=0)

/* Injected after backend attributes have been selected, while display access
 * is owned. Only the first unit per Task deliberately yields. */
void VDIYield(void)
{
    UWORD who=FindTask(NULL)==tasks[0] ? 0:1;
    ++VDIUnits[who];
    if (VDIUnits[who]==1) ExecYield();
}

static void draw(UWORD who,WORD handle,WORD window)
{
    WORD huge[4]={-300,-300,1000,1000};
    WORD clip[4],outside[4]={-8,-8,-1,-1};
    WORD x,y,w,h;
    struct ExecAESContext *c=ExecAESContext();
    ULONG sequence;
    WORD control[12]={0,0,0,0,0,0,0,0,0,0,0,0},points[2];
    VDIPB pb={control,wordText[who],points,NULL,NULL};
    UWORD i;
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_get(window,WF_WXYWH,&x,&y,&w,&h));
    sequence=c->sequence;
    CHECK(c->workstation->fillColor==(who ? 2:4));
    vs_clip(handle,0,huge);
    v_bar(handle,huge); CHECK(ExecAESDiagnostic()==AES_OK);
    clip[0]=x+8; clip[1]=y+8; clip[2]=x+78; clip[3]=y+18;
    vs_clip(handle,1,clip);
    CHECK(vsf_color(handle,3)==3);
    v_bar(handle,huge);
    CHECK(vst_color(handle,who ? 6:1)==(who ? 6:1));
    v_gtext(handle,x+4,y+15,"ABCDEFGHIJKLMN");
    vs_clip(handle,0,huge);
    v_gtext(handle,x-140*8,y+30,longText);
    CHECK(ExecAESDiagnostic()==AES_OK);
    for (i=0;i<40;++i) wordText[who][i]='0'+i%10;
    control[0]=8; control[1]=1; control[3]=40; control[6]=handle;
    points[0]=x; points[1]=y+46;
    vdi_call(&pb); CHECK(ExecAESDiagnostic()==AES_OK);
    control[0]=1; control[1]=control[3]=0;
    vdi_call(&pb); CHECK(ExecAESDiagnostic()==AES_UNSUPPORTED);
    vs_clip(handle,1,outside);
    CHECK(vsf_color(handle,5)==5);
    v_bar(handle,huge);
    CHECK(ExecAESDiagnostic()==AES_OK);
    CHECK(vsf_color(handle,3)==3);
    CHECK(vsf_color(handle,99)==0 && ExecAESDiagnostic()==AES_UNSUPPORTED);
    CHECK(vswr_mode(handle,3)==0 && ExecAESDiagnostic()==AES_UNSUPPORTED);
    CHECK(vsf_interior(handle,2)==0 && ExecAESDiagnostic()==AES_UNSUPPORTED);
    CHECK(vswr_mode(handle,1)==1 && vsf_interior(handle,1)==1);
    CHECK(c->sequence==sequence); /* Every warm VDI call is caller-local. */
    CHECK(wind_update(END_UPDATE));
}

static void worker(UWORD who)
{
    BYTE bit=AllocSignal(-1),reserved[32],used=0,next;
    WORD handle,window=-1,cw,ch,bw,bh,out[58],bad[11],i;
    UWORD command=0;
    ULONG available;
    CHECK(bit>=0);
    starts[who]=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    CHECK(graf_handle(&cw,&ch,&bw,&bh)==1 && cw==8 && ch==8 && bw==8 && bh==8);
    {
        AESPB pb={grafControl[who],grafGlobal[who],NULL,grafOut[who],NULL,NULL};
        aes_call(&pb);
        CHECK(grafOut[who][0]==1 && grafOut[who][1]==8 && grafOut[who][4]==8);
    }
    while ((next=AllocSignal(-1))>=0) reserved[used++]=next;
    Forbid(); available=AvailMem(0); handle=1;
    v_opnvwk((WORD *)input,&handle,out);
    CHECK(handle==0 && ExecAESDiagnostic()==AES_RESOURCE && AvailMem(0)==available);
    Permit();
    while (used) FreeSignal(reserved[--used]);
    for (i=0;i<11;++i) bad[i]=input[i];
    bad[7]=2; handle=1; v_opnvwk(bad,&handle,out);
    CHECK(handle==0 && ExecAESDiagnostic()==AES_UNSUPPORTED);
    out[57]=12345; handle=1; v_opnvwk((WORD *)input,&handle,out);
    CHECK(handle==2 && ExecAESDiagnostic()==AES_OK && out[57]==12345);
    CHECK(out[0]==639 && out[1]==239 && out[13]==16 && out[14]==1 && out[15]==1 && out[25]==3);
    CHECK(out[6]==0 && out[7]==0 && out[37]==0 && out[45]==8 && out[48]==8);
    for (i=49;i<57;++i) CHECK(out[i]==0);
    CHECK(vsf_color(handle,who ? 2:4)==(who ? 2:4));
    i=1; v_opnvwk((WORD *)input,&i,out);
    CHECK(i==0 && ExecAESDiagnostic()==AES_RESOURCE);
    Forbid(); ++AESReady; Signal(root,wake); Permit();
    for (;;) {
        while (command==VDICommand[who]) Wait(starts[who]);
        command=VDICommand[who];
        if (command==1) {
            window=wind_create(NAME|CLOSER|MOVER,0,0,300,140);
            CHECK(window>0);
            CHECK(wind_set_str(window,WF_NAME,who ? "VDI B":"VDI A"));
            CHECK(wind_open(window,who ? 201:33,who ? 65:17,300,140));
            /* Drawing without logical ownership must not touch pixels. */
            v_bar(handle,(WORD *)input);
            CHECK(ExecAESDiagnostic()==AES_BUSY);
        } else if (command==2 || command==5) {
            CHECK(vsf_color(handle,who ? 2:4)==(who ? 2:4));
            draw(who,handle,window);
        } else if (command==3) {
            if (who) {
                CHECK(wind_set(window,WF_CXYWH,33,17,300,140));
                CHECK(vsf_color(handle,2)==2);
                draw(who,handle,window);
            } else {
                UWORD units=VDIUnits[who];
                WORD all[4]={0,0,639,239};
                CHECK(wind_update(BEG_UPDATE));
                CHECK(ExecAESContext()->view->visibleCount==0);
                vs_clip(handle,0,all); v_bar(handle,all);
                v_gtext(handle,45,55,"Completely covered");
                CHECK(VDIUnits[who]==units);
                CHECK(wind_update(END_UPDATE));
            }
        } else if (command==4) CHECK(wind_set(window,WF_CXYWH,201,65,300,140));
        else if (command==9) break;
        Forbid(); VDIStage[who]=command; Signal(root,wake); Permit();
    }
    if (!who) { v_clsvwk(handle); CHECK(ExecAESDiagnostic()==AES_OK); }
    /* The second client deliberately leaves its workstation and window open. */
    CHECK(appl_exit()); CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); ++AESDone; Signal(root,wake); RemTask(NULL);
}
void AESClientOne(void) { worker(0); }
void AESClientTwo(void) { worker(1); }

static void issue(UWORD who,UWORD command)
{
    VDICommand[who]=command; Signal(tasks[who],starts[who]);
}

UWORD AESRun(void)
{
    BYTE bit=AllocSignal(-1);
    ULONG available;
    UWORD i;
    CHECK(bit>=0); wake=1UL<<bit; root=FindTask(NULL);
    available=AvailMem(0);
    for (i=0;i<192;++i) longText[i]='A'+i%26;
    VDIPhase=1;
    while (VDIGo<1) ExecYield();
    tasks[0]=CreateTask("VDI A",1,(APTR)AESClientOne,1024UL);
    tasks[1]=CreateTask("VDI B",1,(APTR)AESClientTwo,1024UL);
    CHECK(tasks[0] && tasks[1]);
    while (AESReady!=2) Wait(wake);
    VDIPhase=2;
    while (VDIGo<2) ExecYield();
    issue(0,1); while (VDIStage[0]!=1) Wait(wake);
    issue(1,1); while (VDIStage[1]!=1) Wait(wake);
    issue(0,2); issue(1,2);
    while (VDIStage[0]!=2 || VDIStage[1]!=2) Wait(wake);
    CHECK(VDIUnits[0]>0 && VDIUnits[1]>0);
    VDIPhase=3;
    while (VDIGo<3) ExecYield();
    issue(1,3); while (VDIStage[1]!=3) Wait(wake);
    issue(0,3); while (VDIStage[0]!=3) Wait(wake);
    VDIPhase=4;
    while (VDIGo<4) ExecYield();
    issue(1,4); while (VDIStage[1]!=4) Wait(wake);
    issue(0,5); issue(1,5);
    while (VDIStage[0]!=5 || VDIStage[1]!=5) Wait(wake);
    VDIPhase=5;
    while (VDIGo<5) ExecYield();
    issue(0,9); issue(1,9);
    while (AESDone!=2) Wait(wake);
    CHECK(AvailMem(0)==available);
    FreeSignal(bit);
    return AESFailures;
}
