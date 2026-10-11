/* SPDX-License-Identifier: MIT */
#ifndef GEM_TEXT_APP_H
#define GEM_TEXT_APP_H
#include <gem.h>
#include "document.h"
struct TextApp {
    WORD id,vdi,window,opened,ready,first,rows,columns;
    WORD cellw,cellh,minw,minh,dirty,turn,menuInstalled,menuLoading;
    WORD work[4],damage[4],message[8],input[11],output[57];
    OBJECT menu[9];
    struct TextDocument document;
    struct TextLoad load;
    char path[128],file[13],target[128],directory[128],mask[128];
    char status[81],row[81];
    ULONG paints,loads,interruptions;
    WORD sliderSize,sliderPosition;
};
WORD TextRun(struct TextApp *);
#endif
