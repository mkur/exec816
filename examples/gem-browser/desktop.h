/* SPDX-License-Identifier: MIT */
#ifndef GEM_DESKTOP_H
#define GEM_DESKTOP_H
#include "browser.h"
#define DESKTOP_FOLDERS 3
#define DESKTOP_CHILDREN 3
#define DESKTOP_ICONS 8
#define DESKTOP_VOLUMES 4
enum { COPY_BUFFER_BYTES=16384, FILE_COPY=1, FILE_DELETE=2,
       JOB_NEXT=1, JOB_TRANSFER=2, JOB_REPLACE=3 };
struct DesktopFileJob {
    struct Browser *owner;
    BPTR input,output;
    ULONG copied;
    LONG error,cleanupError;
    WORD operation,state,index,total,completed,skipped,replacing,temporaryOwned,keepComplete;
    UBYTE pending[BROWSER_ENTRIES/8];
    char source[256],target[256],temporary[256],destination[128];
    UBYTE *buffer;
};
struct DesktopAssociation { char extension[4],program[64]; };
struct DesktopFolder { WORD bounds[4],icons,sort;char path[128]; };
enum { DRAG_ARMED=1,DRAG_TRACKING=2,DRAG_QUEUED=3,DRAG_CANCELLED=4,DRAG_RELEASE=5,
       DESKTOP_DROP=0x6e00 };
struct DesktopDrag {
    WORD phase,source,target,entry,pressX,pressY,lastX,lastY,hover,held;
    char destination[128];
};
struct Desktop {
    WORD id,vdi,window,opened,ready;
    struct Browser *folders[DESKTOP_FOLDERS],*active;
    OBJECT *source,*popup,*stock;
    OBJECT bar[33],tree[DESKTOP_ICONS+2];
    CICONBLK icons[DESKTOP_ICONS];
    ULONG children[DESKTOP_CHILDREN];
    struct ExecProgramResult result;
    WORD message[8],work[4],input[11],output[57];
    WORD mx,my,mb,ks,kr,br,down,armed,clicks,selected;
    WORD installed,quit;
    ULONG launches,paints;
    char status[65];
    struct DesktopFileJob *job;
    struct DesktopAssociation associations[2];
    struct DesktopFolder saved[DESKTOP_FOLDERS];
    WORD savedCount,mouse,defaultIcons,defaultSort,settingsLoaded;
    LONG error;
    char publishedStatus[65];
    struct DesktopDrag drag;
};
extern struct Desktop GEMDesk;
#endif
