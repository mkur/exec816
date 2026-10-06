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

void ExecAESRecycle(struct AESEndpoint *endpoint, struct AESDelivery *record)
{
    UWORD slot = (UWORD)(record - (struct AESDelivery *)endpoint->records);
    Forbid();
    endpoint->freeRecords |= (UWORD)(1U << slot);
    Permit();
}
