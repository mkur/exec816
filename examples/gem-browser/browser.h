/* SPDX-License-Identifier: MIT */
#ifndef GEM_BROWSER_H
#define GEM_BROWSER_H
#include <gem.h>
#include <proto/dos.h>
#include <exec816/program.h>
struct Browser {
    WORD id,vdi,window,opened;
    volatile WORD ready;
    WORD message[8],work[4],input[11],output[57];
    OBJECT *tree,*menu;
    char path[128],names[8][108],labels[8][27],status[28],target[256];
    LONG kinds[8];
    struct FileInfoBlock info;
    WORD count,page,selected,down,armed;
    volatile ULONG launches,paints;
    ULONG child;
    struct ExecProgramResult result;
    /* Popup descriptors and event outputs outlive nested drawing calls. */
    MENU popupInput,popupOutput;
    WORD mx,my,mb,ks,kr,br;
    OBJECT bar[10];
    WORD menuInstalled,menuEnabled;
};
WORD BrowserRun(struct Browser *);
#endif
