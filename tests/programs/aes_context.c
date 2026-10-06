/* Two admitted C Task entries composed with the real desktop drawing image. */
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include "aes_timer_vectors.h"

ULONG AESProbePacket;
volatile UWORD AESChecks[2], AESFailures[2], AESFinished[2];
static struct MsgPort *service;
static struct Task *controller;
static ULONG wake;
static struct ExecAESContext *published[2];

#define CHECK(test) do { if (!(test)) ++AESFailures[who]; ++AESChecks[who]; } while (0)

static void client(UWORD who)
{
    UWORD i, j;
    struct ExecAESContext *context;
    CHECK(ExecAESContext() == NULL);
    CHECK(!ExecAESAttach((struct MsgPort *)0x01000000UL));
    CHECK(ExecAESAttach(service));
    context = ExecAESContext();
    CHECK(context != NULL);
    if (context != NULL) {
        published[who] = context;
        CHECK(ExecAESAttach(service));
        CHECK(context == ExecAESContext());
        CHECK(context->request.owner == FindTask(NULL));
        CHECK(context->request.binding == (UBYTE *)context);
        CHECK(context->request.message.mn_ReplyPort == context->replies);
        CHECK(context->request.bytes == AES_REQUEST_SIZE);
        CHECK(ExecAESTimerRead(context));
        CHECK(context->timer.query->ticks_per_second == 50 || context->timer.query->ticks_per_second == 60);
        ExecAESTimerSend(context, 0, 0);
        CHECK(ExecAESTimerCollect(context, FALSE));
        CHECK(context->timer.error == 0 && context->timer.state == AES_ALARM_IDLE);
        for (i = 0; i < 32; ++i) {
            for (j = 0; j < AES_INTIN_WORDS; ++j)
                context->request.intin[j] = (WORD)(0x8100+who*256+i+j);
            for (j = 0; j < AES_GLOBAL_WORDS; ++j)
                context->request.global[j] = (WORD)(0x4200+who*256+i+j);
            ExecYield();
            CHECK(ExecAESContext() == context);
            for (j = 0; j < AES_INTIN_WORDS; ++j)
                CHECK(context->request.intin[j] == (WORD)(0x8100+who*256+i+j));
            for (j = 0; j < AES_GLOBAL_WORDS; ++j)
                CHECK(context->request.global[j] == (WORD)(0x4200+who*256+i+j));
        }
        CHECK(published[1-who] != context);
        CHECK(ExecAESDetach());
        CHECK(ExecAESContext() == NULL);
        CHECK(ExecAESDetach());
        CHECK(ExecAESAttach(service));
        CHECK(ExecAESContext()->request.intin[0] == 0);
        CHECK(ExecAESDetach());
    }
    Forbid();
    AESFinished[who] = 1;
    Signal(controller, wake);
    RemTask(NULL);
}

void AESClientOne(void) { client(0); }
void AESClientTwo(void) { client(1); }

UWORD AESContextProbe(void)
{
    struct Task *one, *two;
    ULONG available = AvailMem(0);
    BYTE bit = AllocSignal(-1);
    if (timer_vectors() != 0) return 5;
    if (bit < 0) return 1;
    controller = FindTask(NULL);
    wake = 1UL << bit;
    service = CreateMsgPort();
    if (service == NULL) { FreeSignal(bit); return 2; }
    Forbid();
    one = CreateTask("AES C one", 0, (APTR)AESClientOne, 1024UL);
    two = CreateTask("AES C two", 0, (APTR)AESClientTwo, 1024UL);
    Permit();
    while ((one && !AESFinished[0]) || (two && !AESFinished[1])) Wait(wake);
    DeleteMsgPort(service);
    FreeSignal(bit);
    if (!one || !two || AESFailures[0] || AESFailures[1]) return 3;
    if (AvailMem(0) != available) return 4;
    return 0;
}

/* Read/write the same packet on opposite sides of a CPU bank boundary. */
UWORD AESWireProbe(void)
{
    struct AESRequest *r = (struct AESRequest *)AESProbePacket;
    UWORD i;
    if (!ExecAESPointer(r, sizeof(*r)) ||
        ExecAESPointer((void *)0x1000000UL, 1) ||
        ExecAESPointer((void *)0xfffffeUL, 3) ||
        ExecAESPointer(NULL, 1)) return 1;
    if (r->version != AES_VERSION || r->bytes != sizeof(*r) ||
        r->owner != FindTask(NULL) || r->binding != (UBYTE *)r ||
        r->sequence != 0x87654321UL) return 2;
    for (i = 0; i < AES_INTIN_WORDS; ++i) {
        if (r->intin[i] != -100-(WORD)i) return 3;
        r->intin[i] = 300+i;
    }
    for (i = 0; i < AES_GLOBAL_WORDS; ++i) {
        if (r->global[i] != 600+i) return 4;
        r->global[i] = -500-(WORD)i;
    }
    for (i = 0; i < AES_MESSAGE_WORDS; ++i) r->words[i] = -200-(WORD)i;
    return 0;
}
