/* SPDX-License-Identifier: MIT */
#ifndef QED_RUNTIME_H
#define QED_RUNTIME_H
#include "qed-native.h"
#include <stddef.h>

struct QedHeapStats { ULONG blocks, payload, backing, peakBacking; };
void QedHeapSnapshot(struct QedHeapStats *stats);
/* A failed GUI retirement retains its Process, Image and owned backing. */
void QedRetirementFault(const char *message);
#endif
