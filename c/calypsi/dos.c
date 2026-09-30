#include <proto/dos.h>
#include "dos-bridge.h"

/* The launcher installs these native entry addresses before entering C. */
void EXEC_PTR *ExecDosEntries[2];

ULONG EXEC_CALL _DosCall(UWORD entry, const struct ExecDosWriteArgs *args);

BPTR EXEC_CALL Output(void)
{
    return (BPTR)_DosCall(0, NULL);
}

LONG EXEC_CALL Write(BPTR file, const void *buffer, LONG length)
{
    struct ExecDosWriteArgs args = {(ULONG)file, (ULONG)buffer, length};
    return (LONG)_DosCall(sizeof(ExecDosEntries[0]), &args);
}
