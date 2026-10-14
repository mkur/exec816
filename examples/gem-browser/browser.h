/* SPDX-License-Identifier: MIT */
#ifndef GEM_BROWSER_H
#define GEM_BROWSER_H
#include <gem.h>
#include <proto/dos.h>
#include <exec816/program.h>
#include "../../c/calypsi/file-list.h"
#define BROWSER_ENTRIES FILE_LIST_LIMIT
#define BROWSER_ROWS 16
#define BROWSER_ROW_FIRST 2
#define BROWSER_STATUS (BROWSER_ROW_FIRST+BROWSER_ROWS)
#define BROWSER_OBJECTS (BROWSER_STATUS+5)
#define BROWSER_CONTENT_TOP 16
#define BROWSER_CONTENT_BOTTOM 2
#define BROWSER_FOCUS 1
#define BROWSER_PARENT (-2)
struct Browser {
    WORD id,vdi,window,opened;
    volatile WORD ready;
    WORD message[8],work[4],input[11],output[57];
    OBJECT *tree,*menu;
    char path[128],status[128],target[256],savedName[108];
    char labels[BROWSER_ROWS][81];
    struct FileEntry *entries;
    struct FileInfoBlock info;
    WORD count,first,visible,selected,down,armed,truncated;
    volatile ULONG launches,paints;
    ULONG child;
    struct ExecProgramResult result;
    MENU popupInput,popupOutput;
    WORD mx,my,mb,ks,kr,br;
    OBJECT bar[21];
    WORD menuInstalled;
    OBJECT dialogTree[7];
    TEDINFO dialogTed;
    char editText[128];
    WORD dialog,focus,editIndex;
    LONG dialogError;
    struct FileScan scan;
    OBJECT *stock;
    CICONBLK icons[BROWSER_ROWS];
    WORD iconView,sortNames,columns,armedClicks,full,restore[4];
    ULONG totalBytes;
    char information[65];
    OBJECT *applicationMenu;
    struct Desktop *desktop;
    UBYTE selection[BROWSER_ENTRIES/8];
    WORD selectionCount,selectionDirectories,armedModifiers,refreshPending;
    WORD keyboardFocus,parent;
};
/* Only display positions include the virtual parent. Membership and file jobs
 * always address the unchanged real-entry snapshot. */
static inline WORD display_entry(const struct Browser *b,WORD position)
{
    return b->parent && position==0 ? BROWSER_PARENT:position-b->parent;
}
static inline WORD display_index(const struct Browser *b,WORD entry)
{
    return entry==BROWSER_PARENT ? 0:entry<0 ? -1:entry+b->parent;
}
WORD BrowserRun(struct Browser *);
WORD DesktopRun(void);
#endif
