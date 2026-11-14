/* SPDX-License-Identifier: MIT. Extracted from the QED native adapter. */
#include <compat/gemdos.h>
#include <exec816/c-runtime.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <stdlib.h>
#include <errno.h>

void *Malloc(LONG bytes)
{
    ULONG largest;
    if (bytes==-1) {
        largest=AvailMem(MEMF_UPPER|MEMF_LARGEST);
        if (largest>65536UL) largest=65536UL;
        largest=largest>EXEC_CRT_ALLOCATION_PREFIX ? largest-EXEC_CRT_ALLOCATION_PREFIX:0;
        return (void *)largest;
    }
    if (bytes<0 || (ULONG)bytes>EXEC_CRT_MAX_ALLOCATION) {
        errno=bytes<0 ? EINVAL:ENOMEM;
        SetIoErr(bytes<0 ? ERROR_BAD_ARGUMENTS:ERROR_NO_FREE_STORE);
        return NULL;
    }
    return malloc((size_t)bytes);
}
LONG Mfree(void *memory) { free(memory);return 0; }
