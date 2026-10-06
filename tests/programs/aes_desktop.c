/* Resident proof applications. Startup and command control stay outside their
 * GEM event loops; the root remains the DOS Process that performs disk I/O. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESCommand, AESPhase, AESPeerPhase, AESChecks, AESFailures;
volatile UWORD AESReady, AESDone, AESFirstFailure, AESMessages, AESTimers;
static struct Task *controller, *workers[2];
static ULONG wake, starts[2];
static WORD ids[2];
static UWORD issued, stopping;
static BYTE controllerBit;

static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
    Permit();
}
#define CHECK(t) check((t) != 0)

static void holder(UWORD command)
{
    WORD words[8], x, y, buttons, keys, key, clicks, event;
    WORD code=command == 1 ? BEG_UPDATE : BEG_MCTRL;
    CHECK(wind_update(code) == 1);
    AESPhase=1;
    event=evnt_multi(MU_MESAG | MU_TIMER, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, words,
                    20000, 0, &x, &y, &buttons, &keys, &key, &clicks);
    CHECK(event == MU_MESAG && words[0] == 765 && words[1] == ids[1]);
    ++AESMessages;
    AESPhase=2;
    CHECK(evnt_timer(6000, 0) == 1);
    ++AESTimers;
    CHECK(wind_update(code == BEG_UPDATE ? END_UPDATE : END_MCTRL) == 1);
}

static void peer(void)
{
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

static void task(UWORD who)
{
    BYTE bit=AllocSignal(-1);
    CHECK(bit >= 0);
    starts[who]=1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    ids[who]=appl_init();
    CHECK(ids[who] > 0);
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    for (;;) {
        Wait(starts[who]);
        if (stopping) break;
        if (who == 0) holder(issued); else peer();
        if (who == 0) AESPhase=3; else AESPeerPhase=3;
    }
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); ++AESDone; Signal(controller, wake); RemTask(NULL);
}

void AESClientOne(void) { task(0); }
void AESClientTwo(void) { task(1); }

UWORD AESStart(void)
{
    controller=FindTask(NULL);
    controllerBit=AllocSignal(-1);
    CHECK(controllerBit >= 0);
    wake=1UL << controllerBit;
    AESReady=AESDone=AESPhase=AESPeerPhase=AESCommand=issued=stopping=0;
    workers[0]=CreateTask("GEM update client", 1, (APTR)AESClientOne, 1024UL);
    workers[1]=CreateTask("GEM event client", 1, (APTR)AESClientTwo, 1024UL);
    CHECK(workers[0] && workers[1]);
    while (AESReady != 2) Wait(wake);
    return AESFailures;
}

UWORD AESPump(void)
{
    if (AESCommand != issued) {
        CHECK(issued == 0 || (AESPhase == 3 && AESPeerPhase == 3));
        issued=AESCommand;
        AESPhase=AESPeerPhase=0;
        Signal(workers[0], starts[0]);
        Signal(workers[1], starts[1]);
    }
    return AESFailures;
}

UWORD AESStop(void)
{
    ULONG available=AvailMem(0);
    CHECK(issued == 0 || (AESPhase == 3 && AESPeerPhase == 3));
    stopping=1;
    Signal(workers[0], starts[0]);
    Signal(workers[1], starts[1]);
    while (AESDone != 2) Wait(wake);
    FreeSignal(controllerBit);
    /* Compare only retirement: the DOS Process may have opened files since startup. */
    CHECK(AvailMem(0) == available + 432UL);
    return AESFailures;
}
