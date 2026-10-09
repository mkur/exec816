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
    OBJECT home[6],edit[4],menu[9];
    TEDINFO ted;
    char text[32];
    WORD armed,down;
};
#pragma pack(pop)
WORD DialogRun(struct DialogApp *);
#endif
