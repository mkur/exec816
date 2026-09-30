#ifndef EXEC_DOS_BRIDGE_H
#define EXEC_DOS_BRIDGE_H

#include <exec/types.h>

/* Full C-width values reach the Action! bridge before pointer validation. */
struct ExecDosWriteArgs {
    ULONG file;
    ULONG buffer;
    LONG length;
};

#endif
