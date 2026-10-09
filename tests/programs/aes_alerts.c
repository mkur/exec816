#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <string.h>
#include "../../c/calypsi/aes-alert-private.h"

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESAlertPhase[2],AESAlertDone;
ULONG AESAlertContext[2];
const UWORD AESAlertSizes[]={sizeof(struct ExecAESAlert),sizeof(struct ExecAESForm)};
static UWORD fault;
static struct ExecAESAlert parsed;
static char buffer[600];
static struct Task *controller;
static ULONG wake;
static WORD message[8];
static BOOL fail(UWORD stage)
{
    if (fault!=stage) return FALSE;
    fault=0; ExecAESContext()->diagnostic=stage<5 || stage==8 ? AES_RESOURCE:AES_DISPLAY_ERROR;
    return TRUE;
}
void *AESFormAlloc(ULONG bytes,ULONG flags) { return fail(1) ? NULL:AllocMem(bytes,flags); }
void *AESAlertAlloc(ULONG bytes,ULONG flags) { return fail(8) ? NULL:AllocMem(bytes,flags); }
WORD AESFormCreate(WORD kind,WORD x,WORD y,WORD w,WORD h)
{ return fail(2) ? -1:wind_create(kind,x,y,w,h); }
WORD AESFormOpen(WORD handle,WORD x,WORD y,WORD w,WORD h)
{ return fail(3) ? 0:wind_open(handle,x,y,w,h); }
void AESFormVDIOpen(WORD *in,WORD *handle,WORD *out)
{ if (fail(4)) *handle=0; else v_opnvwk(in,handle,out); }
WORD AESFormClose(WORD handle) { return fail(5) ? 0:wind_close(handle); }
WORD AESFormDelete(WORD handle) { return fail(6) ? 0:wind_delete(handle); }
extern BOOL ExecVDIClose(struct ExecAESContext *);
BOOL AESFormVDIClose(struct ExecAESContext *c) { return fail(7) ? FALSE:ExecVDIClose(c); }
static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
    Permit();
}
#define CHECK(t) check((t)!=0)

static void parse_cases(void)
{
    WORD i,j,pos,extra;
    CHECK(ExecAESAlertParse(&parsed,1,"[0][Hello][Okay]")==AES_OK);
    CHECK(parsed.icon==0 && parsed.lineCount==1 && parsed.buttonCount==1);
    CHECK(ExecAESAlertParse(&parsed,0,"[3][A||B|C]]D][Yes|No|Cancel]")==AES_OK);
    CHECK(!strcmp(parsed.lines[0],"A|B") && !strcmp(parsed.lines[1],"C]D"));
    for (i=0;i<4;++i) {
        CHECK(ExecAESAlertParse(&parsed,i,"[2][Question][One|Two|Three]")==AES_OK);
        for (j=0;j<3;++j) CHECK(!!(parsed.tree[j+7].ob_flags&DEFAULT)==(i==j+1));
    }
    CHECK(ExecAESAlertParse(&parsed,-1,"[0][x][y]")==AES_MALFORMED);
    CHECK(ExecAESAlertParse(&parsed,2,"[0][x][y]")==AES_MALFORMED);
    CHECK(ExecAESAlertParse(&parsed,1,"[4][x][y]")==AES_UNSUPPORTED);
    CHECK(ExecAESAlertParse(&parsed,1,"[x][x][y]")==AES_MALFORMED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][x][y]extra")==AES_MALFORMED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][x][]")==AES_MALFORMED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][x][y|]")==AES_MALFORMED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][x][y")==AES_MALFORMED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][a|b|c|d|e|f][y]")==AES_UNSUPPORTED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][x][a|b|c|d]")==AES_UNSUPPORTED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][12345678901234567890123456789012345678901][y]")==AES_UNSUPPORTED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][x][123456789012345678901]")==AES_UNSUPPORTED);
    CHECK(ExecAESAlertParse(&parsed,1,"[0][][y]")==AES_OK);
    /* A genuinely valid 511-byte string, then 512 with unchanged decoded
     * field bounds. This separates source length from decoded capacities. */
    for (extra=38;extra<=39;++extra) {
        strcpy(buffer,"[3]["); pos=4;
        for (i=0;i<5;++i) {
            for (j=0;j<40;++j) { buffer[pos++]=']'; buffer[pos++]=']'; }
            buffer[pos++]=i==4 ? ']':'|';
        }
        buffer[pos++]='[';
        for (i=0;i<60;++i) {
            buffer[pos++]=i<extra ? ']':'x';
            if (i<extra) buffer[pos++]=']';
            if (i==19 || i==39) buffer[pos++]='|';
        }
        buffer[pos++]=']'; buffer[pos]=0;
        CHECK(pos==473+extra);
        CHECK(ExecAESAlertParse(&parsed,3,buffer)==(extra==38 ? AES_OK:AES_UNSUPPORTED));
    }
}

void AESClientOne(void)
{
    WORD window;
    CHECK(ExecAESAttach((struct MsgPort *)AESService)); CHECK(appl_init()>0);
    window=wind_create(NAME|CLOSER|MOVER,192,64,256,136); CHECK(window>0);
    CHECK(wind_set_str(window,WF_NAME,"Alert peer")); CHECK(wind_open(window,192,64,256,136));
    AESAlertContext[1]=(ULONG)ExecAESContext(); AESAlertPhase[1]=1; Signal(controller,wake);
    CHECK(form_alert(1,"[1][Independent peer][Okay]")==1);
    CHECK(ExecAESDetach()); AESAlertPhase[1]=90;
    Forbid(); ++AESAlertDone; Signal(controller,wake); RemTask(NULL);
}

void AESClientTwo(void)
{
    WORD ctl[5]={52,1,1,1,0},global[15],def=2,result;
    LONG text=(LONG)(ULONG)"[2][A||B|C]]D][One|Two|Three]";
    AESPB pb={ctl,global,&def,&result,&text,0};
    CHECK(ExecAESAttach((struct MsgPort *)AESService)); CHECK(appl_init()>0);
    AESAlertContext[0]=(ULONG)ExecAESContext();
    AESAlertPhase[0]=1; CHECK(form_alert(1,"[0][No icon][Okay]")==1);
    AESAlertPhase[0]=2; aes_call(&pb); CHECK(result==2);
    AESAlertPhase[0]=3; CHECK(form_alert(0,"[3][Stop and choose][Back|Continue]")==2);
    AESAlertPhase[0]=4; CHECK(form_alert(1,"[1][Close dismisses][Okay]")==0);
    CHECK(ExecAESDiagnostic()==AES_OK);
    CHECK(ExecAESDetach()); AESAlertPhase[0]=90;
    Forbid(); ++AESAlertDone; Signal(controller,wake); RemTask(NULL);
}

UWORD AESRun(void)
{
    WORD i,window;
    ULONG available=AvailMem(0),base;
    struct ExecAESContext *c;
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0); controller=FindTask(NULL); wake=1UL<<bit;
    parse_cases();
    CHECK(ExecAESAttach((struct MsgPort *)AESService)); CHECK(appl_init()>0);
    c=ExecAESContext(); base=AvailMem(0);
    CHECK(form_alert(1,"bad")==0 && ExecAESDiagnostic()==AES_MALFORMED);
    for (i=1;i<=4;++i) {
        fault=i; CHECK(!form_alert(1,"[0][Failure][Okay]") && !fault);
        CHECK(ExecAESDiagnostic()==AES_RESOURCE && !c->form && AvailMem(0)==base);
    }
    fault=8; CHECK(!form_alert(1,"[0][Allocation][Okay]") && !fault);
    CHECK(ExecAESDiagnostic()==AES_RESOURCE && !c->form && AvailMem(0)==base);
    for (i=5;i<=7;++i) {
        message[0]=100+i; message[7]=500+i;
        CHECK(appl_write(c->gemId,16,message)); fault=i;
        CHECK(!form_alert(1,"[2][Interrupted][Okay]") && !fault);
        CHECK(ExecAESDiagnostic()==AES_DISPLAY_ERROR && c->form && c->form->alert);
        CHECK(form_dial(FMD_FINISH,0,0,0,0,0,0,0,0));
        CHECK(evnt_mesag(message) && message[0]==100+i && message[7]==500+i);
        CHECK(!c->form && AvailMem(0)==base);
    }
    window=wind_create(NAME|CLOSER|MOVER,16,32,80,64); CHECK(window>0);
    CHECK(wind_open(window,16,32,80,64));
    CHECK(!form_alert(1,"[2][Cannot fit here][Okay]") && ExecAESDiagnostic()==AES_RESOURCE);
    CHECK(!c->form && c->view->handle==window && c->view->shown);
    CHECK(ExecAESDetach());
    CHECK(CreateTask("Alert peer",0,(APTR)AESClientOne,1024UL)!=NULL);
    while (!AESAlertPhase[1]) Wait(wake);
    CHECK(CreateTask("Alert input",0,(APTR)AESClientTwo,1024UL)!=NULL);
    while (AESAlertDone<2) Wait(wake);
    FreeSignal(bit); CHECK(AvailMem(0)==available);
    return AESFailures;
}
