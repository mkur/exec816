#include <gem.h>
#include "../../c/calypsi/aes-private.h"
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESFirstFailure, AESReady, AESDone;
volatile UWORD AESPointerCommand, AESPointerButtons, AESPointerQualifiers, AESPointerKind;
volatile WORD AESPointerX, AESPointerY;
volatile ULONG AESPointerClient, AESPointerAck;
static struct Task *controller, *peer;
static ULONG wake, peerWake;
static volatile UWORD peerCommand, peerFinished, peerEntered;
static struct AESInputInbox *peerInput;
static WORD peerWindow;

static void check(BOOL okay, UWORD line)
{
    Forbid(); ++AESChecks;
    if (!okay) { if (!AESFailures) AESFirstFailure = line; ++AESFailures; }
    Permit();
}
#define CHECK(t) check((t) != 0, __LINE__)

void AESClientOne(void)
{
    BYTE bit = AllocSignal(-1);
    peerWake = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    peerInput = ExecAESContext()->endpoint->input;
    peerWindow = wind_create(AES_WINDOW_KIND, 330, 40, 200, 120);
    CHECK(peerWindow > 0 && wind_open(peerWindow, 330, 40, 200, 120));
    AESReady = 1; Signal(controller, wake);
    for (;;) {
        Wait(peerWake);
        if (peerCommand == 1) CHECK(wind_set(peerWindow, WF_TOP, 0, 0, 0, 0));
        else if (peerCommand == 2) {
            CHECK(wind_update(BEG_CHECK | BEG_MCTRL) == 0);
            CHECK(ExecAESDiagnostic() == AES_OK);
        } else if (peerCommand == 3) {
            peerEntered = 1; Signal(controller, wake);
            CHECK(wind_update(BEG_MCTRL));
        } else if (peerCommand == 4) CHECK(wind_update(END_MCTRL));
        else if (peerCommand == 5) {
            CHECK(wind_close(peerWindow) && wind_delete(peerWindow));
            CHECK(wind_update(BEG_MCTRL));
        } else break;
        peerFinished = peerCommand; Signal(controller, wake);
    }
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); AESDone = 1; Signal(controller, wake); RemTask(NULL);
}
void AESClientTwo(void) {}

static void send(UWORD command)
{
    peerFinished = 0;
    peerCommand = command;
    Signal(peer, peerWake);
    while (peerFinished != command) Wait(wake);
}

static void sample(UWORD command, UWORD kind, WORD x, WORD y, UWORD buttons, UWORD qualifiers)
{
    struct ExecAESContext *c = ExecAESContext();
    AESPointerClient = c->identity;
    AESPointerKind = kind; AESPointerX = x; AESPointerY = y;
    AESPointerButtons = buttons; AESPointerQualifiers = qualifiers;
    AESPointerCommand = command;
    Signal(c->directory->owner, c->directory->mask);
    while (AESPointerCommand) Wait(AESPointerAck);
}

static void edge(WORD x, WORD y, UWORD down)
{ sample(1, 3, x, y, down, 1); }

static void take(struct AESInputInbox *in, WORD x, WORD y, UWORD buttons)
{
    UBYTE head = in->buttonHead;
    CHECK(head != in->buttonTail);
    CHECK(in->buttons[head & 15].x == x && in->buttons[head & 15].y == y);
    CHECK(in->buttons[head & 15].buttons == buttons);
    CHECK(in->buttons[head & 15].qualifiers == 2);
    CHECK(in->buttons[head & 15].epoch == in->buttonEpoch);
    ++in->buttonHead;
}

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct AESInputInbox *in;
    WORD handle;
    ULONG available = AvailMem(0), inputMask;
    UWORD i;
    BYTE bit = AllocSignal(-1);
    controller = FindTask(NULL);
    wake = AESPointerAck = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    c = ExecAESContext(); in = c->endpoint->input;
    inputMask = 1UL << c->receiving->mp_SigBit;
    handle = wind_create(AES_WINDOW_KIND, 20, 40, 200, 120);
    CHECK(handle > 0 && wind_open(handle, 20, 40, 200, 120));
    peer = CreateTask("GEM pointer peer", 0, AESClientOne, 1024);
    CHECK(peer != NULL);
    while (!AESReady) Wait(wake);
    CHECK(wind_set(handle, WF_TOP, 0, 0, 0, 0));
    edge(60, 80, 0); /* Fresh released baseline. */
    CHECK(in->eligible && !peerInput->eligible);
    CHECK(ExecAESInputArm(c, AES_INPUT_BUTTON) == AES_OK);

    edge(60, 80, 1);
    take(in, 60, 80, 1);
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_update(BEG_MCTRL));
    CHECK(wind_update(BEG_CHECK | BEG_MCTRL));
    edge(620, 230, 0); /* Owner receives release outside all windows. */
    take(in, 620, 230, 0);
    CHECK(in->latest.x == 620 && in->eligible);
    CHECK(wind_update(END_MCTRL) && wind_update(END_MCTRL));
    CHECK(wind_update(END_UPDATE));

    /* BEG_UPDATE blocks native gestures, not the focused app's content. */
    CHECK(wind_update(BEG_UPDATE));
    sample(2, 3, 70, 90, 1, 1);
    take(in, 70, 90, 1); take(in, 70, 90, 0);
    CHECK(wind_update(END_UPDATE));
    CHECK(in->buttonHead == in->buttonTail && in->loss == 0);

    edge(60, 80, 1);
    send(1); /* Programmatic focus change does not steal the gesture. */
    CHECK(in->eligible && !peerInput->eligible);
    edge(600, 200, 0);
    take(in, 60, 80, 1); take(in, 600, 200, 0);
    CHECK(!in->eligible && peerInput->eligible);
    CHECK(peerInput->buttonHead == peerInput->buttonTail);

    edge(60, 80, 1); /* Inactive activation click remains manager-owned. */
    CHECK(wind_set(handle, WF_TOP, 0, 0, 0, 0));
    CHECK(!in->eligible);
    edge(60, 80, 0);
    CHECK(in->buttonHead == in->buttonTail);
    CHECK(in->eligible);

    edge(60, 80, 1);
    send(2); /* Competitor cannot steal a physical gesture. */
    peerFinished = peerEntered = 0; peerCommand = 3; Signal(peer, peerWake);
    while (!peerEntered) Wait(wake);
    CHECK(evnt_timer(0, 0));
    CHECK(peerFinished == 0);
    edge(60, 80, 0);
    while (peerFinished != 3) Wait(wake);
    take(in, 60, 80, 1); take(in, 60, 80, 0);
    CHECK(!in->eligible && peerInput->eligible);
    send(4);
    CHECK(in->eligible); /* Ownership handback needs no new physical edge. */

    CHECK(wind_update(BEG_MCTRL));
    edge(620, 230, 1); edge(610, 220, 0);
    take(in, 620, 230, 1); take(in, 610, 220, 0);
    CHECK(wind_update(END_MCTRL));

    /* Released deferred title sequence cannot prevent an owner upgrade. */
    CHECK(wind_update(BEG_UPDATE));
    edge(80, 46, 1);
    sample(3, 5, 0, 0, 0, 0); /* BREAK belongs to the deferred title gesture. */
    edge(80, 46, 0);
    CHECK(in->keyHead == in->keyTail);
    CHECK(wind_update(BEG_MCTRL));
    CHECK(in->buttonHead == in->buttonTail && !in->eligible);
    CHECK(wind_update(END_MCTRL) && wind_update(END_UPDATE));
    CHECK(evnt_timer(60, 0));
    CHECK(in->buttonHead == in->buttonTail && in->eligible);

    edge(60, 80, 1);
    CHECK(wind_close(handle));
    CHECK(wind_open(handle, 20, 40, 200, 120));
    sample(1, 2, 65, 85, 1, 0);
    CHECK(in->buttonHead == in->buttonTail && !in->eligible);
    edge(65, 85, 0);
    CHECK(in->buttonHead == in->buttonTail && in->eligible);
    edge(60, 80, 1);
    sample(1, 4, 60, 80, 1, 0);
    CHECK(in->loss == AES_INPUT_BUTTON && !in->eligible);
    CHECK(ExecAESInputRecover(c, AES_INPUT_BUTTON) == AES_INPUT_LOST);
    sample(1, 2, 65, 85, 1, 0);
    CHECK(in->buttonHead == in->buttonTail);
    edge(65, 85, 0);
    sample(2, 3, 70, 90, 1, 1);
    take(in, 70, 90, 1); take(in, 70, 90, 0);
    CHECK(in->loss == 0 && in->keyEpoch == 1);

    CHECK(wind_update(BEG_UPDATE));
    for (i = 0; i < 10; ++i) sample(2, 3, 630, 235, 1, 1);
    CHECK(wind_update(END_UPDATE));
    CHECK(evnt_timer(60, 0));
    CHECK(in->loss == AES_INPUT_BUTTON); /* Deferred native queue loss. */
    CHECK(ExecAESInputRecover(c, AES_INPUT_BUTTON) == AES_INPUT_LOST);
    edge(70, 90, 0);
    CHECK(in->eligible && in->keyHead == in->keyTail);

    send(5); /* Windowless MCTRL owns exclusion, never fabricates content. */
    sample(2, 3, 70, 90, 1, 1);
    CHECK(in->buttonHead == in->buttonTail && !in->eligible);
    CHECK(peerInput->windowEpoch == 0 && peerInput->buttonHead == peerInput->buttonTail);
    send(4);
    CHECK(in->eligible);
    for (i = 0; i < 8; ++i) sample(2, 3, 70, 90, 1, 1);
    CHECK((UBYTE)(in->buttonTail-in->buttonHead) == 16);
    edge(70, 90, 1);
    CHECK(in->loss == AES_INPUT_BUTTON);
    CHECK(ExecAESInputRecover(c, AES_INPUT_BUTTON) == AES_INPUT_LOST);
    edge(70, 90, 0);
    CHECK(in->eligible && in->buttonHead == in->buttonTail);
    ExecAESInputDisarm(c);
    peerCommand = 9; Signal(peer, peerWake);
    while (!AESDone) Wait(wake);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
