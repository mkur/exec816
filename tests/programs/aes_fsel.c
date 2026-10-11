#include "../../c/calypsi/aes-fsel-private.h"
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <proto/exec.h>
#include <string.h>

ULONG AESService;
volatile UWORD AESFileABI=10;
static UWORD bindingVariant;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESFilePhase[2],AESFileDone;
volatile ULONG AESFileReads;
ULONG AESFileCold,AESFileWarm,AESFileReturned;
ULONG AESFileContext[2];
static struct Task *controller;
static ULONG wake;
static UWORD fault;
static char path[128],file[13];
static WORD message[8],button;
struct FileClient { UWORD before; char path[128]; UWORD middle; char file[13]; UWORD after; WORD button; };
static struct FileClient clients[2];
static struct Task *peers[3];
static ULONG peerWake[3];
static volatile UWORD capacity,ready,done;

static void check(BOOL okay)
{
    Forbid();++AESChecks;if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=AESChecks; }Permit();
}
#define CHECK(t) check((t)!=0)
static BOOL fail(UWORD stage)
{
    if (fault!=stage) return FALSE;
    fault=0;ExecAESContext()->diagnostic=stage<5 || stage>=8 ? AES_RESOURCE:AES_DISPLAY_ERROR;
    return TRUE;
}
void *AESFormAlloc(ULONG n,ULONG flags) { return fail(1) ? NULL:AllocMem(n,flags); }
void *AESFileStateAlloc(ULONG n,ULONG flags) { return fail(8) ? NULL:AllocMem(n,flags); }
void *AESFileEntriesAlloc(ULONG n,ULONG flags) { return fail(9) ? NULL:AllocMem(n,flags); }
WORD AESFormCreate(WORD k,WORD x,WORD y,WORD w,WORD h) { return fail(2) ? -1:wind_create(k,x,y,w,h); }
WORD AESFormOpen(WORD w,WORD x,WORD y,WORD dx,WORD dy) { return fail(3) ? 0:wind_open(w,x,y,dx,dy); }
void AESFormVDIOpen(WORD *in,WORD *handle,WORD *out)
{ if (fail(4)) *handle=0;else v_opnvwk(in,handle,out); }
WORD AESFormClose(WORD w) { return fail(5) ? 0:wind_close(w); }
WORD AESFormDelete(WORD w) { return fail(6) ? 0:wind_delete(w); }
extern BOOL ExecVDIClose(struct ExecAESContext *);
BOOL AESFormVDIClose(struct ExecAESContext *c) { return fail(7) ? FALSE:ExecVDIClose(c); }
WORD AESFileNext(struct FileScan *scan)
{
    ++AESFileReads;
    if (fault==10 && scan->count==3) {
        fault=0;scan->count=0;scan->error=ERROR_OBJECT_NOT_FOUND;FileScanEnd(scan);return 0;
    }
    return FileScanNext(scan);
}

static WORD select_file(char *path,char *file,WORD *button,const char *title)
{
    struct ExecAESContext *c=ExecAESContext();
    AESPB pb={c->control,c->request.global,c->intin,c->intout,c->addrin,c->addrout};
    WORD variant=AESFilePhase[0] ? AESFilePhase[0]%4:bindingVariant++%4;
    if (AESFilePhase[0]==8) variant=1;
    if (!variant) return fsel_input(path,file,button);
    if (variant==1) return fsel_exinput(path,file,button,title);
    c->control[0]=variant==2 ? 90:91;c->control[1]=0;c->control[2]=2;
    c->control[3]=variant==2 ? 2:3;c->control[4]=0;
    c->addrin[0]=(LONG)(ULONG)path;c->addrin[1]=(LONG)(ULONG)file;c->addrin[2]=(LONG)(ULONG)title;
    aes_call(&pb);*button=c->intout[1];return c->intout[0];
}

static WORD host(WORD x,WORD y,WORD w,WORD h)
{
    WORD bx,by,bw,bh,window;
    CHECK(wind_calc(WC_BORDER,NAME|CLOSER|MOVER,x,y,w,h,&bx,&by,&bw,&bh));
    window=wind_create(NAME|CLOSER|MOVER,bx,by,bw,bh);CHECK(window>0);
    CHECK(wind_open(window,bx,by,bw,bh));return window;
}

static void finish(WORD who)
{
    CHECK(clients[who].before==0x1234 && clients[who].middle==0x5678 && clients[who].after==0x9abc);
    CHECK(ExecAESDetach());CHECK(ExecDOSDetach());AESFilePhase[who]=90;
    Forbid();++AESFileDone;Signal(controller,wake);RemTask(NULL);
}

void AESClientOne(void)
{
    struct FileClient *a=&clients[1];
    WORD who; BYTE bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    if (capacity) {
        who=ready;bit=AllocSignal(-1);CHECK(bit>=0);peerWake[who]=1UL<<bit;
        host(16+who*120,64,208,128);++ready;Signal(controller,wake);
        Wait(peerWake[who]);CHECK(ExecAESDetach());FreeSignal(bit);
        Forbid();++done;Signal(controller,wake);RemTask(NULL);
    }
    a->before=0x1234;a->middle=0x5678;a->after=0x9abc;
    host(16,64,224,136);AESFileContext[1]=(ULONG)ExecAESContext();
    strcpy(a->path,"D1:*.BIN");strcpy(a->file,"PEER.BIN");
    AESFilePhase[1]=1;Signal(controller,wake);
    CHECK(select_file(a->path,a->file,&a->button,"Independent peer"));
    CHECK(a->button==0 && !strcmp(a->path,"D1:*.BIN") && !strcmp(a->file,"PEER.BIN"));
    finish(1);
}

void AESClientTwo(void)
{
    struct FileClient *a=&clients[0];
    struct ExecAESContext *c;
    WORD window;
    ULONG reads;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    c=ExecAESContext();AESFileContext[0]=(ULONG)c;
    a->before=0x1234;a->middle=0x5678;a->after=0x9abc;
    strcpy(a->path,"D1:*.TXT");strcpy(a->file,"SEED.TXT");AESFilePhase[0]=1;
    CHECK(select_file(a->path,a->file,&a->button,"Save selection"));
    CHECK(a->button==1 && !strcmp(a->file,"new.txt") && !strcmp(a->path,"D1:*.TXT"));
    CHECK(!c->form && !c->view && !c->workstation);
    window=host(360,72,208,128);
    strcpy(a->path,"D1:MANY/*.TXT");a->file[0]=0;AESFilePhase[0]=2;
    CHECK(select_file(a->path,a->file,&a->button,"Compact selector"));
    CHECK(a->button==1 && !strcmp(a->file,"A005.TXT"));
    CHECK(c->view->handle==window && c->view->shown && !c->workstation);
    CHECK(wind_close(window));CHECK(wind_delete(window));
    strcpy(a->path,"D1:MISSING/*.*");strcpy(a->file,"OLD.TXT");AESFilePhase[0]=3;
    CHECK(select_file(a->path,a->file,&a->button,"Correct a path"));
    CHECK(a->button==0 && !strcmp(a->path,"D1:*.TXT") && !strcmp(a->file,"OLD.TXT"));
    strcpy(a->path,"D1:*.TXT");AESFilePhase[0]=4;
    CHECK(select_file(a->path,a->file,&a->button,"Move and close"));CHECK(a->button==0);
    strcpy(a->path,"D1:MANY/*.*");AESFilePhase[0]=5;
    CHECK(select_file(a->path,a->file,&a->button,"Cancel loading"));CHECK(a->button==0);
    window=host(320,64,240,152);strcpy(a->path,"D1:*.TXT");
    AESFilePhase[0]=6;
    CHECK(!select_file(a->path,a->file,&a->button,"Borrowed policy"));
    CHECK(ExecAESDiagnostic()==AES_PENDING && a->button==0 && !strcmp(a->path,"D1:*.TXT"));
    CHECK(evnt_mesag(message) && message[0]==WM_MOVED && c->messageEpoch);
    CHECK(evnt_mesag(message) && message[0]==WM_REDRAW && c->messageEpoch);
    AESFilePhase[0]=7;
    CHECK(!select_file(a->path,a->file,&a->button,"Borrowed closer"));
    CHECK(ExecAESDiagnostic()==AES_PENDING && a->button==0);
    CHECK(evnt_mesag(message) && message[0]==WM_CLOSED && c->messageEpoch);
    CHECK(evnt_mesag(message) && message[0]==WM_REDRAW && c->messageEpoch);
    CHECK(wind_close(window));CHECK(wind_delete(window));
    strcpy(a->path,"D1:MANY/*.*");fault=10;AESFilePhase[0]=8;
    CHECK(select_file(a->path,a->file,&a->button,"0123456789012345678901234567890123456789"));
    CHECK(!fault && a->button==0);
    a->path[0]=0;strcpy(a->file,"DEFAULT.TXT");AESFilePhase[0]=9;
    CHECK(select_file(a->path,a->file,&a->button,NULL));
    CHECK(a->button==0 && !strcmp(a->path,"SYS:*.*") && !strcmp(a->file,"DEFAULT.TXT"));
    strcpy(a->path,"D1:");memset(a->path+3,'?',124);a->path[127]=0;
    strcpy(a->file,"EIGHTCHR.TXT");AESFilePhase[0]=10;
    CHECK(select_file(a->path,a->file,&a->button,NULL));
    CHECK(a->button==0 && strlen(a->path)==127 && !strcmp(a->file,"EIGHTCHR.TXT"));
    strcpy(a->path,"A:\\GEM\\*.*");reads=AESFileReads;AESFilePhase[0]=11;
    CHECK(select_file(a->path,a->file,&a->button,"Exec paths"));
    CHECK(a->button==0 && !strcmp(a->path,"A:\\GEM\\*.*") && AESFileReads==reads);
    CHECK(!c->form && !c->editTree && !c->updateDepth && !c->mouseDepth);
    CHECK(!c->timer.port && !c->endpoint->input->interest);
    finish(0);
}

UWORD AESRun(void)
{
    ULONG available,base;
    struct ExecAESContext *c;
    BPTR lock,opened;
    WORD i,window;
    BYTE bit;
    CHECK(AESFileABI==10);
    /* Mount metadata and the shared filesystem cache live until shutdown. */
    AESFileCold=AvailMem(0);
    opened=Open("D1:A.TXT",MODE_OLDFILE);CHECK(opened && Close(opened));CHECK(ExecDOSDetach());
    AESFileWarm=available=AvailMem(0);bit=AllocSignal(-1);
    CHECK(bit>=0);controller=FindTask(NULL);wake=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);c=ExecAESContext();
    opened=Open("D1:A.TXT",MODE_OLDFILE);CHECK(opened!=0);
    lock=Lock("D1:",SHARED_LOCK);CHECK(lock!=0);base=AvailMem(0);
    {
        WORD ctl[5]={90,0,2,2,0},globals[15],output[2]={9,9};
        LONG address[3]={(LONG)(ULONG)path,(LONG)(ULONG)file,0};
        AESPB pb={ctl,globals,NULL,output,address,NULL};
        for (i=0;i<2;++i) {
            ctl[0]=90+i;ctl[3]=2+i;ctl[1]=1;
            aes_call(&pb);CHECK(!output[0] && !output[1] && ExecAESDiagnostic()==AES_MALFORMED);
            ctl[1]=0;ctl[3]=1;
            aes_call(&pb);CHECK(!output[0] && !output[1] && ExecAESDiagnostic()==AES_MALFORMED);
            ctl[3]=2+i;ctl[2]=1;output[1]=0x5678;
            aes_call(&pb);CHECK(!output[0] && output[1]==0x5678 && ExecAESDiagnostic()==AES_MALFORMED);
            ctl[2]=2;ctl[4]=1;
            aes_call(&pb);CHECK(!output[0] && !output[1] && ExecAESDiagnostic()==AES_MALFORMED);
            ctl[4]=0;
        }
        memset(path,'X',128);strcpy(file,"A.TXT");
        CHECK(!fsel_input(path,file,&button) && !button && ExecAESDiagnostic()==AES_MALFORMED);
        strcpy(path,"D1:*.TXT");memset(file,'X',13);
        CHECK(!fsel_exinput(path,file,&button,"Limits") && !button && ExecAESDiagnostic()==AES_MALFORMED);
        CHECK(!c->form && AvailMem(0)==base);
    }
    strcpy(path,"D1:*.TXT");strcpy(file,"ORIGINAL.TXT");
    for (i=1;i<=9;++i) {
        if (i>=5 && i<=7) continue;
        fault=i;CHECK(!select_file(path,file,&button,0) && !fault);
        CHECK(ExecAESDiagnostic()==AES_RESOURCE && !c->form && AvailMem(0)==base);
        CHECK(!strcmp(path,"D1:*.TXT") && !strcmp(file,"ORIGINAL.TXT") && button==0);
    }
    for (i=5;i<=7;++i) {
        message[0]=WM_REDRAW;message[1]=123;message[7]=500+i;
        CHECK(appl_write(c->gemId,16,message));fault=i;
        CHECK(!select_file(path,file,&button,0) && !fault);
        CHECK(ExecAESDiagnostic()==AES_DISPLAY_ERROR && c->form && c->form->fileSelector);
        CHECK(!strcmp(file,"ORIGINAL.TXT") && button==0);
        CHECK(form_dial(FMD_FINISH,0,0,0,0,0,0,0,0));
        CHECK(evnt_mesag(message) && message[0]==WM_REDRAW && message[1]==123 && message[7]==500+i);
        CHECK(!c->form && AvailMem(0)==base);
    }
    window=host(16,56,207,128);
    CHECK(!select_file(path,file,&button,0) && ExecAESDiagnostic()==AES_RESOURCE);
    CHECK(!c->form && c->view->handle==window && c->view->shown);
    CHECK(wind_close(window));
    CHECK(!select_file(path,file,&button,0) && ExecAESDiagnostic()==AES_BUSY);
    CHECK(wind_delete(window));
    CHECK(wind_update(BEG_UPDATE));
    CHECK(!select_file(path,file,&button,0) && ExecAESDiagnostic()==AES_BUSY);
    CHECK(wind_update(END_UPDATE));
    CHECK(form_dial(FMD_START,0,0,0,0,24,48,208,128));
    CHECK(!select_file(path,file,&button,0) && ExecAESDiagnostic()==AES_BUSY);
    CHECK(form_dial(FMD_FINISH,0,0,0,0,0,0,0,0));
    /* A full application queue still leaves room for the separate repair fact. */
    window=host(16,56,224,136);
    for (i=0;i<16;++i) { message[0]=WM_REDRAW;message[7]=600+i;CHECK(appl_write(c->gemId,16,message)); }
    CHECK(!appl_write(c->gemId,16,message));
    CHECK(!select_file(path,file,&button,0) && ExecAESDiagnostic()==AES_PENDING);
    CHECK(evnt_mesag(message) && message[0]==WM_REDRAW && message[7]==600 && !c->messageEpoch);
    CHECK(evnt_mesag(message) && message[0]==WM_REDRAW && c->messageEpoch);
    for (i=1;i<16;++i) {
        do { CHECK(evnt_mesag(message)); } while (c->messageEpoch);
        CHECK(message[7]==600+i);
    }
    CHECK(wind_close(window));CHECK(wind_delete(window));
    capacity=1;
    for (i=0;i<3;++i) {
        peers[i]=CreateTask("Selector capacity",0,(APTR)AESClientOne,1280UL);
        CHECK(peers[i]!=NULL);while (ready<=i) Wait(wake);
    }
    base=AvailMem(0);
    CHECK(!select_file(path,file,&button,0) && ExecAESDiagnostic()==AES_RESOURCE);
    CHECK(!c->form && AvailMem(0)==base);
    for (i=0;i<3;++i) Signal(peers[i],peerWake[i]);
    while (done<3) Wait(wake);
    capacity=0;
    CHECK(Read(opened,path,5)==5 && !memcmp(path,"hello",5));CHECK(Close(opened));UnLock(lock);
    CHECK(ExecAESDetach());CHECK(ExecDOSDetach());
    CHECK(CreateTask("Selector peer",0,(APTR)AESClientOne,1280UL)!=NULL);
    while (!AESFilePhase[1]) Wait(wake);
    CHECK(CreateTask("Selector input",0,(APTR)AESClientTwo,1280UL)!=NULL);
    while (AESFileDone<2) Wait(wake);
    FreeSignal(bit);AESFileReturned=AvailMem(0);CHECK(AESFileReturned==available);return AESFailures;
}
