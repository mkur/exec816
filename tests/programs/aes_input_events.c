#include <gem.h>
#include "../../c/calypsi/aes-private.h"
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESFirstFailure;
volatile UWORD AESInputCommand, AESInputSource, AESInputCount, AESInputAccepted;
volatile UWORD AESInputEligible, AESInputButtons, AESInputX, AESInputY, AESInputKey, AESInputModifiers;
volatile ULONG AESInputClient, AESInputAck;
static UWORD phase, sends, waits, cancels, reads;
static struct Task *controller;
static ULONG completedMask;
static volatile UWORD completed;
static WORD words[8], x, y, buttons, modifiers, key, clicks;

static void check(BOOL okay, UWORD line)
{
    Forbid(); ++AESChecks;
    if (!okay) { if (!AESFailures) AESFirstFailure = line; ++AESFailures; }
    Permit();
}
#define CHECK(t) check((t) != 0, __LINE__)
void AESClientOne(void);
void AESClientTwo(void) {}

static void produce(UWORD command)
{
    struct ExecAESContext *c = ExecAESContext();
    AESInputClient = c->identity;
    AESInputCommand = command;
    Signal(c->directory->owner, c->directory->mask);
    while (AESInputCommand) Wait(AESInputAck);
}

static void input(UWORD source, WORD px, WORD py, UWORD value, UWORD mods)
{
    AESInputSource = source; AESInputCount = 1;
    AESInputX = px; AESInputY = py;
    AESInputKey = 0x1e61; AESInputButtons = value; AESInputModifiers = mods;
    produce(2);
    CHECK(AESInputAccepted == 1);
}

static void snapshot(WORD px, WORD py, UWORD value, UWORD eligible)
{
    AESInputX = px; AESInputY = py;
    AESInputButtons = value; AESInputEligible = eligible; AESInputModifiers = 0;
    produce(8);
}

static void message(struct ExecAESContext *c)
{
    struct AESEndpoint *destination;
    struct AESDelivery *item = ExecAESReserve(c, c->gemId, &destination);
    CHECK(item != NULL);
    item->words[0] = 777;
    ExecAESPublish(c, destination, item);
}

void AESBeforeWait(struct ExecAESContext *c, ULONG mask)
{
    ++waits;
    if (phase == 1 || phase == 3 || phase == 5) {
        ++phase;
        input(AES_INPUT_KEY, 11, 21, 0, 2);
    } else if (phase == 7) {
        if (waits < 3) Signal(FindTask(NULL), mask);
        else { phase = 0; input(AES_INPUT_KEY, 31, 41, 0, 0); }
    } else if (phase == 8) {
        phase = 9;
        input(AES_INPUT_KEY, 32, 42, 0, 0);
        Signal(FindTask(NULL), mask); /* Input wake hint without a message. */
    } else if (phase == 9) { phase = 0; message(c); }
    else if (phase == 10) { phase = 0; produce(5); }
    else if (phase == 15) {
        phase = 16;
        AESInputSource = AES_INPUT_KEY; produce(4);
    } else if (phase == 12 || phase == 13) {
        UWORD source = phase == 12 ? AES_INPUT_KEY : AES_INPUT_BUTTON;
        phase = 0;
        Wait(1UL << c->timer.port->mp_SigBit);
        input(source, 34, 44, 1, 2);
    }
}

void AESAfterRead(struct ExecAESContext *c)
{
    ++reads;
    if (phase == 14 && reads == 2) {
        phase = 0;
        snapshot(56, 66, 1, 1);
    }
}

void AESBeforeSend(struct ExecAESContext *c)
{
    ++sends;
    if (phase == 17) {
        phase = 0;
        AESInputSource = AES_INPUT_KEY; produce(4);
        c->timer.alarm->tc_Request.io_Command = 0;
    }
    if (phase == 11) {
        phase = 0;
        input(AES_INPUT_KEY, 33, 43, 0, 2);
        c->timer.alarm->tc_Request.io_Command = 0;
    }
}

void AESBeforeCancel(struct ExecAESContext *c)
{
    ++cancels;
    if (phase == 16) { phase = 0; produce(5); }
    if (phase == 2 || phase == 4 || phase == 6) {
        UWORD saved = phase;
        phase = 0;
        input(AES_INPUT_KEY, 51, 61, 0, 4);
        input(AES_INPUT_BUTTON, 71, 81, 1, 2);
        message(c);
        if (saved == 4) { AESInputSource = AES_INPUT_KEY; produce(4); }
        if (saved == 6) produce(5);
    }
}

static WORD event(UWORD flags, UWORD count, UWORD mask, UWORD state, ULONG ms)
{
    return evnt_multi(flags, count, mask, state, 99, 0, 0, 0, 0, 99, 0, 0, 0, 0,
        words, (WORD)ms, (WORD)(ms >> 16), &x, &y, &buttons, &modifiers, &key, &clicks);
}

/* Public combined waits also run on an ordinary 1,024-byte worker stack. */
void AESClientOne(void)
{
    UWORD i;
    BYTE bit = AllocSignal(-1);
    AESInputAck = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    produce(1); snapshot(101, 111, 0, 0);
    for (i = 0; i < 8; ++i) {
        input(AES_INPUT_KEY, 21, 31, 0, 4);
        input(AES_INPUT_BUTTON, 22, 32, 1, 2);
        message(ExecAESContext());
        CHECK(event(MU_KEYBD | MU_BUTTON | MU_MESAG | MU_TIMER, 1, 1, 1, 0) ==
              (MU_KEYBD | MU_BUTTON | MU_MESAG | MU_TIMER));
        CHECK(x == 22 && key == 0x1e61 && modifiers == 6);
    }
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); completed = 1; Signal(controller, completedMask); RemTask(NULL);
}

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct AESInputInbox *in;
    UWORD i, flags, before, kh, bh;
    ULONG available = AvailMem(0), sequence;
    BYTE ack = AllocSignal(-1);
    AESInputAck = 1UL << ack;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    c = ExecAESContext(); in = c->endpoint->input;
    CHECK(!evnt_keybd() && ExecAESDiagnostic() == AES_IDENTITY);
    CHECK(!evnt_button(1, 1, 1, &x, &y, &buttons, &modifiers));
    CHECK(ExecAESDiagnostic() == AES_IDENTITY && c->timer.opened == 0);
    CHECK(event(MU_TIMER, 99, 99, 99, 0) == MU_TIMER);
    produce(1);
    snapshot(101, 111, 0, 0);
    sequence = c->sequence;
    for (i = 1; i < 16; ++i) {
        flags = (i & 3) | ((i & 12) << 2);
        input(AES_INPUT_KEY, 11, 21, 0, 4);
        input(AES_INPUT_BUTTON, 31, 41, 1, 2);
        message(c);
        kh = in->keyHead; bh = in->buttonHead; before = sends;
        CHECK(event(flags, (flags & MU_BUTTON) ? 1 : 99,
                    (flags & MU_BUTTON) ? 1 : 99, 1, 0) == flags);
        CHECK(in->keyHead == (UBYTE)(kh + ((flags & MU_KEYBD) != 0)));
        CHECK(in->buttonHead == (UBYTE)(bh + ((flags & MU_BUTTON) != 0)));
        CHECK(key == ((flags & MU_KEYBD) ? 0x1e61 : 0));
        CHECK(clicks == ((flags & MU_BUTTON) != 0));
        CHECK(x == ((flags & MU_BUTTON) ? 31 : (flags & MU_KEYBD) ? 11 : 101));
        CHECK(y == ((flags & MU_BUTTON) ? 41 : (flags & MU_KEYBD) ? 21 : 111));
        CHECK(modifiers == ((flags & MU_BUTTON) ? ((flags & MU_KEYBD) ? 6 : 2) :
                           (flags & MU_KEYBD) ? 4 : 0));
        CHECK(in->interest == 0 && sends == before && c->sequence == sequence);
        if (!(flags & MU_KEYBD)) CHECK(evnt_keybd() == 0x1e61);
        if (!(flags & MU_BUTTON)) CHECK(evnt_button(1, 1, 1, &x, &y, &buttons, &modifiers));
        if (!(flags & MU_MESAG)) CHECK(evnt_mesag(words) && words[0] == 777);
        CHECK(in->keyHead == in->keyTail && in->buttonHead == in->buttonTail);
    }

    /* Quick transitions survive a delayed client; older nonmatches retire
     * with the first selected edge, preserving later transitions. */
    input(AES_INPUT_BUTTON, 12, 22, 1, 2);
    input(AES_INPUT_BUTTON, 13, 23, 0, 4);
    input(AES_INPUT_BUTTON, 14, 24, 1, 0);
    CHECK(evnt_button(1, 1, 0, &x, &y, &buttons, &modifiers));
    CHECK(x == 13 && y == 23 && buttons == 0 && modifiers == 4);
    CHECK((UBYTE)(in->buttonTail-in->buttonHead) == 1);
    CHECK(evnt_button(0x101, 1, 0, &x, &y, &buttons, &modifiers));
    CHECK(x == 14 && buttons == 1);
    snapshot(55, 65, 1, 1);
    before = in->buttonHead;
    for (i = 0; i < 3; ++i) CHECK(evnt_button(1, 1, 1, &x, &y, &buttons, &modifiers));
    CHECK(x == 55 && y == 65 && in->buttonHead == before);
    snapshot(101, 111, 0, 0);

    input(AES_INPUT_KEY, 15, 25, 0, 2); message(c);
    before = in->keyHead;
    CHECK(!event(MU_KEYBD | MU_BUTTON | MU_MESAG, 2, 1, 1, 0));
    CHECK(ExecAESDiagnostic() == AES_UNSUPPORTED && in->keyHead == before);
    CHECK(!event(MU_BUTTON, 1, 0, 1, 0) && ExecAESDiagnostic() == AES_UNSUPPORTED);
    CHECK(!event(MU_BUTTON, 1, 2, 1, 0) && ExecAESDiagnostic() == AES_UNSUPPORTED);
    CHECK(!event(MU_BUTTON, 1, 1, 2, 0) && ExecAESDiagnostic() == AES_UNSUPPORTED);
    CHECK(!event(MU_KEYBD | MU_M1, 1, 1, 1, 0));
    CHECK(ExecAESDiagnostic() == AES_UNSUPPORTED && in->keyHead == before);
    CHECK(evnt_keybd() == 0x1e61 && evnt_mesag(words) && words[0] == 777);

    /* Equivalent parameter-block entry points and counts. */
    {
        WORD control[5] = {20, 0, 1, 0, 0}, global[15], args[16], out[7];
        LONG addresses[1] = {(LONG)words};
        AESPB pb = {control, global, args, out, addresses, NULL};
        input(AES_INPUT_KEY, 16, 26, 0, 0);
        aes_call(&pb); CHECK(out[0] == 0x1e61);
        input(AES_INPUT_BUTTON, 17, 27, 1, 2);
        control[0] = 21; control[1] = 3; control[2] = 4;
        args[0] = args[1] = args[2] = 1;
        before = in->buttonHead;
        aes_call(&pb); CHECK(out[0] == 0 && ExecAESDiagnostic() == AES_MALFORMED);
        CHECK(in->buttonHead == before);
        control[2] = 5;
        aes_call(&pb); CHECK(out[0] == 1 && out[1] == 17 && out[2] == 27 && out[3] == 1 && out[4] == 2);
        input(AES_INPUT_KEY, 18, 28, 0, 4);
        control[0] = 25; control[1] = 16; control[2] = 7; control[3] = 1;
        for (i = 0; i < 16; ++i) args[i] = 0;
        args[0] = MU_KEYBD | MU_TIMER;
        aes_call(&pb); CHECK(out[0] == (MU_KEYBD | MU_TIMER) && out[1] == 18 && out[5] == 0x1e61);
        input(AES_INPUT_KEY, 19, 29, 0, 0);
        CHECK(evnt_multi_moblk(MU_KEYBD | MU_TIMER, 0, 0, 0, NULL, NULL, NULL,
            0, 0, &x, &y, &buttons, &modifiers, &key, &clicks) == (MU_KEYBD | MU_TIMER));
        CHECK(x == 19 && key == 0x1e61);
    }

    produce(9);
    for (i = 0; i < 8; ++i) {
        input(AES_INPUT_KEY, 20, 30, 0, 0);
        input(AES_INPUT_BUTTON, 20, 30, 1, 0);
        CHECK(event(MU_KEYBD | MU_BUTTON, 1, 1, 1, 0) == (MU_KEYBD | MU_BUTTON));
    }
    CHECK(in->keyHead == 2 && in->buttonHead == 2);
    AESInputSource = AES_INPUT_KEY; produce(4);
    CHECK(event(MU_TIMER, 0, 0, 0, 0) == MU_TIMER && in->loss == AES_INPUT_KEY);
    snapshot(54, 64, 1, 1);
    CHECK(evnt_button(1, 1, 1, &x, &y, &buttons, &modifiers));
    CHECK(in->loss == AES_INPUT_KEY);
    CHECK(!evnt_keybd() && ExecAESDiagnostic() == AES_INPUT_LOST);
    CHECK(in->loss == 0);
    snapshot(101, 111, 0, 0);
    input(AES_INPUT_KEY, 35, 45, 0, 2); message(c);
    AESInputSource = AES_INPUT_BUTTON; produce(4);
    CHECK(!event(MU_KEYBD | MU_BUTTON | MU_MESAG | MU_TIMER, 1, 1, 1, 0));
    CHECK(ExecAESDiagnostic() == AES_INPUT_LOST && in->loss == 0);
    CHECK(in->keyHead != in->keyTail && in->interest == 0);
    CHECK(evnt_keybd() == 0x1e61);
    CHECK(evnt_mesag(words) && words[0] == 777);
    phase = 12;
    CHECK(event(MU_KEYBD | MU_TIMER, 1, 1, 1, 30) == (MU_KEYBD | MU_TIMER));
    CHECK(x == 34 && key == 0x1e61 && c->timer.state == AES_ALARM_IDLE);
    phase = 13;
    CHECK(event(MU_BUTTON | MU_TIMER, 1, 1, 1, 30) == (MU_BUTTON | MU_TIMER));
    CHECK(x == 34 && buttons == 1 && c->timer.state == AES_ALARM_IDLE);
    message(c); phase = 14; reads = 0;
    CHECK(event(MU_BUTTON | MU_MESAG | MU_TIMER, 1, 1, 1, 1000) == (MU_BUTTON | MU_MESAG));
    CHECK(x == 56 && y == 66 && buttons == 1 && words[0] == 777);
    snapshot(101, 111, 0, 0);

    phase = 1; before = cancels;
    CHECK(event(MU_KEYBD | MU_BUTTON | MU_MESAG | MU_TIMER, 1, 1, 1, 1000) == MU_KEYBD);
    CHECK(x == 11 && y == 21 && key == 0x1e61 && clicks == 0 && modifiers == 2);
    CHECK(cancels == before+1 && c->timer.state == AES_ALARM_IDLE);
    CHECK(event(MU_KEYBD | MU_BUTTON | MU_MESAG | MU_TIMER, 1, 1, 1, 0) ==
          (MU_KEYBD | MU_BUTTON | MU_MESAG | MU_TIMER));
    CHECK(x == 71 && y == 81 && modifiers == 6 && words[0] == 777);
    CHECK(in->keyHead == in->keyTail && in->buttonHead == in->buttonTail);
    phase = 3;
    CHECK(!event(MU_KEYBD | MU_BUTTON | MU_MESAG | MU_TIMER, 1, 1, 1, 1000));
    CHECK(ExecAESDiagnostic() == AES_INPUT_LOST && in->loss == 0);
    CHECK(c->timer.state == AES_ALARM_IDLE && in->interest == 0);
    CHECK(in->keyHead == in->keyTail && in->buttonHead != in->buttonTail);
    CHECK(evnt_mesag(words) && words[0] == 777);
    CHECK(evnt_button(1, 1, 1, &x, &y, &buttons, &modifiers));
    CHECK(x == 71);

    message(c); phase = 7; waits = 0;
    CHECK(evnt_keybd() == 0x1e61 && waits == 3);
    CHECK(evnt_mesag(words) && words[0] == 777);
    phase = 8; waits = 0;
    CHECK(evnt_mesag(words) && words[0] == 777 && waits >= 2);
    CHECK(evnt_keybd() == 0x1e61);
    phase = 5;
    CHECK(!event(MU_KEYBD | MU_TIMER, 1, 1, 1, 1000));
    CHECK(ExecAESDiagnostic() == AES_IDENTITY && c->timer.state == AES_ALARM_IDLE);
    CHECK(evnt_mesag(words) && words[0] == 777);
    produce(1); snapshot(101, 111, 0, 0);
    phase = 10;
    CHECK(!event(MU_KEYBD | MU_TIMER, 1, 1, 1, 1000));
    CHECK(ExecAESDiagnostic() == AES_IDENTITY && in->interest == 0);
    produce(1); snapshot(101, 111, 0, 0);
    phase = 15;
    CHECK(!event(MU_KEYBD | MU_TIMER, 1, 1, 1, 1000));
    CHECK(ExecAESDiagnostic() == AES_IDENTITY && c->timer.state == AES_ALARM_IDLE);
    produce(1); snapshot(101, 111, 0, 0);
    phase = 11;
    CHECK(!event(MU_KEYBD | MU_TIMER, 1, 1, 1, 1000));
    CHECK(ExecAESDiagnostic() == AES_TIMER_ERROR && in->keyHead != in->keyTail);
    CHECK(evnt_keybd() == 0x1e61);
    CHECK(c->sequence == sequence);
    CHECK(appl_exit() && appl_init() > 0);
    in = c->endpoint->input;
    produce(1); snapshot(101, 111, 0, 0);
    phase = 17;
    CHECK(!event(MU_KEYBD | MU_TIMER, 1, 1, 1, 1000));
    CHECK(ExecAESDiagnostic() == AES_TIMER_ERROR && in->loss == AES_INPUT_KEY);
    CHECK(!evnt_keybd() && ExecAESDiagnostic() == AES_INPUT_LOST && in->loss == 0);
    CHECK(ExecAESDetach());
    controller = FindTask(NULL);
    completedMask = 1UL << ack;
    CHECK(CreateTask("Input wait stack", 0, AESClientOne, 1024) != NULL);
    while (!completed) Wait(completedMask);
    FreeSignal(ack);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
