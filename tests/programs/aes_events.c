#include <gem.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include "aes_timer_vectors.h"

ULONG AESService, AESClock, AESPark;
volatile UWORD AESChecks, AESFailures, AESReady, AESDone, AESFirstFailure;
volatile ULONG AESBurns;
UWORD AESFault;
static struct Task *controller;
static ULONG wake, targetHigh, targetLow;
static UWORD sends, waits, reads, spurious, phase, cohort;
static volatile UBYTE stopBurn, burnDone;
#define PARK (*(volatile UBYTE *)AESPark)
#define TICKS (*(volatile ULONG *)AESClock)

static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure = AESChecks; }
    Permit();
}
#define CHECK(t) check((t) != 0)

/* Diagnostic publication at an exact wait/submit boundary. This uses the
 * admitted context's transport helpers, without recursively entering GEM. */
static void publish(struct ExecAESContext *c)
{
    struct AESEndpoint *destination;
    struct AESDelivery *record = ExecAESReserve(c, c->gemId, &destination);
    UWORD i;
    CHECK(record != NULL);
    for (i = 0; i < 8; ++i) record->words[i] = 777+i;
    ExecAESPublish(c, destination, record);
}

void AESAfterRead(struct ExecAESContext *c)
{
    ++reads;
    if (phase == 3) {
        c->timer.query->ticks_hi = 0xffffffffUL;
        c->timer.query->ticks_lo = 0xfffffffeUL;
    }
}

void AESBeforeSend(struct ExecAESContext *c)
{
    ++sends;
    targetHigh = c->timer.alarm->ticks_hi;
    targetLow = c->timer.alarm->ticks_lo;
    if (phase == 8) publish(c);
    if (AESFault == 2) c->timer.alarm->tc_Request.io_Command = 0;
}

void AESBeforeWait(struct ExecAESContext *c, ULONG mask)
{
    ++waits;
    if (phase == 5) { phase = 0; publish(c); }
    if (phase == 10) { phase = 0; publish(c); AESFault = 4; }
    if (phase == 6 && spurious) { --spurious; Signal(FindTask(NULL), mask); }
    if (phase == 9) {
        phase = 0;
        while (TICKS <= targetLow) ++AESBurns;
        publish(c);
    }
}

static WORD event(UWORD flags, ULONG ms, WORD *message)
{
    WORD x=-1, y=-1, b=-1, s=-1, k=-1, n=-1;
    WORD result=evnt_multi(flags, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        message, (WORD)ms, (WORD)(ms >> 16), &x, &y, &b, &s, &k, &n);
    CHECK((result ? (x == ExecAESContext()->endpoint->input->latest.x &&
                     y == ExecAESContext()->endpoint->input->latest.y) : (x == 0 && y == 0)) &&
          b == 0 && s == 0 && k == 0 && n == 0);
    return result;
}

static void client(UWORD who)
{
    UWORD i;
    WORD words[8] = {777,1,2,3,4,5,6,7};
    struct ExecAESContext *c;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    c=ExecAESContext();
    CHECK(ExecAESTimerRead(c));
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    if (cohort == 1 && who == 0) {
        c->timer.error=AES_TIMER_ERROR;
        CHECK(appl_write(c->gemId,16,words) == 1);
        CHECK(event(MU_MESAG | MU_TIMER,0,words) == 0);
        CHECK(ExecAESDiagnostic() == AES_TIMER_ERROR);
        CHECK(evnt_mesag(words) == 1 && words[0] == 777);
    } else for (i=0; i<12; ++i) {
        CHECK(event(MU_TIMER,30,NULL) == MU_TIMER);
        CHECK(c->timer.state == AES_ALARM_IDLE && c->sequence == 1);
    }
    CHECK(ExecAESDetach());
    Forbid(); ++AESDone; Signal(controller,wake); RemTask(NULL);
}
void AESClientOne(void) { client(0); }
void AESClientTwo(void) { client(1); }
void AESClientThree(void) { client(2); }
void AESClientFour(void) { client(3); }
void AESBurn(void)
{
    while (!stopBurn) ++AESBurns;
    Forbid(); burnDone=1; Signal(controller,wake); RemTask(NULL);
}
static void (*const entries[4])(void)={AESClientOne,AESClientTwo,AESClientThree,AESClientFour};

UWORD AESRun(void)
{
    WORD id, words[8] = {777,1,2,3,4,5,6,7}, x,y,b,s,k,n;
    UWORD before, i;
    struct ExecAESContext *c;
    ULONG available=AvailMem(0), sequence;
    BYTE bit=AllocSignal(-1);
    CHECK(bit >= 0);
    controller=FindTask(NULL); wake=1UL << bit;
    CHECK(timer_vectors() == 0);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id=appl_init(); CHECK(id > 0);
    c=ExecAESContext(); sequence=c->sequence;
    PARK=1;
    before=sends;
    CHECK(event(MU_TIMER,0,NULL) == MU_TIMER && sends == before);
    CHECK(appl_write(id,16,words) == 1);
    CHECK(event(MU_MESAG | MU_TIMER,0,words) == (MU_MESAG | MU_TIMER));
    CHECK(sends == before && words[0] == 777);
    CHECK(appl_write(id,16,words) == 1);
    CHECK(event(MU_MESAG | MU_TIMER,0xffffffffUL,words) == MU_MESAG);
    CHECK(sends == before);
    CHECK(event(MU_TIMER | MU_BUTTON,0,words) == 0 && ExecAESDiagnostic() == AES_UNSUPPORTED);
    CHECK(event(0,0,words) == 0 && ExecAESDiagnostic() == AES_UNSUPPORTED);
    CHECK(event(MU_MESAG,0,NULL) == 0 && ExecAESDiagnostic() == AES_MALFORMED);
    CHECK(evnt_multi_moblk(MU_TIMER,0,0,0,NULL,NULL,NULL,0,0,&x,&y,&b,&s,&k,&n) == MU_TIMER);
    {
        WORD control[5]={25,16,7,1,0}, global[15], in[16], out[7];
        LONG addresses[1]={(LONG)words};
        AESPB pb={control,global,in,out,addresses,NULL};
        for (i=0; i<16; ++i) in[i]=0;
        in[0]=MU_MESAG | MU_TIMER;
        CHECK(appl_write(id,16,words) == 1);
        aes_call(&pb);
        CHECK(out[0] == (MU_MESAG | MU_TIMER) && global[2] == id);
        CHECK(out[1] == c->endpoint->input->latest.x);
        CHECK(out[2] == c->endpoint->input->latest.y);
        for (i=3; i<7; ++i) CHECK(out[i] == 0);
    }
    /* The message signal is already set, but timer-only Wait must sleep. */
    CHECK(appl_write(id,16,words) == 1);
    waits=0;
    CHECK(event(MU_TIMER,60,NULL) == MU_TIMER);
    CHECK(waits > 0 && waits <= 4);
    CHECK(evnt_mesag(words) == 1 && words[0] == 777);
    phase=5; waits=0;
    CHECK(evnt_mesag(words) == 1 && words[0] == 777 && waits == 1);
    phase=6; spurious=3; before=sends; reads=0;
    CHECK(event(MU_TIMER,500,NULL) == MU_TIMER);
    CHECK(spurious == 0 && sends == before+1);
    CHECK(reads == 1);
    CHECK(c->timer.alarm->ticks_hi == targetHigh && c->timer.alarm->ticks_lo == targetLow);
    phase=8; before=sends;
    CHECK(event(MU_MESAG | MU_TIMER,1000,words) == MU_MESAG);
    CHECK(sends == before+1 && c->timer.alarm->tc_Request.io_Error == IOERR_ABORTED);
    CHECK(c->timer.state == AES_ALARM_IDLE && GetMsg(c->timer.port) == NULL);
    phase=9; before=sends;
    CHECK(event(MU_MESAG | MU_TIMER,60,words) == (MU_MESAG | MU_TIMER));
    CHECK(sends == before+1 && c->timer.alarm->tc_Request.io_Error == 0);
    CHECK(c->timer.state == AES_ALARM_IDLE && GetMsg(c->timer.port) == NULL);
    phase=3;
    CHECK(appl_write(id,16,words) == 1);
    CHECK(event(MU_MESAG | MU_TIMER,10,words) == 0 && ExecAESDiagnostic() == AES_OVERFLOW);
    phase=0;
    CHECK(evnt_mesag(words) == 1 && words[0] == 777);
    CHECK(appl_write(id,16,words) == 1);
    AESFault=4;
    CHECK(event(MU_MESAG | MU_TIMER,0,words) == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
    AESFault=0;
    CHECK(evnt_mesag(words) == 1 && words[0] == 777);
    CHECK(c->sequence == sequence);
    PARK=0;
    CHECK(appl_exit() == 1 && appl_init() > id);
    /* Clock failure after alarm publication must retire it and preserve
     * the arriving message before closing the private timer resources. */
    phase=10;
    CHECK(event(MU_MESAG | MU_TIMER,1000,words) == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
    AESFault=0;
    CHECK(evnt_mesag(words) == 1 && words[0] == 777);
    CHECK(c->timer.state == AES_ALARM_IDLE && c->timer.port == NULL);
    CHECK(appl_exit() == 1 && appl_init() > id);
    AESFault=2;
    CHECK(event(MU_TIMER,100,NULL) == 0 && ExecAESDiagnostic() == AES_TIMER_ERROR);
    AESFault=0;
    CHECK(ExecAESDetach());
    for (cohort=0; cohort<2; ++cohort) {
        AESReady=AESDone=0; stopBurn=burnDone=0;
        for (i=0; i<4; ++i) CHECK(CreateTask("AES events",0,(APTR)entries[i],1024UL) != NULL);
        CHECK(CreateTask("CPU peer",0,(APTR)AESBurn,1024UL) != NULL);
        while (AESDone < 4) Wait(wake);
        stopBurn=1; while (!burnDone) Wait(wake);
    }
    CHECK(AESBurns > 0);
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
