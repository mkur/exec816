#ifndef EXEC_PORTS_H
#define EXEC_PORTS_H
#include <exec/tasks.h>

struct MsgPort {
    struct Node mp_Node;
    UBYTE mp_Flags;
    UBYTE mp_SigBit;
    struct Task EXEC_PTR *mp_SigTask;
    struct List mp_MsgList;
};

struct Message {
    struct Node mn_Node;
    struct MsgPort EXEC_PTR *mn_ReplyPort;
    UWORD mn_Length;
};

#endif
