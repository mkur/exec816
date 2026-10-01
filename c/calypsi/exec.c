#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include "create-task-packet.h"
#include "selectors.h"
#include "tasklease-packet.h"

ULONG EXEC_CALL _ExecPacket(UWORD selector, const void *packet);
ULONG EXEC_CALL _ExecPointer(UWORD selector, const void *pointer);

struct PointerPacket { void EXEC_PTR *pointer; };
struct PointerMask { void EXEC_PTR *pointer; UBYTE pad; ULONG value; };
struct Pair { ULONG first, second; };

#include "tasklease.inc"

APTR EXEC_CALL AllocMem(ULONG bytes, ULONG attributes)
{
    struct Pair args = {bytes, attributes};
    UBYTE *memory = (APTR)_ExecPacket(EXEC_ALLOC_MEM, &args);
    /* Clearing is caller work, just as in the Action! public binding. */
    if (memory != NULL && (attributes & MEMF_CLEAR)) {
        ULONG index;
        for (index = 0; index < bytes; ++index)
            memory[index] = 0;
    }
    return memory;
}

void EXEC_CALL FreeMem(APTR memory, ULONG bytes)
{
    struct PointerMask args = {memory, 0, bytes};
    _ExecPacket(EXEC_FREE_MEM, &args);
}

ULONG EXEC_CALL AvailMem(ULONG attributes)
{
    return _ExecPacket(EXEC_AVAIL_MEM, &attributes);
}

void EXEC_CALL NewList(struct List *list)
{
    list->lh_Head = (struct Node *)&list->lh_Tail;
    list->lh_Tail = NULL;
    list->lh_TailPred = (struct Node *)&list->lh_Head;
}

struct Task *EXEC_CALL CreateTask(CONST_STRPTR name, LONG priority,
                                 APTR entry, ULONG stackSize)
{
    struct ExecCreateTaskPacket args = {0};
    /* Huge C pointers must fit before conversion to the native 24-bit packet. */
    if ((ULONG)name > 0xffffffUL || (ULONG)entry > 0xffffffUL)
        return NULL;
    args.name = name;
    args.priority = priority;
    args.entry = entry;
    args.stackSize = stackSize;
    return (struct Task *)_ExecPacket(EXEC_CREATE_TASK, &args);
}

struct Task *EXEC_CALL AddTask(struct Task *task, void (*entry)(void), void (*finalizer)(void))
{
    struct {
        struct Task EXEC_PTR *task;
        void EXEC_PTR *entry;
        void EXEC_PTR *finalizer;
    } args = {task, (APTR)entry, (APTR)finalizer};
    return (struct Task *)_ExecPacket(EXEC_ADD_TASK, &args);
}

void EXEC_CALL RemTask(struct Task *task) { _ExecPointer(EXEC_REM_TASK, task); }
struct Task *EXEC_CALL FindTask(CONST_STRPTR name) { return (struct Task *)_ExecPointer(EXEC_FIND_TASK, name); }
void EXEC_CALL Forbid(void) { _ExecPointer(EXEC_FORBID, NULL); }
void EXEC_CALL Permit(void) { _ExecPointer(EXEC_PERMIT, NULL); }
void EXEC_CALL ExecYield(void) { _ExecPointer(EXEC_YIELD, NULL); }

BYTE EXEC_CALL AllocSignal(BYTE requested) { return (BYTE)_ExecPacket(EXEC_ALLOC_SIGNAL, &requested); }
void EXEC_CALL FreeSignal(BYTE number) { _ExecPacket(EXEC_FREE_SIGNAL, &number); }

ULONG EXEC_CALL SetSignal(ULONG signals, ULONG mask)
{
    struct Pair args = {signals, mask};
    return _ExecPacket(EXEC_SET_SIGNAL, &args);
}

void EXEC_CALL Signal(struct Task *task, ULONG signals)
{
    struct PointerMask args = {task, 0, signals};
    _ExecPacket(EXEC_SIGNAL, &args);
}

ULONG EXEC_CALL Wait(ULONG signals) { return _ExecPacket(EXEC_WAIT, &signals); }

struct MsgPort *EXEC_CALL CreateMsgPort(void)
{
    struct MsgPort *port = AllocMem(sizeof(*port), MEMF_PUBLIC | MEMF_CLEAR);
    BYTE bit;
    if (port == NULL)
        return NULL;
    bit = AllocSignal(-1);
    if (bit == -1) {
        FreeMem(port, sizeof(*port));
        return NULL;
    }
    port->mp_Node.ln_Type = NT_MSGPORT;
    port->mp_SigBit = bit;
    port->mp_SigTask = FindTask(NULL);
    NewList(&port->mp_MsgList);
    return port;
}

void EXEC_CALL DeleteMsgPort(struct MsgPort *port)
{
    struct PointerPacket args = {port};
    if (port != NULL) {
        BYTE bit = (BYTE)_ExecPacket(EXEC_DELETE_CHECK, &args);
        FreeSignal(bit);
        FreeMem(port, sizeof(*port));
    }
}

void EXEC_CALL PutMsg(struct MsgPort *port, struct Message *message)
{
    struct { struct MsgPort EXEC_PTR *port; struct Message EXEC_PTR *message; } args = {port, message};
    _ExecPacket(EXEC_PUT_MSG, &args);
}

struct Message *EXEC_CALL GetMsg(struct MsgPort *port)
{
    struct PointerPacket args = {port};
    return (struct Message *)_ExecPacket(EXEC_GET_MSG, &args);
}

struct Message *EXEC_CALL WaitPort(struct MsgPort *port)
{
    struct PointerPacket args = {port};
    struct Message *message;
    for (;;) {
        message = (struct Message *)_ExecPacket(EXEC_WAIT_HEAD, &args);
        if (message != NULL)
            return message;
        /* Never clear the signal between observing an empty queue and Wait. */
        Wait(1UL << port->mp_SigBit);
    }
}

void EXEC_CALL ReplyMsg(struct Message *message)
{
    struct PointerPacket args = {message};
    _ExecPacket(EXEC_REPLY_MSG, &args);
}

void EXEC_CALL AddPort(struct MsgPort *port)
{
    struct PointerPacket args = {port};
    _ExecPacket(EXEC_ADD_PORT, &args);
}

void EXEC_CALL RemPort(struct MsgPort *port)
{
    struct PointerPacket args = {port};
    _ExecPacket(EXEC_REM_PORT, &args);
}

struct MsgPort *EXEC_CALL FindPort(CONST_STRPTR name)
{
    struct PointerPacket args = {(APTR)name};
    return (struct MsgPort *)_ExecPacket(EXEC_FIND_PORT, &args);
}
