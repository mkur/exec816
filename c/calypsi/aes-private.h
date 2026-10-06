#ifndef EXEC816_AES_PRIVATE_H
#define EXEC816_AES_PRIVATE_H
#include <exec816/aes.h>

/* A reservation pins the destination until publication.
 * These helpers require an admitted caller; they do not enter GEM recursively. */
struct AESDelivery *ExecAESReserve(struct ExecAESContext *c, WORD id,
                                 struct AESEndpoint **destination);
void ExecAESPublish(struct ExecAESContext *c, struct AESEndpoint *destination,
                    struct AESDelivery *record);
void ExecAESRecycle(struct AESEndpoint *endpoint, struct AESDelivery *record);
#endif
