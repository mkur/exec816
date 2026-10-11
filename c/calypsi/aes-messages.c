#include "aes-private.h"
#include <proto/exec.h>

struct AESDelivery *ExecAESReserve(struct ExecAESContext *c, WORD id,
                                 struct AESEndpoint **destination)
{
    UWORD i, slot, bit;
    struct AESEndpoint *endpoint;
    struct AESDelivery *record = NULL;
    c->diagnostic = AES_IDENTITY;
    Forbid();
    for (i = 0; i < AES_CLIENTS; ++i) {
        endpoint = &c->directory->endpoints[i];
        if (endpoint->state != AES_ENDPOINT_ACCEPTING || endpoint->gemId != id)
            continue;
        c->diagnostic = AES_RESOURCE;
        if (endpoint->holds == 0xffff) break;
        for (slot = 0, bit = 1; slot < AES_QUEUE_DEPTH; ++slot, bit <<= 1) {
            if (!(endpoint->freeRecords & bit)) continue;
            endpoint->freeRecords &= ~bit;
            ++endpoint->holds;
            record = &endpoint->records[slot];
            *destination = endpoint;
            c->diagnostic = AES_OK;
            break;
        }
        break;
    }
    Permit();
    return record;
}

void ExecAESPublish(struct ExecAESContext *c, struct AESEndpoint *endpoint,
                    struct AESDelivery *record)
{
    record->message.mn_ReplyPort = NULL;
    record->message.mn_Length = sizeof(*record);
    PutMsg(endpoint->port, &record->message);
    /* The receiver may already have recycled record. Only the independent
     * publication hold remains ours, including when destination exit raced. */
    Forbid();
    --endpoint->holds;
    if (endpoint->state == AES_ENDPOINT_CLOSING && endpoint->holds == 0) {
        c->directory->changed = 1;
        Signal(c->directory->owner, c->directory->mask);
    }
    Permit();
}

void ExecAESRecycle(struct ExecAESContext *c, struct AESDelivery *record)
{
    struct AESEndpoint *endpoint = c->endpoint;
    Forbid();
    if (record == &endpoint->gui->delivery) {
        if (endpoint->gui->menuEpoch &&
            endpoint->gui->menuEpoch == endpoint->menuEpoch &&
            endpoint->gui->epoch == endpoint->guiEpoch)
            endpoint->menuConsumed = 1;
        endpoint->guiFree = 1;
        if (endpoint->guiWaiting) {
            c->directory->changed = 1;
            Signal(c->directory->owner, c->directory->mask);
        }
    } else {
        UWORD slot = (UWORD)(record - (struct AESDelivery *)endpoint->records);
        endpoint->freeRecords |= (UWORD)(1U << slot);
    }
    Permit();
}

/* This Task is the only receiver. Drop retired GUI notifications before the
 * event decision, leaving ordinary words (including WM_* lookalikes) opaque.
 * Keep the selected live record queued until timer retirement succeeds. */
BOOL ExecAESMessageReady(struct ExecAESContext *c)
{
    struct AESDelivery *record;
    BOOL stale;
    if (c->messagePending) {
        Forbid();
        stale = c->deferredEpoch &&
            (c->deferredEpoch != c->endpoint->guiEpoch ||
             (c->deferredMenuEpoch && c->deferredMenuEpoch != c->endpoint->menuEpoch));
        if (stale) c->messagePending=0;
        Permit();
        if (!stale) return TRUE;
    }
    /* A caller-local repair never needs space in the published queue.
     * Promote only after an older deferred message has been consumed. */
    if (c->repairEpoch) {
        Forbid();
        if (c->repairEpoch==c->endpoint->guiEpoch && c->view &&
            c->view->shown && c->view->handle==c->repairWindow) {
            c->deferredMessage[0]=WM_REDRAW;
            c->deferredMessage[1]=c->deferredMessage[2]=0;
            c->deferredMessage[3]=c->repairWindow;
            c->deferredMessage[4]=c->repair.left;
            c->deferredMessage[5]=c->repair.top;
            c->deferredMessage[6]=c->repair.right-c->repair.left;
            c->deferredMessage[7]=c->repair.bottom-c->repair.top;
            c->deferredEpoch=c->repairEpoch;
            c->deferredMenuEpoch=0;
            c->messagePending=1;
        }
        c->repairEpoch=0;
        Permit();
        if (c->messagePending) return TRUE;
    }
    for (;;) {
        Forbid();
        record = (struct AESDelivery *)c->receiving->mp_MsgList.lh_Head;
        if ((struct Node *)record == (struct Node *)&c->receiving->mp_MsgList.lh_Tail) {
            Permit();
            return FALSE;
        }
        stale = record == &c->endpoint->gui->delivery &&
            (c->endpoint->guiEpoch == 0 ||
             c->endpoint->gui->epoch != c->endpoint->guiEpoch ||
             (c->endpoint->gui->menuEpoch &&
              c->endpoint->gui->menuEpoch != c->endpoint->menuEpoch));
        Permit();
        if (!stale) return TRUE;
        record = (struct AESDelivery *)GetMsg(c->receiving);
        ExecAESRecycle(c, record);
    }
}
