/* A bounded adaptation of the Amiga RKM port1/port2 message exchange.
 * Both sides share one executable; only the main task uses DOS output.
 */
#include <exec/memory.h>
#include <exec/ports.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <clib/alib_protos.h>

#define WORKER_STACK_SIZE 1536UL

struct XYMessage {
    struct Message message;
    WORD x, y;
};

static struct Task *sender;
static struct MsgPort *volatile service;
static ULONG ready_mask, done_mask;

/* The development runners also observe message identity and reply values. */
volatile UWORD received_x, received_y, same_message;

/* A port belongs to its receiver. The sender regains its message on reply. */
void Receiver(void)
{
    struct MsgPort *port = CreateMsgPort();
    service = port;
    if (port != NULL) {
        port->mp_Node.ln_Name = "xyport";
        AddPort(port);
    }
    Signal(sender, ready_mask);
    if (port != NULL) {
        struct XYMessage *request;
        WaitPort(port);
        request = (struct XYMessage *)GetMsg(port);
        request->x += 50;
        request->y += 50;
        ReplyMsg(&request->message);
        RemPort(port);
        DeleteMsgPort(port);
    }
    /* The sender may free shared state only after this Task has retired. */
    Forbid();
    Signal(sender, done_mask);
    RemTask(NULL);
}

int main(void)
{
    struct MsgPort *replies = NULL;
    struct XYMessage *request = NULL;
    BYTE ready_bit, done_bit;
    int result = 1;
    BPTR output = Output();
    static const char sending[] = "C sends: 10,20\n";
    static char received[] = "C reply: 00,00\n";
    static const char success[] = "C message returned; resources released.\n";

    if (output == 0 || Write(output, sending, sizeof(sending)-1) != sizeof(sending)-1)
        return 1;

    sender = FindTask(NULL);
    ready_bit = AllocSignal(-1);
    done_bit = AllocSignal(-1);
    if (ready_bit == -1 || done_bit == -1)
        goto cleanup;
    ready_mask = 1UL << ready_bit;
    done_mask = 1UL << done_bit;

    replies = CreateMsgPort();
    request = AllocMem(sizeof(*request), MEMF_PUBLIC | MEMF_CLEAR);
    if (replies == NULL || request == NULL)
        goto cleanup;
    request->message.mn_ReplyPort = replies;
    request->message.mn_Length = sizeof(*request);
    request->x = 10;
    request->y = 20;

    if (CreateTask("xyreceiver", 0, (APTR)Receiver, WORKER_STACK_SIZE) == NULL)
        goto cleanup;
    Wait(ready_mask);
    if (service != NULL) {
        struct MsgPort *found;
        Forbid();
        found = FindPort("xyport");
        PutMsg(service, &request->message);
        Permit();

        WaitPort(replies);
        same_message = GetMsg(replies) == &request->message;
        received_x = request->x;
        received_y = request->y;
        if (found == service && same_message && received_x == 60 && received_y == 70)
            result = 0;
    }
    Wait(done_mask);

cleanup:
    if (request != NULL)
        FreeMem(request, sizeof(*request));
    if (replies != NULL)
        DeleteMsgPort(replies);
    if (done_bit != -1)
        FreeSignal(done_bit);
    if (ready_bit != -1)
        FreeSignal(ready_bit);
    if (result == 0) {
        received[9] = '0' + received_x / 10;
        received[10] = '0' + received_x % 10;
        received[12] = '0' + received_y / 10;
        received[13] = '0' + received_y % 10;
        if (Write(output, received, sizeof(received)-1) != sizeof(received)-1 ||
            Write(output, success, sizeof(success)-1) != sizeof(success)-1)
            result = 1;
    }
    return result;
}
