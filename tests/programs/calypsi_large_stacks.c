/* Two ordinary C Tasks retain deep local frames across VBI and message calls. */
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <proto/dos.h>

struct XYMessage {
    struct Message message;
    WORD x, y;
};

static struct Task *sender;
static struct MsgPort *volatile service[2];
volatile UWORD received_x, received_y, same_message, failures;
volatile UWORD progress[3];
volatile ULONG checksum[3];
static volatile UWORD completed;

static void check(BOOL okay)
{
    if (!okay)
        ++failures;
}

static void compute(UWORD who)
{
    ULONG a = 0x12345678UL + who, b = 0x87654321UL - who;
    UWORD i;
    for (i = 0; i < 30000; ++i) {
        a = ((a << 1) ^ (a >> 31)) ^ b;
        b += a ^ i;
        progress[who] = i + 1;
    }
    checksum[who] = a ^ b;
}

static void deep(UWORD who, UWORD depth)
{
    volatile UBYTE local[256];
    UWORD i;
    for (i = 0; i < 256; ++i)
        local[i] = (UBYTE)(i ^ who ^ depth);
    if (depth)
        deep(who, depth - 1);
    else {
        struct XYMessage *message;
        Signal(sender, 1UL << (who + 29));
        compute(who + 1);
        message = (struct XYMessage *)WaitPort(service[who]);
        check(GetMsg(service[who]) == &message->message);
        message->x += 50;
        message->y += 50;
        ReplyMsg(&message->message);
    }
    for (i = 0; i < 256; ++i)
        check(local[i] == (UBYTE)(i ^ who ^ depth));
}

void Receiver(void)
{
    struct Task *self = FindTask(NULL);
    UWORD who = (UWORD)(ULONG)self->tc_UserData;
    service[who] = CreateMsgPort();
    check(service[who] != NULL);
    if (service[who]) {
        deep(who, 3);
        DeleteMsgPort(service[who]);
    } else {
        Signal(sender, 1UL << (who + 29));
    }
    Forbid();
    ++completed;
    Signal(sender, 1UL << 31);
    RemTask(NULL);
}

int main(void)
{
    struct MsgPort *replies;
    struct XYMessage *messages;
    UWORD who, count = 0;
    ULONG ready = 0;
    BPTR output = Output();
    static const char sending[] = "C sends: 10,20\n";
    static const char reply[] = "C reply: 60,70\n";
    static const char success[] = "C message returned; resources released.\n";
    check(Write(output, sending, sizeof(sending)-1) == sizeof(sending)-1);
    sender = FindTask(NULL);
    for (who = 29; who <= 31; ++who)
        if (AllocSignal(who) != who)
            return 1;
    replies = CreateMsgPort();
    if (!replies)
        return 1;
    /* Public messages need even addresses; native C stack objects may be odd. */
    messages = AllocMem(2 * sizeof(*messages), MEMF_PUBLIC | MEMF_CLEAR);
    if (!messages)
        return 1;
    Forbid();
    for (who = 0; who < 2; ++who) {
        struct Task *worker = CreateTask("large C", 0, (APTR)Receiver, 2560UL);
        check(worker != NULL);
        if (!worker)
            break;
        worker->tc_UserData = (APTR)(ULONG)who;
        ++count;
    }
    Permit();
    /* A partial admission is a test failure, but still retire the admitted Task. */
    while (ready != (((1UL << count)-1) << 29))
        ready |= Wait(3UL << 29);
    compute(0);
    for (who = 0; who < count; ++who) {
        messages[who].message.mn_ReplyPort = replies;
        messages[who].message.mn_Length = sizeof(struct XYMessage);
        messages[who].x = 10;
        messages[who].y = 20;
        if (service[who])
            PutMsg(service[who], &messages[who].message);
    }
    same_message = 1;
    for (who = 0; who < count; ++who) {
        if (service[who]) {
            struct Message *message = WaitPort(replies);
            check(GetMsg(replies) == message);
            same_message &= message == &messages[0].message || message == &messages[1].message;
        }
    }
    while (completed != count)
        Wait(1UL << 31);
    check(count == 2);
    for (who = 0; who < count; ++who)
        check(messages[who].x == 60 && messages[who].y == 70);
    received_x = count ? messages[0].x : 0;
    received_y = count ? messages[0].y : 0;
    FreeMem(messages, 2 * sizeof(*messages));
    DeleteMsgPort(replies);
    for (who = 29; who <= 31; ++who)
        FreeSignal(who);
    check(Write(output, reply, sizeof(reply)-1) == sizeof(reply)-1);
    check(Write(output, success, sizeof(success)-1) == sizeof(success)-1);
    return failures != 0;
}
