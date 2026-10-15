#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService, AESUpdates, AESMouseHolds, AESLockCount, AESNativeBusy, AESPolicyGate;
volatile UWORD AESChecks, AESFailures, AESFirstFailure, AESReady, AESDone;
static struct Task *controller, *workers[3];
static ULONG wake, starts[3];
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

/* Test coordination only: the presenter has published its whole-turn boundary.
 * Keep inherited Forbid until the controlled caller operation has completed. */
static void await_gate(void)
{
    for (;;) {
        Forbid();
        if (GATE==1) return;
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
    /* Local BEGIN followed by a forced unavailable-gate RPC END. */
    await_gate(); sequence=c->sequence;
    CHECK(wind_update(BEG_UPDATE));
    CHECK(c->sequence==sequence);
    GATE=0;
    CHECK(wind_update(END_UPDATE));
    CHECK(c->sequence==sequence+1 && c->updateDepth==0);
    CHECK(self->tc_TDNestCnt==0);
    Permit();
    /* RPC BEGIN followed by local END: transport stays consecutive. */
    await_gate(); sequence=c->sequence; GATE=0;
    CHECK(wind_update(BEG_UPDATE));
    CHECK(c->sequence==sequence+1);
    Permit(); await_gate();
    CHECK(wind_update(END_UPDATE));
    CHECK(c->sequence==sequence+1 && c->updateDepth==0);
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
    BYTE bit=AllocSignal(-1);
    CHECK(bit >= 0);
    starts[who]=1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id=appl_init();
    CHECK(id > 0);
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    Wait(starts[who]);
    CHECK(wind_update(BEG_CHECK | BEG_UPDATE) == 0 && ExecAESDiagnostic() == AES_OK);
    CHECK(wind_update(BEG_CHECK | BEG_MCTRL) == 0 && ExecAESDiagnostic() == AES_OK);
    CHECK(wind_update(END_UPDATE) == 0 && ExecAESDiagnostic() == AES_IDENTITY);
    CHECK(wind_update(END_MCTRL) == 0 && ExecAESDiagnostic() == AES_IDENTITY);
    Forbid(); ++tried; Signal(controller, wake); Permit();
    Wait(starts[who]);
    CHECK(wind_update(code) == 1);
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
