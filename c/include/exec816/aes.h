#ifndef EXEC816_AES_H
#define EXEC816_AES_H
#include <exec816/aes-wire.h>
#include <devices/timer.h>

struct ExecAESTimer {
    struct MsgPort *port;
    struct TimerClockRequest *query, *alarm;
    UBYTE state, opened;
    UWORD error;
};

/* Runtime hooks, separate from GEM application entry points. The startup
 * controller retains the service until every attached Task has detached. */
struct ExecAESContext {
    struct AESRequest request; /* Original binding address is also its packet. */
    struct MsgPort *service;
    struct MsgPort *replies;
    struct MsgPort *receiving;
    struct AESDelivery *records;
    struct AESDirectory *directory;
    struct AESEndpoint *endpoint;
    WORD control[5];
    WORD intin[AES_INTIN_WORDS], intout[AES_INTOUT_WORDS], words[AES_MESSAGE_WORDS];
    LONG addrin[3], addrout[1];
    UWORD diagnostic;
    UBYTE busy;
    ULONG identity, sequence;
    WORD gemId;
    struct ExecAESTimer timer;
};

BOOL ExecAESAttach(struct MsgPort *service);
BOOL ExecAESDetach(void);
struct ExecAESContext *ExecAESContext(void);
UWORD ExecAESDiagnostic(void);
BOOL ExecAESPointer(const void *pointer, ULONG bytes);
#endif
