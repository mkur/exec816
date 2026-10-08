#include <gem.h>
#include "../../c/calypsi/aes-private.h"
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESFirstFailure, AESReady, AESDone;
volatile UWORD AESInputCommand, AESInputCode, AESInputKind;
volatile ULONG AESInputClient, AESInputAck, AESInputRoute;
volatile UWORD AESPhysical, AESPhysicalGo;
static struct Task *controller;
static ULONG wake, peerWake;
static volatile UWORD peerDone;
static void check(BOOL okay, UWORD line)
{
    Forbid();
    ++AESChecks;
    if (!okay) { if (!AESFailures) AESFirstFailure = line; ++AESFailures; }
    Permit();
}
#define CHECK(t) check((t) != 0, __LINE__)

void AESClientOne(void)
{
    WORD handle;
    BYTE bit = AllocSignal(-1);
    peerWake = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    handle = wind_create(AES_WINDOW_KIND, 330, 40, 200, 120);
    CHECK(handle > 0 && wind_open(handle, 330, 40, 200, 120));
    AESReady = 1;
    Signal(controller, wake);
    Wait(peerWake);
    CHECK(ExecAESContext()->endpoint->input->keyHead ==
          ExecAESContext()->endpoint->input->keyTail);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); peerDone = 1; Signal(controller, wake); RemTask(NULL);
}
void AESClientTwo(void) {}

static void produce(UWORD command, UWORD kind, UWORD code)
{
    struct ExecAESContext *c = ExecAESContext();
    AESInputClient = c->identity;
    AESInputKind = kind;
    AESInputCode = code;
    AESInputCommand = command;
    Signal(c->directory->owner, c->directory->mask);
    while (AESInputCommand) Wait(AESInputAck);
}

static void key(UWORD raw, UWORD expected, UWORD modifiers)
{
    struct AESInputInbox *in = ExecAESContext()->endpoint->input;
    UBYTE head = in->keyHead;
    produce(2, 1, raw);
    CHECK((UBYTE)(in->keyTail-head) == 1);
    CHECK((UWORD)in->keys[head & 15].key == expected);
    CHECK(in->keys[head & 15].qualifiers == modifiers);
    CHECK(in->keys[head & 15].epoch == in->keyEpoch);
    ++in->keyHead;
}

UWORD AESRun(void)
{
    struct Task *peer;
    struct AESInputInbox *in;
    WORD handle;
    ULONG available = AvailMem(0), route;
    UWORD i;
    BYTE bit = AllocSignal(-1);
    controller = FindTask(NULL);
    wake = AESInputAck = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    handle = wind_create(AES_WINDOW_KIND, 20, 40, 200, 120);
    CHECK(handle > 0 && wind_open(handle, 20, 40, 200, 120));
    in = ExecAESContext()->endpoint->input;
    produce(1, 0, 0); /* Capture recipient before the peer takes focus. */
    route = AESInputRoute;
    CHECK(route != 0);
    peer = CreateTask("GEM key peer", 0, AESClientOne, 1024);
    CHECK(peer != NULL);
    while (!AESReady) Wait(wake);
    produce(3, 1, 63);
    CHECK(in->keyTail == 1 && in->keys[0].key == 0x1e61);
    ++in->keyHead;
    key(12, 0x1c0d, 0);
    key(28, 0x011b, 0);
    key(44, 0x0f09, 0);
    key(108, 0x0f09, 2);
    key(33, 0x3920, 0);
    key(52, 0x0e08, 0);
    key(180, 0x537f, 4);
    key(134, 0x4b00, 4);
    key(135, 0x4d00, 4);
    key(142, 0x4800, 4);
    key(143, 0x5000, 4);
    key(146, 0x2e03, 4);
    key(210, 0x2e03, 6);
    key(127, 0x1e41, 2);
    produce(2, 1, 60); /* Caps survives focus changes, no delivered key. */
    CHECK(in->keyHead == in->keyTail);
    produce(4, 0, 0);
    key(63, 0x1e41, 0);
    for (i = 0; i < 4; ++i) key(63, 0x1e41, 0); /* Captured repeats. */
    produce(2, 5, 1); /* One durable BREAK notice becomes Escape. */
    CHECK((UBYTE)(in->keyTail-in->keyHead) == 1);
    CHECK(in->keys[in->keyHead & 15].key == 0x011b);
    ++in->keyHead;
    CHECK(wind_close(handle));
    CHECK(wind_open(handle, 20, 40, 200, 120));
    produce(3, 1, 63); /* Old capture route cannot name the new open. */
    CHECK(in->keyHead == in->keyTail);
    produce(1, 0, 0);
    CHECK(AESInputRoute != route);
    key(63, 0x1e41, 0);
    produce(2, 4, 1); /* Capture loss remains source-specific. */
    CHECK(in->loss == AES_INPUT_KEY);
    CHECK(ExecAESInputRecover(ExecAESContext(), AES_INPUT_KEY) == AES_INPUT_LOST);
    CHECK(in->loss == 0 && in->buttonEpoch == 1);
    key(63, 0x1e41, 0);
    produce(4, 0, 0);
    AESPhysical = 1;
    while (!AESPhysicalGo) ExecYield(); /* Host fixture checkpoint only. */
    CHECK((UBYTE)(in->keyTail-in->keyHead) == 2);
    CHECK((UWORD)in->keys[in->keyHead & 15].key == 0x2e03);
    CHECK(in->keys[in->keyHead & 15].qualifiers == 4);
    ++in->keyHead;
    CHECK(in->keys[in->keyHead & 15].key == 0x011b);
    ++in->keyHead;
    Signal(peer, peerWake);
    while (!peerDone) Wait(wake);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    AESDone = 1;
    return AESFailures;
}
