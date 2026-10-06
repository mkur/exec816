#include <gem.h>
#include "../../c/calypsi/aes-private.h"
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

BOOL Peer_ExecAESAttach(struct MsgPort *service);
BOOL Peer_ExecAESDetach(void);
struct ExecAESContext *Peer_ExecAESContext(void);
WORD Peer_appl_init(void);

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESReady, AESDone;
static struct Task *controller, *workers[5];
static ULONG wake, commands[5];
static WORD ids[5];
static void check(BOOL okay)
{
    Forbid(); ++AESChecks; if (!okay) ++AESFailures; Permit();
}
#define CHECK(t) check((t) != 0)

static void raw(struct ExecAESContext *c, UWORD status)
{
    struct Message *m;
    c->request.status = AES_PENDING;
    PutMsg(c->service, &c->request.message);
    while ((m = GetMsg(c->replies)) == NULL) WaitPort(c->replies);
    CHECK(m == &c->request.message);
    CHECK(c->request.status == status);
}

static void worker(UWORD who)
{
    BYTE bit = AllocSignal(-1);
    CHECK(bit >= 0);
    commands[who] = 1UL << bit;
    CHECK(who == 1 ? Peer_ExecAESAttach((struct MsgPort *)AESService) :
                     ExecAESAttach((struct MsgPort *)AESService));
    ids[who] = who == 1 ? Peer_appl_init() : appl_init();
    if (who < 4) {
        CHECK(ids[who] > 0);
        struct ExecAESContext *context = who == 1 ? Peer_ExecAESContext() : ExecAESContext();
        CHECK((who == 1 ? Peer_appl_init() : appl_init()) == ids[who]);
        CHECK(context->request.global[2] == ids[who]);
        CHECK(context->endpoint->id == context->identity);
        CHECK(context->endpoint->port == context->receiving);
        if (who == 1) CHECK(ExecAESContext() == NULL);
    } else {
        CHECK(ids[who] == -1);
        CHECK(ExecAESDiagnostic() == AES_RESOURCE);
    }
    Forbid(); ++AESReady; Signal(controller, wake); Permit();
    Wait(commands[who]);
    if (who == 4) {
        UWORD i;
        ids[who] = appl_init();
        CHECK(ids[who] > 0);
        for (i = 0; i < 4; ++i) CHECK(ids[who] > ids[i]);
    }
    /* Runtime wrapper retires a still-registered app before Task removal. */
    CHECK(who == 1 ? Peer_ExecAESDetach() : ExecAESDetach());
    CHECK((who == 1 ? Peer_ExecAESContext() : ExecAESContext()) == NULL);
    FreeSignal(bit);
    Forbid(); ++AESDone; Signal(controller, wake); RemTask(NULL);
}

void AESClientOne(void) { worker(0); }
void AESClientTwo(void) { worker(1); }
void AESClientThree(void) { worker(2); }
void AESClientFour(void) { worker(3); }
void AESClientFive(void) { worker(4); }
static void (*const entries[5])(void) = {
    AESClientOne, AESClientTwo, AESClientThree, AESClientFour, AESClientFive
};

UWORD AESRun(void)
{
    UWORD i, j, round;
    WORD first;
    struct ExecAESContext *c;
    ULONG available = AvailMem(0);
    BYTE bit = AllocSignal(-1);
    CHECK(bit >= 0);
    controller = FindTask(NULL);
    wake = 1UL << bit;
    CHECK(appl_init() == -1);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    first = appl_init();
    CHECK(first > 0);
    CHECK(appl_init() == first);
    c = ExecAESContext();
    CHECK(c->request.global[0] == 0 && c->request.global[1] == 4);
    CHECK(c->request.global[2] == first && c->request.global[10] == 4);
    /* Rejected packets cannot consume sequence or change registration. */
    c->request.operation = AES_OP_EXIT;
    c->request.sequence = 1;
    raw(c, AES_IDENTITY);
    c->request.sequence = 2;
    c->request.client = 0xdeadbeefUL;
    raw(c, AES_IDENTITY);
    c->request.client = c->identity;
    c->request.owner = NULL;
    raw(c, AES_IDENTITY);
    c->request.owner = controller;
    c->request.binding = NULL;
    raw(c, AES_IDENTITY);
    c->request.binding = (UBYTE *)c;
    c->request.operation = 999;
    raw(c, AES_UNSUPPORTED);
    c->sequence = 2;
    CHECK(appl_exit() == 1);
    CHECK(appl_exit() == 0 && ExecAESDiagnostic() == AES_IDENTITY);
    {
        BYTE signals[32], signal;
        UWORD count = 0;
        ULONG before = AvailMem(0);
        while ((signal = AllocSignal(-1)) >= 0) signals[count++] = signal;
        CHECK(appl_init() == -1 && ExecAESDiagnostic() == AES_RESOURCE);
        CHECK(AvailMem(0) == before);
        CHECK(c->records == NULL && c->receiving == NULL && c->identity == 0);
        while (count) FreeSignal(signals[--count]);
    }
    CHECK(appl_init() > first);
    {
        WORD control[5] = {10, 0, 1, 0, 0}, global[15], result;
        AESPB pb = {control, global, NULL, &result, NULL, NULL};
        aes_call(&pb);
        CHECK(result == c->gemId && global[2] == c->gemId);
        control[0] = 999;
        aes_call(&pb);
        CHECK(result == 0 && ExecAESDiagnostic() == AES_UNSUPPORTED);
    }
    /* Hold a destination across its exit. The presenter must keep serving
     * RPC while exit is pending, and the caller must not free the pool. */
    AESReady = AESDone = 0;
    workers[1] = CreateTask("AES retiring", 0, (APTR)AESClientTwo, 1024UL);
    CHECK(workers[1] != NULL);
    while (AESReady < 1) Wait(wake);
    {
        struct AESEndpoint *destination = NULL;
        struct AESDelivery *record = ExecAESReserve(c, ids[1], &destination);
        UWORD attempts;
        CHECK(record != NULL && destination != NULL);
        CHECK(destination->holds == 1);
        Signal(workers[1], commands[1]);
        for (attempts = 0; attempts < 128 &&
             destination->state != AES_ENDPOINT_CLOSING; ++attempts) ExecYield();
        CHECK(destination->state == AES_ENDPOINT_CLOSING);
        CHECK(AESDone == 0 && destination->records != NULL);
        CHECK(wind_update(BEG_UPDATE | AES_TRY) == 1);
        CHECK(wind_update(END_UPDATE) == 1);
        CHECK(ExecAESReserve(c, ids[1], &destination) == NULL);
        CHECK(ExecAESDiagnostic() == AES_IDENTITY);
        for (i = 0; i < AES_MESSAGE_WORDS; ++i) record->words[i] = 400+i;
        ExecAESPublish(c, destination, record);
        while (AESDone < 1) Wait(wake);
        CHECK(destination->state == AES_ENDPOINT_RETIRED);
        CHECK(destination->port == NULL && destination->records == NULL);
    }
    CHECK(ExecAESDetach());
    for (round = 0; round < 3; ++round) {
        AESReady = AESDone = 0;
        for (i = 0; i < 4; ++i) {
            workers[i] = CreateTask("AES client", 0, (APTR)entries[i], 1024UL);
            CHECK(workers[i] != NULL);
        }
        while (AESReady < 4) Wait(wake);
        for (i = 0; i < 4; ++i)
            for (j = i+1; j < 4; ++j) CHECK(ids[i] != ids[j]);
        workers[4] = CreateTask("AES fifth", 0, (APTR)entries[4], 1024UL);
        CHECK(workers[4] != NULL);
        while (AESReady < 5) Wait(wake);
        for (i = 0; i < 4; ++i) Signal(workers[i], commands[i]);
        while (AESDone < 4) Wait(wake);
        Signal(workers[4], commands[4]);
        while (AESDone < 5) Wait(wake);
    }
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}

UWORD AESExhausted(void)
{
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() == -1);
    CHECK(ExecAESDiagnostic() == AES_OVERFLOW);
    CHECK(ExecAESDetach());
    return AESFailures;
}
