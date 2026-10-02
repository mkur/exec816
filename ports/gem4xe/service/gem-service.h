/* Private supervised service API. Records must stay at their original upper-RAM
 * addresses until stop/collection/disposal. Only the configured owner submits.
 * GEM headers are deliberately absent from this translation-unit boundary. */
#ifndef GEM_SERVICE_H
#define GEM_SERVICE_H
#include "gem-abi.h"

#define GEM_DOWN 0
#define GEM_STARTING 1
#define GEM_RUNNING 2
#define GEM_STOPPING_STATE 3
#define GEM_RETIRED 4

struct GemBackend {
    UWORD (*open)(void *context, WORD *workout);
    UWORD (*command)(void *context, const struct GemCommand *command,
                     const WORD *points, const WORD *ints, WORD *reply);
    UWORD (*fence)(void *context);
    UWORD (*close)(void *context);
    void *context;
};

struct GemScratch { WORD points[GEM_MAX_POINT_PAIRS * 2], ints[GEM_MAX_INT_WORDS]; };
struct GemClient;
struct GemServer {
    volatile UWORD state, startup_result;
    struct Task *owner, *worker;
    struct TaskLease owner_lease, worker_lease;
    struct MsgPort *port;
    struct GemScratch *scratch;
    const struct GemBackend *backend;
    struct GemClient *client;
    struct MsgPort *client_reply;
    struct GemRequest *inflight, *stop_packet;
    ULONG generation, session, next_sequence;
    ULONG ready_mask;
    struct MsgPort *stop_replies;
};

struct GemClient {
    struct GemServer *server;
    struct MsgPort *replies;
    struct GemRequest *packet, *pending;
    struct TaskLease owner_lease;
    ULONG session, next_sequence;
    UWORD status;
};

UWORD GemUpperExtent(const void *address, ULONG bytes);
UWORD GemAddressExtent(const void *address, ULONG bytes);
UWORD GemValidatePacket(const struct GemRequest *request);
UWORD GemServiceStart(struct GemServer *server, const struct GemBackend *backend);
void GemServiceWorker(void);
UWORD GemServiceStop(struct GemServer *server);

UWORD GemClientInit(struct GemClient *client, struct GemServer *server);
UWORD GemClientDispose(struct GemClient *client);
UWORD GemPrepare(struct GemClient *client, UWORD operation, UWORD commands, UWORD payload_bytes);
UWORD GemSubmit(struct GemClient *client);
UWORD GemCollect(struct GemClient *client);
UWORD GemStatus(const struct GemClient *client);
UWORD GemOpen(struct GemClient *client);
UWORD GemClose(struct GemClient *client);
UWORD GemCall(struct GemClient *client, UWORD opcode, UWORD subopcode,
              UWORD pairs, UWORD words, const WORD *points, const WORD *ints);
#endif
