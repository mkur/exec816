/* SPDX-License-Identifier: MIT */
#ifndef GEM_PANEL_H
#define GEM_PANEL_H
#include <gem.h>
#pragma pack(push, 2)
struct Panel {
    WORD id,vdi,window,opened;
    volatile WORD ready;
    volatile ULONG actions,paints;
    WORD message[8],work[4],input[11],output[57];
    OBJECT tree[8];
    char status[22];
    WORD focus,armed,saved,down;
    WORD staged,applied;
};
#pragma pack(pop)
WORD PanelRun(struct Panel *);
#endif
