#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESReady, AESDone;
volatile UWORD AESGuiCommand;
volatile ULONG AESGuiClient;

#define CHECK(t) do { ++AESChecks; if (!(t)) ++AESFailures; } while (0)

static void produce(UWORD command)
{
    struct ExecAESContext *c = ExecAESContext();
    AESGuiClient = c->identity;
    AESGuiCommand = command;
    Signal(c->directory->owner, c->directory->mask);
    while (AESGuiCommand) Wait(1UL << c->receiving->mp_SigBit);
}

static void notice(WORD kind, WORD handle, WORD x, WORD y, WORD w, WORD h)
{
    WORD words[8];
    CHECK(evnt_mesag(words) == 1);
    CHECK(words[0] == kind);
    CHECK(words[1] == 0 && words[2] == 0);
    CHECK(words[3] == handle);
    CHECK(words[4] == x && words[5] == y);
    CHECK(words[6] == w && words[7] == h);
}

void AESClientOne(void) {}
void AESClientTwo(void) {}

UWORD AESRun(void)
{
    WORD words[8] = {0}, id, mx, my, mb, ks, kr, br;
    UWORD i;
    ULONG available = AvailMem(0);
    struct ExecAESContext *c;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id = appl_init();
    CHECK(id > 0);
    c = ExecAESContext();
    produce(1);
    for (i = 0; i < 16; ++i) {
        words[0] = i;
        CHECK(appl_write(id, 16, words));
    }
    CHECK(!appl_write(id, 16, words) && ExecAESDiagnostic() == AES_RESOURCE);
    produce(2);
    CHECK(c->endpoint->freeRecords == 0);
    CHECK(c->endpoint->guiFree == 0);
    CHECK(c->endpoint->guiWaiting == 1);
    for (i = 0; i < 16; ++i) {
        CHECK(evnt_mesag(words));
        CHECK(words[0] == i);
    }
    notice(AES_WM_REDRAW, 7, 10, 20, 30, 40);
    notice(AES_WM_REDRAW, 7, 90, 25, 20, 20);
    notice(AES_WM_TOPPED, 7, 0, 0, 0, 0);
    notice(AES_WM_MOVED, 7, 31, 41, 100, 100);
    notice(AES_WM_CLOSED, 7, 0, 0, 0, 0);
    CHECK(c->endpoint->freeRecords == 0xffff);
    CHECK(c->endpoint->guiFree == 1);
    CHECK(c->endpoint->guiWaiting == 0);

    /* A service-looking appl_write is not a stale GUI notification. */
    words[0] = AES_WM_REDRAW;
    words[3] = 7;
    CHECK(appl_write(id, 16, words));
    produce(3);
    CHECK(evnt_multi(MU_MESAG | MU_TIMER, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, words, 0, 0,
        &mx, &my, &mb, &ks, &kr, &br) == (MU_MESAG | MU_TIMER));
    CHECK(words[0] == AES_WM_REDRAW && words[3] == 7);
    notice(AES_WM_REDRAW, 8, 110, 120, 10, 11);

    /* No consumer is needed while exit drains a queued GUI record. */
    produce(2);
    CHECK(appl_exit());
    CHECK(appl_init() > id);
    CHECK(ExecAESContext()->endpoint->guiFree == 1);
    CHECK(ExecAESDetach());
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
