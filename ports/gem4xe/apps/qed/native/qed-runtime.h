/* SPDX-License-Identifier: MIT */
#ifndef QED_RUNTIME_H
#define QED_RUNTIME_H
#include "qed-native.h"
#include <stddef.h>

struct QedHeapStats { ULONG blocks, payload, backing, peakBacking; };
void QedHeapSnapshot(struct QedHeapStats *stats);
void QedHeapCleanup(void);
/* A failed GUI retirement must retain its Process, image and owned backing. */
void QedRetirementFault(const char *message);
/* Copy zero/one native path argument; argv[0] and the vector share ownership. */
int QedArguments(const char *tail,const char *name,int *argc,char ***argv);
/* argc=0 reports invalid launch input; the editor opens an empty document.
 * The body releases GUI borrowers before returning to owned-runtime cleanup. */
int QedRuntimeRun(int (*body)(int,char **));
#endif
