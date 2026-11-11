#include <gem.h>
#include <exec816/console-view.h>
#include <string.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService, AESUpdates, AESMouseHolds, AESLockCount, AESNativeBusy, AESPolicyGate, AESNativeReady;
volatile UWORD AESChecks, AESFailures, AESFirstFailure, AESReady, AESDone;
static struct Task *controller, *workers[3];
static ULONG wake, starts[3], hints[3];
static volatile UWORD tried, orderCount, order[3];

static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
    Permit();
}
#define CHECK(t) check((t) != 0)
#define UPDATES (*(volatile UWORD *)AESUpdates)
#define MOUSE (*(volatile UWORD *)AESMouseHolds)
#define QUEUED (*(volatile UBYTE *)AESLockCount)
#define NATIVE_BUSY (*(volatile UBYTE *)AESNativeBusy)
#define GATE (*(volatile UBYTE *)AESPolicyGate)
#define NATIVE_READY (*(volatile UBYTE *)AESNativeReady)

/* Test coordination only: the presenter has published its whole-turn boundary.
 * Keep inherited Forbid until the controlled caller operation has completed. */
static void await_gate(void)
{
    for (;;) {
        Forbid();
        if (GATE==1 && NATIVE_READY) return;
        Permit(); ExecYield();
    }
}

static void local_pairs(void)
{
    struct ExecAESContext *c=ExecAESContext();
    struct AESRequest older={0};
    struct MsgPort *reply=CreateMsgPort();
    struct Task *self=FindTask(NULL);
    ULONG sequence;
    WORD windows[AES_WINDOWS],i;
    CHECK(reply!=NULL);
    /* Maximum owned-window snapshot depth, with actual open window records. */
    for (i=0;i<AES_WINDOWS;++i) {
        windows[i]=wind_create(NAME|CLOSER|MOVER,32+i*16,32+i*8,128,64);
        CHECK(windows[i]>0);
        CHECK(wind_open(windows[i],32+i*16,32+i*8,128,64));
    }
    await_gate(); sequence=c->sequence;
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_update(BEG_CHECK|BEG_UPDATE));
    CHECK(wind_update(END_UPDATE));
    CHECK(wind_update(END_UPDATE));
    CHECK(c->sequence==sequence && c->updateDepth==0 && UPDATES==0);
    CHECK(self->tc_TDNestCnt==0);
    Permit();
    /* A closed scene gate sleeps and resumes the local END without RPC. */
    await_gate(); sequence=c->sequence;
    CHECK(wind_update(BEG_UPDATE));
    CHECK(c->sequence==sequence);
    GATE=0;
    CHECK(wind_update(END_UPDATE));
    CHECK(c->sequence==sequence && c->updateDepth==0);
    CHECK(self->tc_TDNestCnt==0);
    Permit();
    /* The same wait preserves local BEGIN/END and the caller's Forbid. */
    await_gate(); sequence=c->sequence; GATE=0;
    CHECK(wind_update(BEG_UPDATE));
    CHECK(c->sequence==sequence);
    Permit(); await_gate();
    CHECK(wind_update(END_UPDATE));
    CHECK(c->sequence==sequence && c->updateDepth==0);
    Permit();
    /* An older unadmitted request prevents a fresh TRY from jumping the port.
     * Deliberately malformed so admission replies without taking a lock. */
    older.message.mn_Length=sizeof(older);
    older.message.mn_ReplyPort=reply;
    await_gate(); sequence=c->sequence;
    PutMsg(c->service,&older.message);
    CHECK(!wind_update(BEG_CHECK|BEG_UPDATE));
    CHECK(c->diagnostic==AES_OK && c->sequence==sequence && !UPDATES);
    Permit();
    while (!GetMsg(reply)) Wait(1UL<<reply->mp_SigBit);
    CHECK(older.status==AES_MALFORMED);
    for (i=AES_WINDOWS;i>0;--i) {
        CHECK(wind_close(windows[i-1]));
        CHECK(wind_delete(windows[i-1]));
    }
    DeleteMsgPort(reply);
}

static void loop(UWORD who)
{
    WORD words[8] = {765, 1, 2, 3, 4, 5, 6, 7}, id;
    WORD code = who == 1 ? BEG_MCTRL : BEG_UPDATE;
    ULONG sequence;
    BYTE bit=AllocSignal(-1);
    CHECK(bit >= 0);
    starts[who]=1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id=appl_init();
    CHECK(id > 0);
    hints[who]=1UL<<ExecAESContext()->replies->mp_SigBit;
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    Wait(starts[who]);
    CHECK(wind_update(BEG_CHECK | BEG_UPDATE) == 0 && ExecAESDiagnostic() == AES_OK);
    CHECK(wind_update(BEG_CHECK | BEG_MCTRL) == 0 && ExecAESDiagnostic() == AES_OK);
    CHECK(wind_update(END_UPDATE) == 0 && ExecAESDiagnostic() == AES_IDENTITY);
    CHECK(wind_update(END_MCTRL) == 0 && ExecAESDiagnostic() == AES_IDENTITY);
    Forbid(); ++tried; Signal(controller, wake); Permit();
    Wait(starts[who]);
    sequence=ExecAESContext()->sequence;
    CHECK(wind_update(code) == 1);
    CHECK(ExecAESContext()->sequence==sequence);
    CHECK(!ExecAESContext()->busy);
    CHECK((SetSignal(0,starts[who]) & starts[who])!=0);
    Forbid(); order[orderCount++]=who; Permit();
    CHECK(evnt_timer(0, 0) == 1);
    CHECK(appl_write(id, 16, words) == 1);
    words[0]=0;
    CHECK(evnt_mesag(words) == 1 && words[0] == 765);
    if (who == 0) {
        CHECK(wind_update(BEG_UPDATE) == 1);
        CHECK(wind_update(BEG_MCTRL) == 1);
        /* Runtime exit releases nested update and explicit mouse holds. */
    } else if (who == 1) {
        /* Upgrade while an update waiter depends on this mouse owner. */
        CHECK(wind_update(BEG_UPDATE) == 1);
        CHECK(wind_update(END_UPDATE) == 1);
        /* Leave the explicit mouse hold for cooperative exit. */
    } else CHECK(wind_update(END_UPDATE) == 1);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); ++AESDone; Signal(controller, wake); RemTask(NULL);
}

void AESClientOne(void) { loop(0); }
void AESClientTwo(void) { loop(1); }
void AESClientThree(void) { loop(2); }
static void (*const entries[3])(void) = {AESClientOne, AESClientTwo, AESClientThree};

/* Stream replies and copied input progress while this producer owns UPDATE.
 * The renderer must remain blocked until END, with no synchronous paint wait. */
static void console_under_update(void)
{
    struct MsgPort *port=CreateMsgPort();
    struct IOStdReq *io=(struct IOStdReq *)CreateIORequest(port,sizeof(*io));
    static struct ExecConsoleViewSnapshot snapshot;
    static struct ExecConsoleViewInput input;
    static UBYTE text[192],result[4];
    ULONG view,old;
    UWORD i;
    CHECK(port && io);
    CHECK(OpenDevice("console.device",0,(struct IORequest *)io,0)==0);
    view=ExecConsoleViewSubscribe(0,wake);
    CHECK(view!=0);
    snapshot.first=0;
    CHECK(ExecConsoleViewSnapshot(view,&snapshot)==EXEC_CONSOLE_VIEW_OK);
    input.route=snapshot.route;
    old=snapshot.revision;
    CHECK(wind_update(BEG_UPDATE));
    memset(text,'Z',sizeof(text));
    io->io_Command=CMD_WRITE;io->io_Data=text;io->io_Length=sizeof(text);
    CHECK(DoIO((struct IORequest *)io)==0 && io->io_Actual==sizeof(text));
    CHECK(UPDATES==1);
    CHECK(ExecConsoleViewSnapshot(view,&snapshot)==EXEC_CONSOLE_VIEW_OK);
    CHECK(snapshot.revision!=old);
    CHECK(ExecConsoleViewAcknowledge(view,old)==EXEC_CONSOLE_VIEW_STALE);
    /* A full queue backpressures copied bytes, retaining a durable loss hint. */
    input.kind=EXEC_CONSOLE_VIEW_INPUT_BYTES;input.count=1;input.bytes[0]='q';
    Forbid();
    for (i=0;i<8;++i) CHECK(ExecConsoleViewInput(view,&input)==EXEC_CONSOLE_VIEW_OK);
    CHECK(ExecConsoleViewInput(view,&input)==EXEC_CONSOLE_VIEW_RESOURCE);
    input.kind=EXEC_CONSOLE_VIEW_INPUT_LOSS;
    CHECK(ExecConsoleViewInput(view,&input)==EXEC_CONSOLE_VIEW_OK);
    Permit();
    io->io_Command=CMD_READ;io->io_Data=result;io->io_Length=sizeof(result);
    CHECK(DoIO((struct IORequest *)io)==1 && io->io_Actual==0);
    io->io_Command=CMD_CLEAR;io->io_Length=0;
    CHECK(DoIO((struct IORequest *)io)==0);
    input.kind=EXEC_CONSOLE_VIEW_INPUT_BYTES;input.count=1;input.bytes[0]='R';
    CHECK(ExecConsoleViewInput(view,&input)==EXEC_CONSOLE_VIEW_OK);
    io->io_Command=CMD_READ;io->io_Length=sizeof(result);
    CHECK(DoIO((struct IORequest *)io)==0 && io->io_Actual==1 && result[0]=='R');
    SendIO((struct IORequest *)io);AbortIO((struct IORequest *)io);
    CHECK(WaitIO((struct IORequest *)io)==IOERR_ABORTED && io->io_Actual==0);
    CHECK(wind_update(END_UPDATE));
    CHECK(ExecConsoleViewUnsubscribe(view)==EXEC_CONSOLE_VIEW_OK);
    CloseDevice((struct IORequest *)io);
    DeleteIORequest((struct IORequest *)io);DeleteMsgPort(port);
}

UWORD AESRun(void)
{
    UWORD i, position, round;
    WORD words[8] = {876, 1, 2, 3, 4, 5, 6, 7}, id;
    ULONG available=AvailMem(0);
    BYTE bit=AllocSignal(-1);
    CHECK(bit >= 0);
    controller=FindTask(NULL);
    wake=1UL << bit;
    CHECK(wind_update(BEG_UPDATE) == 0);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id=appl_init();
    CHECK(id > 0);
    CHECK(wind_update(END_UPDATE) == 0 && ExecAESDiagnostic() == AES_IDENTITY);
    CHECK(wind_update(END_MCTRL) == 0 && ExecAESDiagnostic() == AES_IDENTITY);
    CHECK(wind_update(4) == 0 && ExecAESDiagnostic() == AES_UNSUPPORTED);
    CHECK(wind_update(BEG_CHECK | END_UPDATE) == 0 && ExecAESDiagnostic() == AES_UNSUPPORTED);
    local_pairs();
    console_under_update();
    /* Startup paint may still own a native token: wait before testing recurse. */
    CHECK(wind_update(BEG_UPDATE) == 1);
    CHECK(wind_update(BEG_CHECK | BEG_UPDATE) == 1);
    CHECK(UPDATES == 2 && MOUSE == 0);
    CHECK(wind_update(BEG_MCTRL) == 1);
    CHECK(wind_update(BEG_CHECK | BEG_MCTRL) == 1);
    CHECK(UPDATES == 2 && MOUSE == 2);
    CHECK(wind_update(END_UPDATE) == 1);
    CHECK(wind_update(END_MCTRL) == 1);
    CHECK(UPDATES == 1 && MOUSE == 1);
    UPDATES=0xffff;
    CHECK(wind_update(BEG_UPDATE) == 0 && ExecAESDiagnostic() == AES_OVERFLOW);
    CHECK(UPDATES == 0xffff && MOUSE == 1);
    UPDATES=1;
    MOUSE=0xffff;
    CHECK(wind_update(BEG_MCTRL) == 0 && ExecAESDiagnostic() == AES_OVERFLOW);
    CHECK(MOUSE == 0xffff && UPDATES == 1);
    MOUSE=1;
    for (round=0; round<2; ++round) {
        AESReady=AESDone=tried=orderCount=0;
        if (round) {
            await_gate(); NATIVE_BUSY=1; GATE=0; Permit();
        }
        for (i=0; i<3; ++i) {
            workers[i]=CreateTask("AES lock peer", 1, (APTR)entries[i], 1024UL);
            CHECK(workers[i] != NULL);
        }
        while (AESReady < 3) Wait(wake);
        for (i=0; i<3; ++i) Signal(workers[i], starts[i]);
        while (tried < 3) Wait(wake);
        CHECK(UPDATES == (round ? 0 : 1) && MOUSE == (round ? 0 : 1));
        for (position=0; position<3; ++position) {
            i=round ? 2-position : position;
            Signal(workers[i], starts[i]);
            /* Diagnostic coordination only. Production lock waits never poll. */
            while (QUEUED < position+1) ExecYield();
        }
        CHECK(QUEUED == 3 && orderCount == 0);
        /* A wake hint cannot grant ownership; unrelated signals must survive
         * the private lock wait, even when both arrive before Wait itself. */
        for (i=0;i<3;++i) Signal(workers[i],hints[i]|starts[i]);
        CHECK(evnt_timer(30, 0) == 1);
        CHECK(appl_write(id, 16, words) == 1);
        CHECK(evnt_mesag(words) == 1 && words[0] == 876);
        if (!round) {
            CHECK(wind_update(END_UPDATE) == 1);
            CHECK(evnt_timer(0, 0) == 1);
            CHECK(QUEUED == 3 && orderCount == 0);
            CHECK(wind_update(END_MCTRL) == 1);
        } else {
            NATIVE_BUSY=0;
            /* A new try must not jump ahead of already eligible queued peers. */
            CHECK(wind_update(BEG_CHECK | BEG_UPDATE) == 0);
        }
        while (AESDone < 3) Wait(wake);
        CHECK(orderCount == 3);
        for (i=0; i<3; ++i) CHECK(order[i] == (round ? 2-i : i));
        CHECK(UPDATES == 0 && MOUSE == 0 && QUEUED == 0);
    }
    {
        WORD control[5] = {107, 1, 1, 0, 0}, global[15], input, result;
        AESPB pb = {control, global, &input, &result, NULL, NULL};
        input=BEG_UPDATE;
        aes_call(&pb);
        CHECK(result == 1);
        input=END_UPDATE;
        aes_call(&pb);
        CHECK(result == 1);
    }
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
