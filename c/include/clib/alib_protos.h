#ifndef CLIB_ALIB_PROTOS_H
#define CLIB_ALIB_PROTOS_H
#include <exec/tasks.h>

/* Same source signature as classic amiga.lib; Exec816 supplies one service. */
struct Task *EXEC_CALL CreateTask(CONST_STRPTR name, LONG priority,
                                 APTR entry, ULONG stackSize);

#endif
