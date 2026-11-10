/* SPDX-License-Identifier: MIT. GEMDOS names; allocation ownership is common. */
#include "qed-runtime.h"
#include "internal.h"
#include <stdlib.h>
LONG Malloc(LONG bytes)
{
    ULONG largest;
    if (bytes==-1) {
        largest=AvailMem(MEMF_UPPER|MEMF_LARGEST);
        if (largest>65536UL) largest=65536UL;
        return largest>EXEC_CRT_ALLOCATION_PREFIX ? largest-EXEC_CRT_ALLOCATION_PREFIX:0;
    }
    return bytes>0 && bytes<=65535UL ? (LONG)malloc((size_t)bytes):0;
}
LONG Mfree(void *pointer) { free(pointer);return 0; }
void QedHeapSnapshot(struct QedHeapStats *stats)
{
    struct ExecCRuntimeHeapStats native;
    ExecCRuntimeHeapSnapshot(&native);
    stats->blocks=native.blocks;stats->payload=native.payload;
    stats->backing=native.backing;stats->peakBacking=native.peakBacking;
}
