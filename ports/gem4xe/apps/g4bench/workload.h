/* Exec adaptation declarations for G4BENCH; GPL-2.0-or-later. */
#ifndef G4BENCH_WORKLOAD_H
#define G4BENCH_WORKLOAD_H
#include <gem.h>
void BenchSetup(WORD,const WORD *,WORD);
void BenchClip(WORD,WORD *);
void BenchDraw(WORD,WORD);
UWORD BenchTextLength(void);
#endif
