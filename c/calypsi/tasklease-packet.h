/* Generated from abi/tasks.json; do not edit. */
#ifndef EXEC_TASKLEASE_PACKET_H
#define EXEC_TASKLEASE_PACKET_H
#include <exec/tasklease.h>
struct ExecRetainTaskPacket {
    struct Task EXEC_PTR *task;
    struct TaskLease EXEC_PTR *lease;
};
#endif
