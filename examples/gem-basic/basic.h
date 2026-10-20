/* SPDX-License-Identifier: MIT */
#ifndef GEM_BASIC_H
#define GEM_BASIC_H
#include <gem.h>

/* Private to each loaded application image. No resident editor state. */
struct BasicApp {
    WORD id,vdi,window,opened,ready;
    WORD cellw,cellh,input[11],output[57],message[8],work[4];
    ULONG paints;
};
WORD BasicOpen(struct BasicApp *);
WORD BasicClose(struct BasicApp *);
WORD BasicEvent(struct BasicApp *,WORD *);
WORD BasicRun(struct BasicApp *);
#endif
