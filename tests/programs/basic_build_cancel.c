/* Fixture-only control of real controller turns. Input still enters through AES. */
#include "../../examples/gem-basic/build.h"
#include "../../examples/gem-basic/build-job.h"
#include "../../examples/gem-basic/files.h"
#include "../../examples/gem-basic/file-ui.h"
#include <proto/exec.h>
#include <proto/dos.h>
#include <devices/timer.h>
#include <string.h>
#ifndef FIXTURE_FIRST
#define FIXTURE_FIRST 0
#define FIXTURE_LIMIT 24
#endif
extern struct BasicBuildJob b;
extern struct BasicFileJob publication;
void FixtureActualStep(struct BasicEditor *);
volatile ULONG FixtureHeld,FixtureCompleted,FixtureRecovered,FixtureReady,FixtureFinished,FixtureChecks;
volatile ULONG FixtureMaxTurnTicks;
volatile ULONG FixtureRecoveryShown;
static struct MsgPort *clockPort;
static struct TimerClockRequest *clock;
static UWORD index=FIXTURE_FIRST,mode,turns,recovery,settling;
static ULONG last;
static const UWORD targets[]={4,5,7,8,8,10,11,11,14,12,13};
static char source[8192];
static ULONG holders[2];
static UWORD deleteFailed;

LONG FixtureDelete(const char *name)
{
    if (index==23 && b.phase==14 && !deleteFailed && !strcmp(name,b.source)) {
        deleteFailed=1;DeleteFile("RAM:ABSENT.X");return 0;
    }
    return DeleteFile(name);
}

static ULONG ticks(void)
{
    if (!clock) {
        clockPort=CreateMsgPort();
        clock=(struct TimerClockRequest *)CreateIORequest(clockPort,sizeof(*clock));
        if (!clock || OpenDevice("timer.device",UNIT_VBLANK,&clock->tc_Request,0)) {
            FixtureChecks=0xfffc;return 0;
        }
    }
    clock->tc_Request.io_Command=TD_READCLOCK;
    if (DoIO(&clock->tc_Request)) FixtureChecks=0xfffb;
    return clock->ticks_lo;
}

void FixtureCleanup(void)
{
    if (clock) {
        CloseDevice(&clock->tc_Request);DeleteIORequest(&clock->tc_Request);
        DeleteMsgPort(clockPort);clock=0;clockPort=0;
    }
}

static void content(struct BasicEditor *e,WORD recovering)
{
    UWORD i,n=0;
    if (!recovering) {
        for (i=0;i<32;++i) {
            source[n++]='\'';memset(source+n,' ',200);n+=200;source[n++]='\n';
        }
        if (index%11==6) strcpy(source+n,"DO: LOOP");
        else if (index%11==7) strcpy(source+n,"PRINT \"INPUT\": INPUT N");
        else strcpy(source+n,"PRINT \"CANCEL\"");
        n+=strlen(source+n);
    } else { strcpy(source,"PRINT \"RECOVER\"");n=strlen(source); }
    if (BasicReplace(&e->document,0,e->document.bytes,(const UBYTE *)source,n)) {
        FixtureChecks=0xffff;return;
    }
    e->caret=e->anchor=0;e->first=e->left=0;BasicEditorDamage(e,0,BASIC_LINES);
}

WORD FixtureSelect(char *path,char *leaf,WORD *selected,const char *title)
{
    (void)title;strcpy(path,"RAM:*.COM");strcpy(leaf,"CANCEL.COM");*selected=1;return 1;
}

void BasicBuildStep(struct BasicEditor *e)
{
    UWORD target=targets[index%11];ULONG before,elapsed;
    if (FixtureChecks>=0xfff0) return;
    if (b.phase) {
        if (index<22 && !recovery && !b.stop && b.phase==target) {
            ++turns;
            if ((target!=4 && target!=5 && target!=12 || b.at) &&
                (target!=7 && target!=10 || turns>=6) &&
                (target!=13 || publication.phase==2 && publication.at)) {
                FixtureHeld=index+1;return;
            }
        }
        before=ticks();FixtureActualStep(e);elapsed=ticks()-before;
        if (elapsed>FixtureMaxTurnTicks) FixtureMaxTurnTicks=elapsed;
        return;
    }
    if (b.job && b.job!=last) {
        last=b.job;
        if (recovery) {
            if (b.cause) { FixtureChecks=0xfffe;return; }
            FixtureRecovered=index+1;++index;FixtureHeld=0;recovery=0;turns=0;
            ++FixtureChecks;
        } else {
            if (index==22) {
                UWORD i;struct ExecProgramResult result;
                if (b.cause!=103 || b.programResult.primary || b.programResult.secondary) { FixtureChecks=0xfffa;return; }
                for (i=0;i<2;++i) ExecBreakProgram(holders[i]);
                for (i=0;i<2;++i) {
                    if (!ExecWaitProgram(holders[i],&result) || result.secondary!=304) { FixtureChecks=0xfff6;return; }
                    holders[i]=0;
                }
            } else if (index==23) {
                BPTR file;
                if (b.cause || b.warning!=205 || !b.recovery || !deleteFailed) { FixtureChecks=0xfff8;return; }
                FixtureRecoveryShown=BasicBuildRecovery(e);
                file=Open(b.source,MODE_OLDFILE);
                if (!file || !Close(file) || !DeleteFile(b.source)) { FixtureChecks=0xfff7;return; }
            } else if (!b.stop || b.cause!=304 && target!=14) { FixtureChecks=0xfffd;return; }
            FixtureCompleted=index+1;FixtureHeld=0;settling=2;FixtureReady=0;
            ++FixtureChecks;return;
        }
    }
    if (BasicFilesWork()) return;
    if (settling) {
        if (--settling) return;
        content(e,1);recovery=1;
        b.serial=(0x80000000UL|((ULONG)index<<12)|0x400UL)-1;
        FixtureReady=index+1;return;
    }
    if (recovery) return; /* Host presses the real Run shortcut. */
    if (index==FIXTURE_LIMIT) {
        FixtureCleanup();
        FixtureFinished=1;return;
    }
    if (index==22) {
        holders[0]=ExecStartProgram("SYS:C/HOLD",NULL);
        holders[1]=ExecStartProgram("SYS:C/HOLD",NULL);
        if (!holders[0] || !holders[1]) {
            FixtureChecks=0xfff9;return;
        }
    }
    target=targets[index%11];
    content(e,0);
    mode=index%11==3 ? 128:index%11==4 ? 240:16;
    b.serial=(0x80000000UL|((ULONG)index<<12)|mode)-1;
    BasicBuildRequest(e,target==12 || target==13 ? BASIC_BUILD_PUBLISH:BASIC_BUILD_RUN);
}
