/* SPDX-License-Identifier: MIT */
#ifndef GEM_COUNTER_H
#define GEM_COUNTER_H
#include <gem.h>

struct CounterConfig {
    const char *title;
    WORD x,y,width,height,ink,paper;
};
/* The resident wrapper supplies upper-memory application storage. Keeping the
 * model and GEM arrays here leaves the small Task stack for call depth. */
struct Counter {
    const struct CounterConfig *config;
    WORD id,vdi,window,opened;
    volatile WORD ready;
    volatile ULONG count,paints;
    WORD message[8],work[4];
    char label[14];
    WORD input[11],output[57];
};
WORD CounterRun(struct Counter *app);
#endif
