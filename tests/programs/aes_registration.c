#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

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
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    ids[who] = appl_init();
    if (who < 4) {
        CHECK(ids[who] > 0);
        CHECK(appl_init() == ids[who]);
        CHECK(ExecAESContext()->request.global[2] == ids[who]);
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
    CHECK(ExecAESDetach());
    CHECK(ExecAESContext() == NULL);
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
