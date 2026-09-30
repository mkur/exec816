/* Generated from abi/tasks.json; do not edit. */
#ifndef EXEC_CREATE_TASK_PACKET_H
#define EXEC_CREATE_TASK_PACKET_H
#include <exec/types.h>
struct ExecCreateTaskPacket {
    const char EXEC_PTR *name;
    UBYTE pad3[1];
    LONG priority;
    void EXEC_PTR *entry;
    UBYTE pad11[1];
    ULONG stackSize;
};
#endif
