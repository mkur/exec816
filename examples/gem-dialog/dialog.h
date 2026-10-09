/* SPDX-License-Identifier: MIT */
#ifndef GEM_DIALOG_EXAMPLE_H
#define GEM_DIALOG_EXAMPLE_H
#include <gem.h>
#pragma pack(push,2)
struct DialogApp {
    WORD id,vdi,window,opened;
    volatile WORD ready,phase;
    volatile ULONG accepted,paints,interruptions;
    WORD message[8],work[4],input[11],output[57];
    OBJECT home[10],edit[4],menu[11];
    TEDINFO ted;
    char text[32];
    WORD armed,down;
    char path[128],file[13],directory[40],selection[40];
    WORD fileButton,fileResult;
};
#pragma pack(pop)
WORD DialogRun(struct DialogApp *);
#endif
