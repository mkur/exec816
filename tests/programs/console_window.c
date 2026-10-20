/* WB7: ordinary loaded C launcher, real child and physical GEM control. */
#include <exec816/aes.h>
#include <exec816/console.h>
#include <exec816/program.h>
#include <exec816/runtime.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <gem.h>
#include <string.h>

volatile UWORD CWChecks,CWStage,CWRound,CWSaves,CWStopped,CWFirstFailure;
volatile ULONG CWUnit,CWChild;
volatile WORD CWSource,CWOutput;
static WORD vdi;
static OBJECT menu[]={
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,11},
    {1,3,3,G_IBOX,0,0,0,8,0,424,11},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Program",0,0,72,11},
    {0,5,5,G_IBOX,0,0,0,0,11,640,229},
    {4,6,7,G_BOX,0,0,0x1100,8,0,144,22},
    {7,-1,-1,G_STRING,0,0,(ULONG)"Save probe",0,0,144,11},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Stop",0,11,144,11}
};
#define CHECK(x) do { ++CWChecks;if (!(x)) { CWFirstFailure=__LINE__;return __LINE__; } } while (0)

static void name(char *text,const char *device,ULONG unit)
{
    UWORD i;strcpy(text,device);
    for (i=0;i<8;++i) text[4+i]="0123456789ABCDEF"[(unit>>((7-i)*4))&15];
    text[12]=0;
}

static WORD paint(void)
{
    WORD r[4],clip[4],okay=1;
    if (!ExecAESBeginUpdate(CWSource)) return 0;
    if (!wind_get(CWSource,WF_FIRSTXYWH,&r[0],&r[1],&r[2],&r[3])) okay=0;
    while (okay && r[2] && r[3]) {
        clip[0]=r[0];clip[1]=r[1];clip[2]=r[0]+r[2]-1;clip[3]=r[1]+r[3]-1;
        vs_clip(vdi,1,clip);vsf_color(vdi,0);v_bar(vdi,clip);
        if (!ExecAESPainted(CWSource,r[0],r[1],r[2],r[3])) okay=0;
        if (!wind_get(CWSource,WF_NEXTXYWH,&r[0],&r[1],&r[2],&r[3])) okay=0;
    }
    vs_clip(vdi,0,clip);
    return wind_update(END_UPDATE) && okay;
}

static WORD events(struct ExecAESWaitSpec *s)
{
    WORD *m=s->message;BPTR file;
    if (m[0]==MN_SELECTED) {
        if (m[4]==6) {
            file=Open("RAM:CWGUI.TXT",MODE_NEWFILE);
            if (!file) return 0;
            if (Write(file,"GUI",3)!=3) { Close(file);return 0; }
            if (!Close(file)) return 0;
            ++CWSaves;
        } else if (m[4]==7 && CWChild) {
            if (!ExecBreakProgram(CWChild)) return 0;
            ++CWStopped;
        }
        return menu_tnormal(menu,m[3],1);
    }
    if (m[3]!=CWSource && m[3]!=CWOutput) return 1;
    if (m[0]==WM_REDRAW) return m[3]==CWSource ? paint():1;
    if (m[0]==WM_TOPPED) return wind_set(m[3],WF_TOP,0,0,0,0);
    if (m[0]==WM_MOVED) {
        if (m[3]==CWOutput) {
            m[4]=((m[4]+8)&~7)-8;m[5]=((m[5]+11)&~7)-11;
        }
        return wind_set(m[3],WF_CXYWH,m[4],m[5],m[6],m[7]);
    }
    if (m[0]==WM_CLOSED) {
        if (CWChild && !ExecBreakProgram(CWChild)) return 0;
        ++CWStopped;
        if (m[3]==CWOutput) return wind_close(CWOutput);
    }
    return 1;
}

int main(void)
{
    struct ExecAESWaitSpec wait={0};struct ExecProgramStart start={0};
    struct ExecProgramResult result;BPTR input,output;ULONG second,third;
    WORD i,bw,bh,cw,ch,in[11],out[57],got,windows[6],count;char path[13];
    CHECK(appl_init()>0);
    vdi=graf_handle(&cw,&ch,&bw,&bh);for (i=0;i<10;++i) in[i]=1;in[10]=2;
    v_opnvwk(in,&vdi,out);CHECK(vdi && cw==8 && ch==8);
    CWSource=wind_create(NAME|CLOSER|MOVER,24,29,320,128);CHECK(CWSource>0);
    CHECK(wind_set_str(CWSource,WF_NAME,"Console control"));
    CHECK(wind_open(CWSource,24,29,320,128) && menu_bar(menu,1));
    count=0;
    while (count<6) {
        got=wind_create(NAME|CLOSER|MOVER,0,0,32,32);
        if (got<0) break;
        windows[count++]=got;
    }
    CHECK(count>0 && count<6 && ExecAESDiagnostic()==AES_RESOURCE);
    for (i=0;i<count;++i) CHECK(wind_delete(windows[i]));
    for (CWRound=0;CWRound<3;++CWRound) {
        CWStage=1;CWUnit=ExecConsoleCreate(64,20);CHECK(CWUnit);
        if (!CWRound) {
            second=ExecConsoleCreate(64,20);third=ExecConsoleCreate(64,20);
            CHECK(second && third && !ExecConsoleCreate(64,20));
            CHECK(ExecConsoleDestroy(second) && ExecConsoleDestroy(third));
            CHECK(!ExecConsoleDestroy(second));
        }
        CHECK(!ExecAESConsole(CWSource,CWUnit));
        CWOutput=wind_create(NAME|CLOSER|MOVER,56,21,528,173);CHECK(CWOutput>0);
        CHECK(wind_set_str(CWOutput,WF_NAME,"Owned output") && ExecAESConsole(CWOutput,CWUnit));
        CHECK(!ExecConsoleDestroy(CWUnit));
        name(path,"CON:",CWUnit);input=Open(path,MODE_OLDFILE);CHECK(input);
        name(path,"RAW:",CWUnit);output=Open(path,MODE_NEWFILE);CHECK(output);
        CHECK(ExecConsoleMode(input,EXEC_CONSOLE_ATASCII)==1);
        CHECK(!ExecConsoleDestroy(CWUnit));
        CHECK(Write(output,"OWNED\n",6)==6);
        CHECK(wind_open(CWOutput,56,21,528,173));
        start.input=input;start.output=output;start.console=input;
        CWChild=ExecStartProgram(CWRound==1 ? "SYS:CWREAD.COM":"SYS:CWKEY.COM",&start);
        CHECK(CWChild);
        CWStage=2;
        if (CWRound==2) CHECK(ExecBreakProgram(CWChild));
        for (;;) {
            if (ExecCollectProgram(CWChild,&result)) break;
            wait.flags=MU_MESAG;wait.signalMask=ExecProgramMask(CWChild);CHECK(wait.signalMask);
            got=ExecAESWait(&wait);CHECK(got);
            if (got&MU_MESAG) CHECK(events(&wait));
        }
        CWChild=0;CWStage=3;CHECK(result.primary==20 && result.secondary==ERROR_BREAK);
        CHECK(ExecConsoleGetMode(input)==EXEC_CONSOLE_ATASCII);
        if (!CWRound) {
            while (CWSaves<2) {
                wait.flags=MU_MESAG;wait.signalMask=0;
                got=ExecAESWait(&wait);CHECK(got && (got&MU_MESAG));
                CHECK(events(&wait));
            }
        }
        /* A prior output close is harmless. A hidden binding still retains
         * the unit until deletion; endpoint closure is independent. */
        CHECK(wind_close(CWOutput));CHECK(!ExecConsoleDestroy(CWUnit));
        CHECK(wind_delete(CWOutput));CWOutput=0;
        CHECK(!ExecConsoleDestroy(CWUnit));
        CHECK(Close(input) && Close(output));
        CHECK(ExecConsoleDestroy(CWUnit));CWUnit=0;
    }
    CWStage=4;CHECK(CWSaves>=3 && CWStopped>=2);
    CHECK(DeleteFile("RAM:CWGUI.TXT"));
    CHECK(menu_bar(menu,0) && appl_exit());CWStage=5;
    return 0;
}
