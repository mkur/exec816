#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService, AESMode, AESError, AESClock, AESAlarms, AESFour;
volatile UWORD AESChecks, AESFailures, AESReady, AESDone;
volatile UWORD AESFirstFailure;
volatile ULONG AESBurns;
static volatile UBYTE stopBurn, burnDone;
static struct Task *controller, *workers[4];
static ULONG wake, starts[4];
static UWORD phase;

static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure = AESChecks; }
    Permit();
}
#define CHECK(t) check((t) != 0)
#define MODE (*(volatile UBYTE *)AESMode)
#define ERROR (*(volatile UBYTE *)AESError)
#define TICKS (*(volatile UWORD *)AESClock)
#define ALARMS (*(volatile UWORD *)AESAlarms)

static WORD event(UWORD flags, ULONG ms, WORD *message, WORD slot)
{
    WORD x=-1, y=-1, b=-1, s=-1, k=-1, n=-1;
    WORD result = evnt_multi((WORD)flags, slot, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, message, (WORD)ms, (WORD)(ms >> 16),
        &x, &y, &b, &s, &k, &n);
    CHECK(x == 0 && y == 0 && b == 0 && s == 0 && k == 0 && n == 0);
    return result;
}

static void loop(UWORD who)
{
    WORD message[8] = {777, 1, 2, 3, 4, 5, 6, 7};
    WORD id, result;
    BYTE bit = AllocSignal(-1);
    CHECK(bit >= 0);
    starts[who] = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id = appl_init();
    CHECK(id > 0);
    if (phase == 7) CHECK(appl_write(id, 16, message) == 1);
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    Wait(starts[who]);
    result = event(phase == 7 ? MU_MESAG | MU_TIMER : MU_TIMER, 1000UL, message, who);
    if (phase == 7) {
        CHECK(result == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
        message[0] = -1;
        CHECK(evnt_mesag(message) == 1 && message[0] == 777);
    } else CHECK(result == MU_TIMER);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); ++AESDone; Signal(controller, wake); RemTask(NULL);
}

void AESClientOne(void) { loop(0); }
void AESClientTwo(void) { loop(1); }
void AESClientThree(void) { loop(2); }
void AESClientFour(void) { loop(3); }
void AESBurn(void)
{
    while (!stopBurn) ++AESBurns; /* Deliberately no Yield, Wait or gateway. */
    Forbid(); burnDone=1; Signal(controller, wake); RemTask(NULL);
}
static void (*const entries[4])(void) = {
    AESClientOne, AESClientTwo, AESClientThree, AESClientFour
};

UWORD AESRun(void)
{
    UWORD before, alarms, i;
    WORD id, old, message[8] = {1234, -2, 3, -4, 5, -6, 7, -8};
    WORD x, y, b, s, k, n;
    ULONG available = AvailMem(0);
    BYTE bit = AllocSignal(-1);
    CHECK(bit >= 0);
    controller = FindTask(NULL);
    wake = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id = appl_init();
    CHECK(id > 0);
    before = TICKS;
    CHECK(evnt_timer(0, 0) == 1);
    CHECK((UWORD)(TICKS-before) >= 1);
    before = TICKS;
    CHECK(evnt_timer(30, 0) == 1);
    CHECK((UWORD)(TICKS-before) >= 3);
    alarms = ALARMS;
    CHECK(event(MU_TIMER, 0, NULL, 0) == MU_TIMER);
    CHECK(ALARMS == alarms);
    CHECK(appl_write(id, 16, message) == 1);
    CHECK(event(MU_MESAG | MU_TIMER, 0, message, 0) == (MU_MESAG | MU_TIMER));
    CHECK(ALARMS == alarms && message[0] == 1234);
    CHECK(appl_write(id, 16, message) == 1);
    CHECK(event(MU_MESAG | MU_TIMER, 0xffffffffUL, message, 0) == MU_MESAG);
    CHECK(ALARMS == alarms);
    CHECK(event(MU_TIMER | MU_BUTTON, 0, message, 0) == 0);
    CHECK(ExecAESDiagnostic() == AES_UNSUPPORTED);
    CHECK(event(0, 0, message, 0) == 0 && ExecAESDiagnostic() == AES_UNSUPPORTED);
    CHECK(evnt_multi_moblk(MU_TIMER, 0, 0, 0, NULL, NULL, NULL, 0, 0,
        &x, &y, &b, &s, &k, &n) == MU_TIMER);
    {
        WORD control[5] = {25, 16, 7, 1, 0}, global[15], in[16], out[7];
        LONG addresses[1] = {0};
        AESPB pb = {control, global, in, out, addresses, NULL};
        /* Calypsi 5.18 omits implicit zeros for partial local initializers.
         * Populate the whole caller-owned parameter block explicitly. */
        for (i = 0; i < 16; ++i) in[i] = 0;
        in[0] = MU_TIMER;
        aes_call(&pb);
        CHECK(out[0] == MU_TIMER && global[2] == id);
        for (i = 1; i < 7; ++i) CHECK(out[i] == 0);
        control[0] = 333;
        aes_call(&pb);
        CHECK(out[0] == 0 && ExecAESDiagnostic() == AES_UNSUPPORTED);
    }
    MODE = 1;
    CHECK(evnt_timer(0xffff, 0xffff) == 1);
    MODE = 0;
    CHECK(appl_write(id, 16, message) == 1);
    MODE = 2;
    CHECK(event(MU_MESAG | MU_TIMER, 10, message, 0) == (MU_MESAG | MU_TIMER));
    MODE = 3;
    CHECK(evnt_timer(10, 0) == 0 && ExecAESDiagnostic() == AES_OVERFLOW);
    MODE = 0;
    CHECK(appl_write(id, 16, message) == 1);
    MODE = 4;
    CHECK(event(MU_MESAG | MU_TIMER, 0, message, 0) == 0);
    CHECK(ExecAESDiagnostic() == AES_TIMER_ERROR);
    MODE = 0;
    CHECK(evnt_mesag(message) == 1 && message[0] == 1234);
    ERROR = 0; /* Diagnostic recovery after all alarm ownership is settled. */
    MODE = 5;
    CHECK(evnt_timer(100, 0) == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
    MODE = 0;
    ERROR = 0;
    old = id;
    CHECK(ExecAESDetach());
    for (phase = 6; phase <= 7; ++phase) {
        AESReady = AESDone = 0;
        MODE = (UBYTE)phase;
        for (i = 0; i < 4; ++i) {
            workers[i] = CreateTask("AES timed", 1, (APTR)entries[i], 1024UL);
            CHECK(workers[i] != NULL);
        }
        while (AESReady < 4) Wait(wake);
        alarms = ALARMS;
        Forbid();
        for (i = 0; i < 4; ++i) Signal(workers[i], starts[i]);
        Permit();
        if (phase == 6) CHECK(CreateTask("CPU peer", 0, (APTR)AESBurn, 1024UL) != NULL);
        while (AESDone < 4) Wait(wake);
        CHECK(*(volatile UBYTE *)AESFour == 1);
        if (phase == 6) {
            stopBurn = 1;
            while (!burnDone) Wait(wake);
            CHECK(AESBurns > 0);
            CHECK(ALARMS == alarms+1);
        }
        MODE = 0;
        ERROR = 0;
    }
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > old);
    CHECK(evnt_timer(0, 0) == 1);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
