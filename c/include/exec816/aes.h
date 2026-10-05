#ifndef EXEC816_AES_H
#define EXEC816_AES_H
#include <exec816/aes-wire.h>

/* Runtime hooks, separate from GEM application entry points. The startup
 * controller retains the service until every attached Task has detached. */
struct ExecAESContext {
    struct AESRequest request; /* Original binding address is also its packet. */
    struct MsgPort *service;
    struct MsgPort *replies;
    WORD control[5];
    LONG addrin[3], addrout[1];
    UWORD diagnostic;
    UBYTE busy;
    ULONG identity, sequence;
    WORD gemId;
};

BOOL ExecAESAttach(struct MsgPort *service);
BOOL ExecAESDetach(void);
struct ExecAESContext *ExecAESContext(void);
UWORD ExecAESDiagnostic(void);
BOOL ExecAESPointer(const void *pointer, ULONG bytes);
#endif
