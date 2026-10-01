/* Generated from abi/tasks.json; do not edit. */
#ifndef EXEC_TASKLEASE_H
#define EXEC_TASKLEASE_H
#include <exec/tasks.h>
struct TaskLease {
    struct Task EXEC_PTR *task;
    UBYTE pad;
    ULONG incarnation;
    void EXEC_PTR *identity;
    UBYTE pad2;
};
UBYTE EXEC_CALL RetainTask(struct Task *task, struct TaskLease *lease);
UBYTE EXEC_CALL ReleaseTask(struct TaskLease *lease);
#endif
