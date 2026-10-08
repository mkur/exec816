#include <gem.h>
#include "../../c/calypsi/aes-private.h"
#include <exec816/runtime.h>

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESReady, AESDone, AESFirstFailure;
volatile UWORD AESInputCommand, AESInputSource, AESInputCount, AESInputAccepted;
volatile UWORD AESInputEligible, AESInputButtons;
volatile ULONG AESInputClient, AESInputAck;

#define CHECK(t) do { ++AESChecks; if (!(t)) { if (!AESFailures) AESFirstFailure=AESChecks; ++AESFailures; } } while (0)

static void produce(UWORD command)
{
    struct ExecAESContext *c = ExecAESContext();
    AESInputClient = c->identity;
    AESInputCommand = command;
    Signal(c->directory->owner, c->directory->mask);
    while (AESInputCommand) Wait(AESInputAck);
}

void AESClientOne(void) {}
void AESClientTwo(void) {}

/* Leave enough space for a receive port, but not the registration storage.
 * Every allocation is retained in its own block and restored after failure. */
static void allocation_failure(struct ExecAESContext *c)
{
    struct Block { struct Block *next; ULONG bytes; } *head = NULL, *block;
    static const ULONG sizes[3] = {32768, 1024, 128};
    ULONG available = AvailMem(0), before;
    UWORD i;
    void *spare = AllocMem(128, MEMF_PUBLIC);
    CHECK(spare != NULL);
    for (i = 0; i < 3; ++i)
        while ((block = AllocMem(sizes[i], MEMF_PUBLIC)) != NULL) {
            block->bytes = sizes[i];
            block->next = head;
            head = block;
        }
    FreeMem(spare, 128);
    before = AvailMem(0);
    CHECK(appl_init() == -1 && ExecAESDiagnostic() == AES_RESOURCE);
    CHECK(c->records == NULL && c->receiving == NULL && c->identity == 0);
    CHECK(AvailMem(0) == before);
    while (head != NULL) {
        ULONG bytes = head->bytes;
        block = head;
        head = head->next;
        FreeMem(block, bytes);
    }
    CHECK(AvailMem(0) == available);
}

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct AESInputInbox *input;
    UWORD i;
    WORD words[8] = {777};
    ULONG available = AvailMem(0), mask, epoch;
    BYTE ack = AllocSignal(-1);
    CHECK(ack >= 0);
    AESInputAck = 1UL << ack;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    c = ExecAESContext();
    input = c->endpoint->input;
    mask = 1UL << c->receiving->mp_SigBit;
    CHECK(sizeof(*input) <= 640);
    CHECK(input->windowEpoch == 0);
    CHECK(ExecAESInputArm(c, AES_INPUT_KEY) == AES_IDENTITY);
    produce(1);
    epoch = input->windowEpoch;
    CHECK(epoch != 0 && epoch == c->endpoint->guiEpoch);
    CHECK(input->loss == 0 && input->interest == 0);

    SetSignal(0, mask);
    AESInputCount = 16;
    AESInputSource = AES_INPUT_KEY;
    produce(2);
    CHECK(AESInputAccepted == 16 && input->keyTail == 16);
    CHECK((SetSignal(0, mask) & mask) == 0);
    for (i = 0; i < 16; ++i) {
        CHECK(input->keys[i].epoch == input->keyEpoch);
        CHECK(input->keys[i].key == 0x100+i);
        CHECK(input->keys[i].x == (WORD)i && input->keys[i].y == -(WORD)i);
    }
    AESInputSource = AES_INPUT_BUTTON;
    AESInputButtons = 1;
    produce(2);
    CHECK(AESInputAccepted == 16 && input->buttonTail == 16);
    CHECK((SetSignal(0, mask) & mask) == 0);
    for (i = 0; i < 16; ++i) {
        CHECK(input->buttons[i].epoch == input->buttonEpoch);
        CHECK(input->buttons[i].buttons == 1 && input->buttons[i].qualifiers == 2);
    }

    /* Full input queues do not borrow ordinary-message capacity. */
    for (i = 0; i < 16; ++i) CHECK(appl_write(c->gemId, 16, words));
    CHECK(!appl_write(c->gemId, 16, words));
    CHECK(ExecAESDiagnostic() == AES_RESOURCE);
    SetSignal(0, mask);
    CHECK(ExecAESInputArm(c, AES_INPUT_KEY) == AES_OK);
    input->selectedKey = input->keys[0];
    AESInputCount = 1;
    AESInputSource = AES_INPUT_KEY;
    produce(2);
    CHECK(AESInputAccepted == 0 && input->loss == AES_INPUT_KEY);
    CHECK(input->keyEpoch == 2 && input->keyHead == 0 && input->keyTail == 16);
    CHECK((SetSignal(0, mask) & mask) != 0);
    CHECK(input->keys[0].epoch == input->selectedKey.epoch);
    CHECK(input->keys[0].key == input->selectedKey.key);
    produce(2);
    CHECK(AESInputAccepted == 0 && input->keyEpoch == 2);
    CHECK((SetSignal(0, mask) & mask) == 0);
    CHECK(ExecAESInputRecover(c, AES_INPUT_BUTTON) == AES_OK);
    CHECK(input->loss == AES_INPUT_KEY && input->buttonHead == 0);
    CHECK(evnt_timer(0, 0) == 1 && input->loss == AES_INPUT_KEY);
    CHECK(ExecAESInputRecover(c, AES_INPUT_KEY) == AES_INPUT_LOST);
    CHECK(input->keyHead == input->keyTail && input->loss == 0);
    CHECK(c->endpoint->freeRecords == 0 && input->buttonHead == 0);
    for (i = 0; i < 16; ++i) {
        CHECK(evnt_mesag(words));
        CHECK(words[0] == 777);
    }
    produce(2);
    CHECK(AESInputAccepted == 1 && input->keys[0].epoch == 2);
    CHECK((SetSignal(0, mask) & mask) != 0);
    CHECK(GetMsg(c->receiving) == NULL); /* Wake is not a message. */
    ExecAESInputDisarm(c);
    CHECK(input->interest == 0);

    CHECK(ExecAESInputArm(c, AES_INPUT_BUTTON) == AES_OK);
    AESInputEligible = 0;
    produce(3);
    CHECK((SetSignal(0, mask) & mask) == 0);
    AESInputEligible = 1;
    produce(3);
    CHECK((SetSignal(0, mask) & mask) != 0);
    CHECK(input->eligible == 1 && input->latest.epoch == epoch);
    produce(3);
    CHECK((SetSignal(0, mask) & mask) == 0);
    AESInputSource = AES_INPUT_BUTTON;
    produce(4);
    CHECK(input->loss == AES_INPUT_BUTTON && input->eligible == 0);
    CHECK((SetSignal(0, mask) & mask) != 0);
    CHECK(input->keyHead != input->keyTail);
    CHECK(ExecAESInputRecover(c, AES_INPUT_BUTTON) == AES_INPUT_LOST);
    CHECK(input->buttonHead == input->buttonTail);

    /* Publish before the wait: its latched bit must satisfy Wait immediately. */
    produce(2);
    CHECK(Wait(mask) & mask);
    CHECK(c->endpoint->holds == 0);
    produce(5);
    CHECK(input->windowEpoch == 0 && input->interest == 0);
    CHECK(ExecAESInputRecover(c, AES_INPUT_BUTTON) == AES_IDENTITY);
    CHECK((SetSignal(0, mask) & mask) != 0);
    produce(1);
    CHECK(input->windowEpoch != 0 && input->windowEpoch != epoch);
    CHECK(input->keyHead == input->keyTail && input->buttonHead == input->buttonTail);
    produce(6);
    AESInputSource = AES_INPUT_KEY;
    for (i = 0; i < 20; ++i) {
        produce(2);
        CHECK(AESInputAccepted == 1);
        CHECK((UBYTE)(input->keyTail-input->keyHead) == 1);
        CHECK(input->keys[input->keyHead & 15].key == 0x100);
        ++input->keyHead; /* This private fixture is the sole consumer. */
    }
    CHECK(input->keyHead == 14 && input->keyTail == 14);
    produce(7);
    produce(4);
    CHECK(input->keyEpoch == 0xffffffffUL && input->exhausted == AES_INPUT_KEY);
    CHECK(ExecAESInputRecover(c, AES_INPUT_KEY) == AES_OVERFLOW);
    produce(2);
    CHECK(AESInputAccepted == 0);
    produce(5);
    produce(1);
    CHECK(input->exhausted == 0 && input->keyEpoch == 1);
    CHECK(appl_exit());
    allocation_failure(c);
    CHECK(appl_init() > 0);
    CHECK(c->endpoint->input->windowEpoch == 0);
    CHECK(ExecAESDetach());
    FreeSignal(ack);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
