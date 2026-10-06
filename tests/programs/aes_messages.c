#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService, AESPark;
#define PARK (*(volatile UBYTE *)AESPark)
volatile UWORD AESChecks, AESFailures, AESReady, AESDone;
static struct Task *controller;
static ULONG wake;
static ULONG starts[2];
static WORD ids[2];

static void check(BOOL okay)
{
    Forbid(); ++AESChecks; if (!okay) ++AESFailures; Permit();
}
#define CHECK(t) check((t) != 0)

static void fill(WORD *words, WORD value)
{
    UWORD i;
    for (i = 0; i < 8; ++i) words[i] = value+i;
}

static void contents(WORD *words, WORD value)
{
    UWORD i;
    for (i = 0; i < 8; ++i) CHECK(words[i] == value+i);
}

static void loop(UWORD who)
{
    WORD words[8];
    UWORD i;
    BYTE bit = AllocSignal(-1);
    ULONG start = 1UL << bit;
    starts[who] = start;
    CHECK(bit >= 0);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    ids[who] = appl_init();
    CHECK(ids[who] > 0);
    /* Both IDs are supplied by startup; no application discovery extension. */
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    Wait(start);
    for (i = 0; i < 64; ++i) {
        if (who == 0) {
            fill(words, (WORD)(i*16));
            CHECK(appl_write(ids[1], 16, words) == 1);
            fill(words, -30000); /* Destination must own the accepted copy. */
            CHECK(evnt_mesag(words) == 1);
            contents(words, (WORD)(i*16+8));
        } else {
            CHECK(evnt_mesag(words) == 1);
            contents(words, (WORD)(i*16));
            fill(words, (WORD)(i*16+8));
            CHECK(appl_write(ids[0], 16, words) == 1);
        }
    }
    PARK = 0;
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); ++AESDone; Signal(controller, wake); RemTask(NULL);
}

void AESClientOne(void) { loop(0); }
void AESClientTwo(void) { loop(1); }

UWORD AESRun(void)
{
    WORD words[8], id;
    UWORD i;
    struct Task *one, *two;
    ULONG available = AvailMem(0);
    BYTE bit = AllocSignal(-1);
    CHECK(bit >= 0);
    controller = FindTask(NULL);
    wake = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id = appl_init();
    CHECK(id > 0);
    PARK = 1;
    fill(words, 100);
    CHECK(!appl_write(id, 14, words) && ExecAESDiagnostic() == AES_MALFORMED);
    CHECK(!appl_write(id, 16, NULL) && ExecAESDiagnostic() == AES_MALFORMED);
    CHECK(!appl_write(-1, 16, words) && ExecAESDiagnostic() == AES_IDENTITY);
    CHECK(!appl_write(32767, 16, words) && ExecAESDiagnostic() == AES_IDENTITY);
    for (i = 0; i < 16; ++i) {
        fill(words, i*16);
        CHECK(appl_write(id, 16, words) == 1);
    }
    CHECK(!appl_write(id, 16, words) && ExecAESDiagnostic() == AES_RESOURCE);
    for (i = 0; i < 16; ++i) {
        fill(words, -1000);
        CHECK(evnt_mesag(words) == 1);
        contents(words, i*16);
    }
    fill(words, 1234);
    CHECK(appl_write(id, 16, words) == 1);
    CHECK(evnt_mesag(words) == 1);
    contents(words, 1234);
    {
        WORD control[5] = {12, 2, 1, 1, 0}, global[15], in[2] = {id, 16}, result;
        LONG addresses[1] = {(LONG)words};
        AESPB pb = {control, global, in, &result, addresses, NULL};
        aes_call(&pb);
        CHECK(result == 1);
        fill(words, -1);
        control[0] = 23; control[1] = 0;
        aes_call(&pb);
        CHECK(result == 1);
        contents(words, 1234);
    }
    /* Queue contents may be discarded on exit, then no ID can address them. */
    CHECK(appl_write(id, 16, words) == 1);
    PARK = 0;
    CHECK(appl_exit() == 1);
    CHECK(appl_init() > id);
    CHECK(!appl_write(id, 16, words) && ExecAESDiagnostic() == AES_IDENTITY);
    CHECK(ExecAESDetach());
    one = CreateTask("AES send", 0, (APTR)AESClientOne, 1024UL);
    two = CreateTask("AES receive", 0, (APTR)AESClientTwo, 1024UL);
    CHECK(one != NULL && two != NULL);
    while (AESReady < 2) Wait(wake);
    PARK = 1;
    Signal(two, starts[1]);
    ExecYield();
    Signal(one, starts[0]);
    while (AESDone < 2) Wait(wake);
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
