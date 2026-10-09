/* SPDX-License-Identifier: MIT */
#ifndef GEM_BROWSER_H
#define GEM_BROWSER_H
#include <gem.h>
#include <proto/dos.h>
#include <exec816/program.h>
#define BROWSER_ENTRIES 256
#define BROWSER_ROWS 16
#define BROWSER_ROW_FIRST 4
#define BROWSER_STATUS (BROWSER_ROW_FIRST+BROWSER_ROWS)
struct BrowserEntry { char name[108]; LONG kind; };
struct Browser {
    WORD id,vdi,window,opened;
    volatile WORD ready;
    WORD message[8],work[4],input[11],output[57];
    OBJECT *tree,*menu;
    char path[128],status[128],target[256],savedName[108];
    char labels[BROWSER_ROWS][81];
    struct BrowserEntry *entries;
    struct FileInfoBlock info;
    WORD count,first,visible,selected,down,armed,truncated;
    volatile ULONG launches,paints;
    ULONG child;
    struct ExecProgramResult result;
    MENU popupInput,popupOutput;
    WORD mx,my,mb,ks,kr,br;
    OBJECT bar[13];
    WORD menuInstalled,menuEnabled;
    OBJECT dialogTree[6];
    TEDINFO dialogTed;
    char editText[128];
    WORD dialog,focus,editIndex;
    LONG dialogError;
};
WORD BrowserRun(struct Browser *);
#endif
