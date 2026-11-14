/* SPDX-License-Identifier: MIT. Editor diagnostics over the common CRT. */
#include "qed-runtime.h"
#include "internal.h"
#include <stdlib.h>
void QedHeapSnapshot(struct QedHeapStats *stats)
{
    struct ExecCRuntimeHeapStats native;
    ExecCRuntimeHeapSnapshot(&native);
    stats->blocks=native.blocks;stats->payload=native.payload;
    stats->backing=native.backing;stats->peakBacking=native.peakBacking;
}
