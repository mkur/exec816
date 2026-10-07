/* Resident proof applications. Startup and command control stay outside their
 * GEM event loops; the root remains the DOS Process that performs disk I/O. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESCommand, AESPhase, AESPeerPhase, AESChecks, AESFailures;
volatile UWORD AESReady, AESDone, AESFirstFailure, AESMessages, AESTimers, AESRestarts;
volatile ULONG AESBurns;
/* Diagnostic command 7 has an external, frame-anchored offer source. These
 * counters never throttle that source: lag remains visible as a backlog. */
volatile UWORD AESOffered, AESStarted, AESCompleted;
static UWORD notified;
static struct ExecAESContext *clientContexts[2];
static volatile UWORD quiescent;
static volatile UBYTE retireAllowed[2];

static ULONG held_bytes(struct ExecAESContext *c)
{
    ULONG bytes = ((sizeof(*c)+7UL) & ~7UL) + 2*((sizeof(struct MsgPort)+7UL) & ~7UL)
        + ((AES_QUEUE_DEPTH * sizeof(struct AESDelivery) + sizeof(struct AESGuiDelivery) + 7UL) & ~7UL);
    if (c->timer.port) bytes += (sizeof(struct MsgPort)+7UL) & ~7UL;
    if (c->timer.query) bytes += (sizeof(struct TimerClockRequest)+7UL) & ~7UL;
    if (c->timer.alarm) bytes += (sizeof(struct TimerClockRequest)+7UL) & ~7UL;
    return bytes;
}

static struct Task *controller, *workers[2];
static ULONG wake, starts[2];
static WORD ids[2];
static volatile UWORD issued, stopping;
static UWORD reverse;
static WORD previousIds[2];
static BYTE controllerBit;
static volatile UWORD checks[3];

static void check(UWORD who, BOOL okay)
{
    /* Each Task writes its own counter. Successful assertions must not add
     * scheduling gates to the workload whose latency we are measuring. */
    ++checks[who];
    if (!okay) {
        Forbid();
        ++AESFailures;
        if (!AESFirstFailure) AESFirstFailure=checks[0]+checks[1]+checks[2];
        Permit();
    }
}
#define CHECK(t) check(who, (t) != 0)

static void holder(UWORD command)
{
    UWORD who=0;
    WORD words[8], x, y, buttons, keys, key, clicks, event;
    WORD code=command == 1 ? BEG_UPDATE : BEG_MCTRL;
    CHECK(wind_update(code) == 1);
    AESPhase=1;
    event=evnt_multi(MU_MESAG | MU_TIMER, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, words,
                    20000, 0, &x, &y, &buttons, &keys, &key, &clicks);
    CHECK(event == MU_MESAG && words[0] == 765 && words[1] == ids[1]);
    ++AESMessages;
    AESPhase=2;
    /* Physical gesture setup consumes over four seconds in the integration
     * fixture. Leave a bounded drawing window before automatic unlock. This
     * hold tests independent progress, not an input-latency acceptance limit. */
    CHECK(evnt_timer(8000, 0) == 1);
    ++AESTimers;
    CHECK(wind_update(code == BEG_UPDATE ? END_UPDATE : END_MCTRL) == 1);
}

static void peer(void)
{
    UWORD who=1;
    WORD words[8] = {765, 0, 2, 3, 4, 5, 6, 7};
    UWORD i;
    for (i=0; i<100 && AESPhase != 1; ++i) CHECK(evnt_timer(20, 0) == 1);
    CHECK(AESPhase == 1);
    CHECK(evnt_timer(80, 0) == 1);
    words[1]=ids[1];
    CHECK(appl_write(ids[0], 16, words) == 1);
    for (i=0; i<12; ++i) {
        CHECK(evnt_timer(20, 0) == 1);
        ++AESTimers;
        CHECK(appl_write(ids[1], 16, words) == 1);
        words[0]=0;
        CHECK(evnt_mesag(words) == 1 && words[0] == 765);
        ++AESMessages;
    }
}

static WORD events(WORD *words, UWORD milliseconds)
{
    WORD x,y,b,k,key,clicks;
    return evnt_multi(MU_MESAG | MU_TIMER,0,0,0,0,0,0,0,0,0,0,0,0,0,
                      words,milliseconds,0,&x,&y,&b,&k,&key,&clicks);
}

static void cpu(UWORD who)
{
    UWORD i;
    if (who == 0) {
        AESPhase=1;
        AESBurns=0;
        /* Deliberately no ExecYield, Wait or GEM call in this CPU-only phase. */
        while (AESPeerPhase < 2) ++AESBurns;
        CHECK(AESBurns > 0);
    } else {
        for (i=0; i<25; ++i) { CHECK(evnt_timer(20,0) == 1); ++AESTimers; }
        AESPeerPhase=2;
    }
}

static void exchange(UWORD who, BOOL continuous, BOOL paced)
{
    WORD words[8] = {0,0,2,3,4,5,6,7}, event;
    UWORD sequence=0;
    if (who == 0) AESPhase=1;
    while (!stopping && (continuous || sequence < 64)) {
        if (who == 0) {
            if (paced) {
                while (!stopping && sequence == AESOffered) Wait(starts[0]);
                if (stopping) break;
                AESStarted=sequence+1;
            }
            words[0]=sequence;words[1]=ids[0];
            event=appl_write(ids[1],16,words);
            CHECK(event == 1 || stopping);
            if (!event) break;
            event=events(words,continuous ? 250 : 5000);
            if (!stopping) CHECK((event & MU_MESAG) && words[0] == sequence && words[1] == ids[1]);
            ++AESMessages;
            if (continuous || (sequence & 3) == 0) {
                CHECK(evnt_timer(continuous ? 100 : 0,0) == 1);
                ++AESTimers;
            }
            ++sequence;
            if (paced) AESCompleted=sequence;
        } else {
            event=events(words,paced ? 5000 : continuous ? 100 : 5000);
            if (stopping) break;
            CHECK(event != 0);
            if (event & MU_MESAG) {
                CHECK(words[0] == sequence && words[1] == ids[0]);
                words[1]=ids[1];
                event=appl_write(ids[0],16,words);
                CHECK(event == 1 || stopping);
                ++AESMessages;++sequence;
            } else CHECK(continuous);
        }
    }
}

static void task(UWORD who)
{
    BYTE bit=AllocSignal(-1);
    CHECK(bit >= 0);
    starts[who]=1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    ids[who]=appl_init();
    CHECK(ids[who] > previousIds[who]);
    previousIds[who]=ids[who];
    clientContexts[who]=ExecAESContext();
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    for (;;) {
        Wait(starts[who]);
        if (stopping) break;
        if (issued == 3) cpu(who);
        else if (issued == 4 || issued == 5 || issued == 7)
            exchange(who,issued != 4,issued == 7);
        else if (who == 0) holder(issued); else peer();
        if (who == 0) AESPhase=3; else AESPeerPhase=3;
        /* The paced sender may consume the stop hint in its offer wait. */
        if (stopping) break;
    }
    /* Finish the current GEM call before the controller snapshots resources.
     * Signals are hints; a stale start bit cannot grant retirement. */
    Forbid(); ++quiescent; Signal(controller, wake); Permit();
    while (!retireAllowed[who]) Wait(starts[who]);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); ++AESDone; Signal(controller, wake); RemTask(NULL);
}

void AESClientOne(void) { task(0); }
void AESClientTwo(void) { task(1); }

UWORD AESStart(void)
{
    UWORD who=2;
    controller=FindTask(NULL);
    controllerBit=AllocSignal(-1);
    CHECK(controllerBit >= 0);
    wake=1UL << controllerBit;
    AESReady=AESDone=AESPhase=AESPeerPhase=AESCommand=issued=stopping=quiescent=0;
    retireAllowed[0]=retireAllowed[1]=0;
    AESOffered=AESStarted=AESCompleted=notified=0;
    workers[0]=CreateTask("GEM update client", 1, (APTR)AESClientOne, 1024UL);
    workers[1]=CreateTask("GEM event client", 1, (APTR)AESClientTwo, 1024UL);
    CHECK(workers[0] && workers[1]);
    while (AESReady != 2) Wait(wake);
    return AESFailures;
}

UWORD AESStop(void);

UWORD AESPump(void)
{
    UWORD who=2;
    if (AESCommand == 6) {
        CHECK(AESStop() == 0);
        reverse^=1;
        CHECK(AESStart() == 0);
        ++AESRestarts;
        return AESFailures;
    }
    if (AESCommand != issued) {
        CHECK(issued == 0 || (AESPhase == 3 && AESPeerPhase == 3));
        issued=AESCommand;
        AESPhase=AESPeerPhase=0;
        Signal(workers[0], starts[0]);
        Signal(workers[1], starts[1]);
    }
    if (issued == 7 && notified != AESOffered) {
        notified=AESOffered;
        Signal(workers[0], starts[0]);
    }
    return AESFailures;
}

UWORD AESStop(void)
{
    UWORD who=2;
    ULONG available, released;
    CHECK(issued == 0 || issued == 5 || issued == 7 || (AESPhase == 3 && AESPeerPhase == 3));
    stopping=1;
    Signal(workers[0], starts[0]);
    Signal(workers[1], starts[1]);
    while (quiescent != 2) Wait(wake);
    available=AvailMem(0);
    released=held_bytes(clientContexts[0])+held_bytes(clientContexts[1]);
    retireAllowed[reverse]=1;
    Signal(workers[reverse], starts[reverse]);
    while (AESDone != 1) Wait(wake);
    retireAllowed[1-reverse]=1;
    Signal(workers[1-reverse], starts[1-reverse]);
    while (AESDone != 2) Wait(wake);
    FreeSignal(controllerBit);
    /* Compare only retirement: the DOS Process may have opened files since startup. */
    CHECK(AvailMem(0) == available + released);
    AESChecks=checks[0]+checks[1]+checks[2];
    return AESFailures;
}
