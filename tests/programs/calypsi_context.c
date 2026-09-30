/* Integration probe: two C activations compute across real VBI switches.
 * Keep stress and observation state out of the small public example.
 */
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <proto/dos.h>

#define WORKER_STACK_SIZE 1536UL

struct XYMessage {
    struct Message message;
    WORD x, y;
};

static struct Task *worker;
static struct Task *sender;
static struct MsgPort *volatile service;
static ULONG wake_mask, done_mask;
volatile UWORD received_x, received_y, same_message;
volatile UWORD progress[2], failures;
volatile ULONG checksum[2];

static void check(BOOL condition)
{
    if (!condition)
        ++failures;
}

static void compute(UWORD who)
{
    ULONG a = 0x12345678UL + who;
    ULONG b = 0x87654321UL - who;
    UWORD index;
    /* No kernel calls: progress here requires VBI preemption. */
    for (index = 0; index < 30000; ++index) {
        a = (a << 1) ^ (a >> 31) ^ b;
        b += a ^ index;
        progress[who] = index + 1;
    }
    checksum[who] = a ^ b;
}

void Receiver(void)
{
    struct MsgPort *port = CreateMsgPort();
    struct XYMessage *message;
    service = port;
    check(FindTask(NULL) == worker);
    if (port != NULL) {
        port->mp_Node.ln_Name = "c-context";
        AddPort(port);
        check(GetMsg(port) == NULL);
    }
    Signal(sender, wake_mask);
    if (port == NULL)
        goto finished;
    compute(1);
    message = (struct XYMessage *)WaitPort(port);
    check(GetMsg(port) == &message->message);
    message->x += 50;
    message->y += 50;
    ReplyMsg(&message->message);
    RemPort(port);
    DeleteMsgPort(port);
finished:
    Forbid();
    Signal(sender, done_mask);
    RemTask(NULL);
    check(FALSE); /* Self removal must not return. */
}

int main(void)
{
    struct MsgPort *replies = NULL;
    struct XYMessage *message = NULL;
    BYTE wake, done;
    int result = 1;
    ULONG available;
    BPTR output = Output();
    static const char sending[] = "C sends: 10,20\nextra";
    static const char reply[] = "C reply: 60,70\n";
    static const char success[] = "C message returned; resources released.\n";

    check(output != 0 && Output() == output);
    check(Write(output, sending, sizeof(reply)-1) == sizeof(reply)-1);
    check(Write(output, NULL, 0) == 0);
    check(Write(output, sending, -65536L) == -1);
    check(Write(0, sending, 1) == -1);
    check(Write(output | 0x01000000L, sending, 1) == -1);
    check(Write(output, (const void *)((ULONG)sending | 0x01000000UL), 1) == -1);
    available = AvailMem(0);
    sender = FindTask(NULL);
    check(sender != NULL);
    check(AllocMem(0, MEMF_PUBLIC) == NULL);
    check(CreateTask(NULL, 0, (APTR)Receiver, 0) == NULL);
    check(CreateTask(NULL, -129, (APTR)Receiver, 1) == NULL);
    check(CreateTask(NULL, 128, (APTR)Receiver, 1) == NULL);
    check(CreateTask(NULL, 65536L, (APTR)Receiver, 1) == NULL);
    check(CreateTask(NULL, 0, (APTR)Receiver, 65536UL) == NULL);
    check(CreateTask(NULL, 0, (APTR)Receiver, 0xffffffffUL) == NULL);
    check(CreateTask(NULL, 0, NULL, 1) == NULL);
    check(CreateTask((CONST_STRPTR)0x01000000UL, 0, (APTR)Receiver, 1) == NULL);
    check(CreateTask(NULL, 0, (APTR)((ULONG)(APTR)Receiver | 0x01000000UL), 1) == NULL);
    wake = AllocSignal(31);
    check(wake == 31 && AllocSignal(31) == -1);
    if (wake != 31)
        return 1;
    done = AllocSignal(30);
    if (done != 30) {
        FreeSignal(wake);
        return 1;
    }
    wake_mask = 1UL << wake;
    done_mask = 1UL << done;
    check((SetSignal(wake_mask, wake_mask) & wake_mask) == 0);
    check((SetSignal(0, wake_mask) & wake_mask) == wake_mask);

    replies = CreateMsgPort();
    message = AllocMem(sizeof(*message), MEMF_PUBLIC | MEMF_CLEAR);
    if (replies == NULL || message == NULL)
        goto cleanup;
    check(IsListEmpty(&replies->mp_MsgList));
    check(message->x == 0 && message->y == 0);
    message->message.mn_ReplyPort = replies;
    message->message.mn_Length = sizeof(*message);
    message->x = 10;
    message->y = 20;
    Forbid();
    worker = CreateTask("context", -128, (APTR)Receiver, WORKER_STACK_SIZE);
    if (worker != NULL)
        check(worker->tc_Node.ln_Pri == -128);
    Permit();
    if (worker == NULL)
        goto cleanup;
    check(Wait(wake_mask) == wake_mask);
    if (service == NULL)
        goto wait_done;
    compute(0);
    Forbid();
    Forbid();
    check(FindPort("c-context") == service);
    PutMsg(service, &message->message);
    Permit();
    Permit();
    check(WaitPort(replies) == &message->message);
    same_message = GetMsg(replies) == &message->message;
    received_x = message->x;
    received_y = message->y;
wait_done:
    check(Wait(done_mask) == done_mask);
    check(FindPort("c-context") == NULL);
    result = !(same_message && received_x == 60 && received_y == 70);
cleanup:
    if (message != NULL)
        FreeMem(message, sizeof(*message));
    if (replies != NULL)
        DeleteMsgPort(replies);
    FreeSignal(done);
    FreeSignal(wake);
    check(AvailMem(0) == available);
    check(Write(output, reply, sizeof(reply)-1) == sizeof(reply)-1);
    check(Write(output, success, sizeof(success)-1) == sizeof(success)-1);
    return result || failures != 0;
}
