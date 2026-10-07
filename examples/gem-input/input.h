/* SPDX-License-Identifier: MIT */
#ifndef GEM_INPUT_H
#define GEM_INPUT_H
#include <gem.h>

struct InputConfig {
    const char *title;
    WORD x,y,width,height,ink,paper;
};
/* Application-owned upper memory keeps GEM arrays off the small Task stack. */
struct InputApp {
    const struct InputConfig *config;
    WORD id,vdi,window,opened;
    volatile WORD ready;
    volatile ULONG activations,paints;
    WORD message[8],work[4];
    char key[10],clicks[14];
    WORD down,armed,tick;
    WORD input[11],output[57];
};
WORD InputRun(struct InputApp *app);
/* The host translates a failed event call into retryable input loss or a fatal
 * error. The GEM body has no dependency on Exec attachment or diagnostics. */
WORD InputRecover(void);
#endif
