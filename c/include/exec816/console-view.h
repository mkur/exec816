/* SPDX-License-Identifier: MIT */
#ifndef EXEC816_CONSOLE_VIEW_H
#define EXEC816_CONSOLE_VIEW_H
#include <exec816/console-view-types.h>
/* Handles belong to the subscribing Task. Unsubscribe before freeing its
 * signal or exiting. Snapshot cells are copied; match revisions across chunks
 * and acknowledge only a fully presented revision. A stale ACK rearms the hint.
 * Retired units return CLOSED until the consumer explicitly unsubscribes. */
ULONG EXEC_CALL ExecConsoleView(ULONG operation,ULONG first,ULONG second);
static inline ULONG ExecConsoleViewSubscribe(ULONG unit,ULONG signal)
{
    return ExecConsoleView(EXEC_CONSOLE_VIEW_OP_SUBSCRIBE,unit,signal);
}
static inline UWORD ExecConsoleViewUnsubscribe(ULONG view)
{
    return (UWORD)ExecConsoleView(EXEC_CONSOLE_VIEW_OP_UNSUBSCRIBE,view,0);
}
static inline UWORD ExecConsoleViewSnapshot(ULONG view,struct ExecConsoleViewSnapshot *packet)
{
    return (UWORD)ExecConsoleView(EXEC_CONSOLE_VIEW_OP_SNAPSHOT,view,(ULONG)packet);
}
static inline UWORD ExecConsoleViewAcknowledge(ULONG view,ULONG revision)
{
    return (UWORD)ExecConsoleView(EXEC_CONSOLE_VIEW_OP_ACKNOWLEDGE,view,revision);
}
static inline UWORD ExecConsoleViewInput(ULONG view,const struct ExecConsoleViewInput *packet)
{
    return (UWORD)ExecConsoleView(EXEC_CONSOLE_VIEW_OP_INPUT,view,(ULONG)packet);
}
static inline UWORD ExecConsoleViewPending(ULONG view)
{
    return (UWORD)ExecConsoleView(EXEC_CONSOLE_VIEW_OP_PENDING,view,0);
}
#endif
