#include <gem.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include "aes_timer_vectors.h"

ULONG AESService, AESClock, AESPark;
volatile UWORD AESChecks, AESFailures, AESReady, AESDone, AESFirstFailure;
volatile ULONG AESBurns;
UWORD AESFault;
static struct Task *controller;
static ULONG wake;
static volatile UBYTE stopBurn, burnDone;
static struct MsgPort *ports[4];

static void check(BOOL okay)
{
    Forbid();
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure = AESChecks; }
    Permit();
}
#define CHECK(t) check((t) != 0)
#define TICKS (*(volatile ULONG *)AESClock)

/* Test-only boundary after the full duration has been converted. The real
 * device still owns publication, expiry/error and terminal collection. */
void AESBeforeSend(struct ExecAESContext *c)
{
    if (AESFault == 1) {
        ULONG delta = c->timer.alarm->ticks_lo - TICKS;
        CHECK(delta > 200000000UL && delta < 300000000UL);
        c->timer.alarm->ticks_hi = c->timer.alarm->ticks_lo = 0;
    } else if (AESFault == 2) c->timer.alarm->tc_Request.io_Command = 0;
}

void AESAfterRead(struct ExecAESContext *c) {}
void AESBeforeWait(struct ExecAESContext *c, ULONG mask) {}

static void client(UWORD who)
{
    UWORD i;
    struct ExecAESContext *c;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    c = ExecAESContext();
    CHECK(ExecAESTimerRead(c));
    ports[who] = c->timer.port;
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    for (i = 0; i < 12; ++i) {
        CHECK(evnt_timer(20, 0) == 1);
        CHECK(c->timer.state == AES_ALARM_IDLE);
        CHECK(c->sequence == 1);
    }
    CHECK(ExecAESDetach());
    Forbid(); ++AESDone; Signal(controller, wake); RemTask(NULL);
}

void AESClientOne(void) { client(0); }
void AESClientTwo(void) { client(1); }
void AESClientThree(void) { client(2); }
void AESClientFour(void) { client(3); }
void AESBurn(void)
{
    while (!stopBurn) ++AESBurns;
    Forbid(); burnDone = 1; Signal(controller, wake); RemTask(NULL);
}
static void (*const entries[4])(void) = {
    AESClientOne, AESClientTwo, AESClientThree, AESClientFour
};

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct MsgPort *port;
    struct TimerClockRequest *requests[16];
    ULONG available = AvailMem(0), before, sequence;
    UWORD i, j;
    BYTE bit = AllocSignal(-1);
    WORD id, words[8] = {123, 1, 2, 3, 4, 5, 6, 7};
    CHECK(bit >= 0);
    controller = FindTask(NULL);
    wake = 1UL << bit;
    CHECK(timer_vectors() == 0);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    c = ExecAESContext();
    CHECK(c->timer.port == NULL);
    sequence = c->sequence;
    before = TICKS;
    CHECK(evnt_timer(0, 0) == 1);
    CHECK(TICKS-before >= 1 && c->sequence == sequence);
    before = TICKS;
    CHECK(evnt_timer(30, 0) == 1);
    CHECK(TICKS-before >= 3 && c->sequence == sequence);
    CHECK(c->timer.state == AES_ALARM_IDLE && GetMsg(c->timer.port) == NULL);
    {
        WORD control[5] = {24, 2, 1, 0, 0}, global[15], in[2] = {0, 0}, result;
        AESPB pb = {control, global, in, &result, NULL, NULL};
        aes_call(&pb);
        CHECK(result == 1 && c->sequence == sequence && global[2] == c->gemId);
    }
    AESFault = 1;
    CHECK(evnt_timer(0xffff, 0xffff) == 1);
    AESFault = 2;
    CHECK(evnt_timer(10, 0) == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
    CHECK(c->timer.state == AES_ALARM_IDLE);
    AESFault = 0;
    CHECK(appl_exit() == 1 && appl_init() > 0);
    AESFault = 4;
    CHECK(evnt_timer(10, 0) == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
    CHECK(c->timer.port == NULL && c->timer.query == NULL && c->timer.alarm == NULL);
    AESFault = 0;
    CHECK(appl_exit() == 1);

    /* Eight competing originals fill all opens; the presenter owns none. */
    port = CreateMsgPort();
    CHECK(port != NULL);
    for (i = 0; i < 8; ++i) {
        requests[i] = (struct TimerClockRequest *)CreateIORequest(port, sizeof(*requests[i]));
        CHECK(requests[i] != NULL);
        CHECK(OpenDevice("timer.device", UNIT_VBLANK, &requests[i]->tc_Request, 0) == 0);
    }
    id = appl_init();
    CHECK(id > 0);
    CHECK(evnt_timer(0, 0) == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
    CHECK(appl_write(id, 16, words) == 1);
    words[0] = 0;
    CHECK(evnt_mesag(words) == 1 && words[0] == 123);
    for (i = 0; i < 8; ++i) {
        CloseDevice(&requests[i]->tc_Request);
        DeleteIORequest(&requests[i]->tc_Request);
    }
    CHECK(appl_exit() == 1 && appl_init() > 0);
    CHECK(evnt_timer(0, 0) == 1);

    /* Sixteen real borrowed alarms fill pending capacity without additional
     * opens. Reuse is legal only after exact completion collection. */
    for (i = 0; i < 16; ++i) {
        requests[i] = (struct TimerClockRequest *)CreateIORequest(c->timer.port, sizeof(*requests[i]));
        CHECK(requests[i] != NULL);
        requests[i]->tc_Request.io_Device = c->timer.query->tc_Request.io_Device;
        requests[i]->tc_Request.io_Unit = c->timer.query->tc_Request.io_Unit;
        requests[i]->tc_Request.io_Command = TD_WAITUNTIL;
        requests[i]->ticks_hi = 100;
        requests[i]->ticks_lo = 0;
        SendIO(&requests[i]->tc_Request);
    }
    CHECK(evnt_timer(1000, 0) == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
    for (i = 0; i < 16; ++i) {
        AbortIO(&requests[i]->tc_Request);
        CHECK(WaitIO(&requests[i]->tc_Request) == IOERR_ABORTED);
        requests[i]->tc_Request.io_Device = requests[i]->tc_Request.io_Unit = NULL;
        DeleteIORequest(&requests[i]->tc_Request);
    }
    DeleteMsgPort(port);
    CHECK(ExecAESDetach());
    for (i = 0; i < 4; ++i)
        CHECK(CreateTask("AES timer", 0, (APTR)entries[i], 1024UL) != NULL);
    CHECK(CreateTask("CPU peer", 0, (APTR)AESBurn, 1024UL) != NULL);
    while (AESReady < 4) Wait(wake);
    for (i = 0; i < 4; ++i)
        for (j = i+1; j < 4; ++j) CHECK(ports[i] != ports[j]);
    while (AESDone < 4) Wait(wake);
    stopBurn = 1;
    while (!burnDone) Wait(wake);
    CHECK(AESBurns > 0);
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
