/* SPDX-License-Identifier: MIT */
#include "desktop.h"
static ULONG desktop_launch(struct Desktop *,const char *,const char *,UWORD);
static WORD desktop_copy_start(struct Browser *,WORD);
static WORD desktop_job_finish(struct Desktop *,WORD);
static WORD desktop_job_choice(struct Desktop *,WORD);
static WORD desktop_delete(struct Browser *);
static const char *desktop_association(struct Desktop *,const char *);
#include <exec816/aes.h>
#include <string.h>
#include <proto/exec.h>

enum { MENU_TITLE=3, MENU_OPEN=6, MENU_REFRESH=7, MENU_STOP=8, MENU_QUIT=9, MENU_PATH=10, MENU_NEW=11, MENU_RENAME=12, MENU_ICONS=15, MENU_LIST=16, MENU_NAME=17, MENU_PARENT=18, MENU_ALL=19, MENU_NONE=20 };
enum { DIALOG_PATH=1,DIALOG_NEW=2,DIALOG_RENAME=3,DIALOG_COPY=4,DIALOG_COPYING=5,DIALOG_DELETE=6,DIALOG_REPLACE=7,DIALOG_DELETING=8 };
static const OBJECT menuSource[] = {
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,11},
    {1,3,13,G_IBOX,0,0,0,8,0,424,11},
    {13,-1,-1,G_TITLE,0,0,(ULONG)"File",0,0,64,11},
    {0,5,14,G_IBOX,0,0,0,0,11,640,229},
    {14,6,18,G_BOX,0,0,0x00011100,8,0,160,90},
    {7,-1,-1,G_STRING,0,DISABLED,(ULONG)"Open",1,1,158,11},
    {8,-1,-1,G_STRING,0,0,(ULONG)"Refresh  Ctrl+L",1,12,158,11},
    {9,-1,-1,G_STRING,0,DISABLED,(ULONG)"Stop",1,23,158,11},
    {10,-1,-1,G_STRING,0,0,(ULONG)"Quit",1,34,158,11},
    {11,-1,-1,G_STRING,0,0,(ULONG)"Path...",1,45,158,11},
    {12,-1,-1,G_STRING,0,0,(ULONG)"New Folder",1,56,158,11},
    {18,-1,-1,G_STRING,0,DISABLED,(ULONG)"Rename...",1,67,158,11},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"View",64,0,64,11},
    {4,15,20,G_BOX,0,0,0x00011100,72,0,144,57},
    {16,-1,-1,G_STRING,0,0,(ULONG)"  Icons",1,1,142,11},
    {17,-1,-1,G_STRING,0,0,(ULONG)"  List",1,12,142,11},
    {19,-1,-1,G_STRING,0,0,(ULONG)"  Sort by name",1,23,142,11},
    {5,-1,-1,G_STRING,0,0,(ULONG)"Parent   Esc",1,78,158,11},
    {20,-1,-1,G_STRING,0,0,(ULONG)"Select All",1,34,142,11},
    {14,-1,-1,G_STRING,LASTOB,0,(ULONG)"Select None",1,45,142,11}
};
/* Membership belongs to the snapshot, not the reused visible OBJECTs. */
static WORD selected_entry(const struct Browser *b,UWORD index)
{
    return (b->selection[index>>3] & (1U<<(index&7)))!=0;
}
static void mark_entry(struct Browser *b,UWORD index,WORD state)
{
    UBYTE mask=1U<<(index&7);
    WORD delta;
    if (selected_entry(b,index)==state) return;
    delta=state ? 1:-1;
    b->selection[index>>3]^=mask;
    b->selectionCount+=delta;
    if (b->entries[index].kind>0) b->selectionDirectories+=delta;
}
static void clear_selection(struct Browser *b)
{
    memset(b->selection,0,sizeof(b->selection));
    b->selectionCount=b->selectionDirectories=0;
}
static WORD single_entry(struct Browser *b)
{
    WORD i;
    if (b->selectionCount!=1) return -1;
    for (i=0;i<b->count;++i) if (selected_entry(b,i)) return i;
    return -1;
}
static WORD has_parent(const struct Browser *b)
{
    const char *p=strchr(b->path,':');
    return p && p[1] && (p[1]!='/' || p[2]);
}
static WORD menu_state(struct Browser *b)
{
    WORD one=single_entry(b);
    WORD enabled=(!b->dialog && (b->selected==BROWSER_PARENT || (one>=0 && (b->entries[one].kind>0 || !b->child))) ? 1:0)
        |(b->child ? 2:0)|(!b->dialog && one>=0 ? 4:0)|(!b->dialog ? 8:0)
        |(b->desktop && !b->dialog && !b->desktop->job && b->selectionCount && !b->selectionDirectories ? 16:0)
        |(b->desktop && !b->dialog && !b->desktop->job && b->selectionCount ? 32:0)|(!b->dialog && b->parent ? 64:0);
    WORD changed=b->menuEnabled<0 ? 127:enabled^b->menuEnabled;
    if ((changed&1) && !menu_ienable(b->applicationMenu,MENU_OPEN,enabled&1)) return 0;
    if ((changed&2) && !menu_ienable(b->applicationMenu,MENU_STOP,enabled&2)) return 0;
    if ((changed&4) && !menu_ienable(b->applicationMenu,MENU_RENAME,enabled&4)) return 0;
    if ((changed&64) && !menu_ienable(b->applicationMenu,MENU_PARENT,enabled&64)) return 0;
    if (changed&8) {
        if (!menu_ienable(b->applicationMenu,MENU_REFRESH,enabled&8) ||
            !menu_ienable(b->applicationMenu,MENU_PATH,enabled&8) || !menu_ienable(b->applicationMenu,MENU_NEW,enabled&8) ||
            !menu_ienable(b->applicationMenu,MENU_ICONS,enabled&8) || !menu_ienable(b->applicationMenu,MENU_LIST,enabled&8) ||
            !menu_ienable(b->applicationMenu,MENU_NAME,enabled&8) ||
            !menu_ienable(b->applicationMenu,MENU_ALL,enabled&8) || !menu_ienable(b->applicationMenu,MENU_NONE,enabled&8)) return 0;
    }
    if (b->desktop && (changed&48)) {
        if (!menu_ienable(b->applicationMenu,30,(enabled&16)!=0) ||
            !menu_ienable(b->applicationMenu,31,(enabled&32)!=0)) return 0;
    }
    b->menuEnabled=enabled;return 1;
}
static void stop(struct Browser *b)
{
    if (b->child) { ExecBreakProgram(b->child);strcpy(b->status,"Stopping"); }
}
static void label(char *to,const char *from,WORD max)
{
    WORD i=0;
    while (i<max && from[i]) { to[i]=from[i];++i; }
    to[i]=0;
}
/* Grid scrolling keeps the first visible entry on a complete row. */
static WORD first_entry(struct Browser *b,WORD first)
{
    WORD extent;
    if (!b->iconView) return FileFirst(first,b->count+b->parent,b->visible);
    extent=((b->count+b->parent+b->columns-1)/b->columns-b->visible/b->columns)*b->columns;
    if (extent<0) extent=0;
    if (first<0) first=0;
    if (first>extent) first=extent;
    return first/b->columns*b->columns;
}
static WORD icon_kind(const struct FileEntry *entry)
{
    static const struct { const char *name;WORD icon; } apps[]={
        {"PANEL.APP",6},{"CALC.APP",7},{"TEXT.APP",8},{"COUNTER.APP",9}
    };
    WORD i;
    if (entry->kind>0) return 5;
    if (!strchr(entry->name,'.')) return 11;
    if (FileMatch("*.APP",entry->name)) {
        for (i=0;i<4;++i) if (FileMatch(apps[i].name,entry->name)) return apps[i].icon;
        return 2;
    }
    return 3;
}
/* The freed File slot owns four decorative edges. Existing black fill and
 * white disabled stipple give a dotted border without a new drawing operation. */
static void layout_focus(struct Browser *b)
{
    OBJECT *focus=&b->tree[BROWSER_FOCUS],*row,*edge;
    WORD index=display_index(b,b->selected)-b->first,i;
    focus->ob_flags=HIDETREE;
    if (!b->keyboardFocus || index<0 || index>=b->visible) return;
    row=&b->tree[BROWSER_ROW_FIRST+index];
    focus->ob_flags=0;
    focus->ob_x=row->ob_x;focus->ob_y=row->ob_y;
    /* A zero-sized container keeps its decorative children out of hit testing. */
    focus->ob_width=focus->ob_height=0;
    for (i=0;i<4;++i) {
        edge=&b->tree[BROWSER_STATUS+1+i];
        edge->ob_x=i==3 ? row->ob_width-1:0;
        edge->ob_y=i==1 ? row->ob_height-1:0;
        edge->ob_width=i<2 ? row->ob_width:1;
        edge->ob_height=i<2 ? 1:row->ob_height;
    }
}
/* Reuse the visible object pool and shared stock bitmaps for every directory. */
static void layout(struct Browser *b)
{
    WORD i,index,columns=(b->work[2]-16)/8,rows;
    if (b->dialog && b->dialog!=DIALOG_DELETE) {
        b->dialogTree[0].ob_x=b->work[0];b->dialogTree[0].ob_y=b->work[1];
        b->dialogTree[0].ob_width=b->work[2];b->dialogTree[0].ob_height=b->work[3];
        b->dialogTree[2].ob_width=b->work[2]-16;
        b->dialogTree[5].ob_y=b->work[3]-10;b->dialogTree[5].ob_width=b->work[2]-16;
        return;
    }
    b->columns=b->iconView ? (b->work[2]-16)/104:1;
    if (b->columns<1) b->columns=1;
    if (b->columns>BROWSER_ROWS) b->columns=BROWSER_ROWS;
    rows=(b->work[3]-BROWSER_CONTENT_TOP-BROWSER_CONTENT_BOTTOM)/(b->iconView ? 36:12);
    if (rows<1) rows=1;
    if (rows>BROWSER_ROWS/b->columns) rows=BROWSER_ROWS/b->columns;
    b->visible=rows*b->columns;
    b->first=first_entry(b,b->first);
    if (columns>80) columns=80;
    b->tree[0].ob_x=b->work[0];b->tree[0].ob_y=b->work[1];
    b->tree[0].ob_width=b->work[2];b->tree[0].ob_height=b->work[3];
    for (i=0;i<BROWSER_ROWS;++i) {
        OBJECT *row=&b->tree[BROWSER_ROW_FIRST+i];
        index=display_entry(b,b->first+i);
        row->ob_type=b->iconView ? G_CICON:G_BUTTON;
        row->ob_x=8+(i%b->columns)*104;
        row->ob_y=BROWSER_CONTENT_TOP+(i/b->columns)*(b->iconView ? 36:12);
        row->ob_width=b->iconView ? 104:b->work[2]-16;
        row->ob_height=b->iconView ? 32:10;
        row->ob_spec=(ULONG)b->labels[i];
        row->ob_flags=i<b->visible && (!b->iconView || index<b->count) ? SELECTABLE:SELECTABLE|HIDETREE;
        row->ob_state=index<b->count ? ((index==BROWSER_PARENT ? b->selected==BROWSER_PARENT:selected_entry(b,index)) ? SELECTED:0):DISABLED;
        b->labels[i][0]=0;
        if (index<b->count) {
            if (b->iconView) {
                b->icons[i]=*(const CICONBLK *)(ULONG)b->stock[index==BROWSER_PARENT ? 10:icon_kind(&b->entries[index])].ob_spec;
                label(b->labels[i],index==BROWSER_PARENT ? "..":b->entries[index].name,12);
                b->icons[i].monoblk.ib_ptext=(ULONG)b->labels[i];
                b->icons[i].monoblk.ib_yicon=2;
                b->icons[i].monoblk.ib_char&=0xf0ff;
                b->icons[i].monoblk.ib_wtext=96;
                row->ob_spec=(ULONG)&b->icons[i];
            } else {
                b->labels[i][0]=index==BROWSER_PARENT || b->entries[index].kind>0 ? '>':' ';
                label(b->labels[i]+1,index==BROWSER_PARENT ? "..":b->entries[index].name,columns-1);
            }
        }
    }
    b->tree[BROWSER_STATUS].ob_spec=(ULONG)b->status;
    b->tree[BROWSER_STATUS].ob_width=b->work[2]-16;
    b->tree[BROWSER_STATUS].ob_y=2;
    layout_focus(b);
    if (b->dialog==DIALOG_DELETE) {
        OBJECT *form=b->dialogTree;
        WORD width=b->work[2]-8,limit,length;
        if (width>360) width=360;
        form[0].ob_x=b->work[0]+(b->work[2]-width)/2;
        form[0].ob_y=b->work[1]+(b->work[3]-72)/2;
        form[0].ob_width=width;form[0].ob_height=72;
        form[0].ob_spec=0x00011170;
        form[1].ob_y=8;form[1].ob_width=width-16;
        form[2].ob_y=22;form[2].ob_width=width-16;
        form[3].ob_x=(width-144)/2;form[3].ob_y=50;
        form[4].ob_x=form[3].ob_x+80;form[4].ob_y=50;form[4].ob_width=64;
        form[5].ob_y=36;form[5].ob_width=width-16;
        form[6].ob_type=G_BOX;form[6].ob_flags=LASTOB;
        form[6].ob_spec=(form[b->focus].ob_state&SELECTED) ? 0x1170:0x1171;
        form[6].ob_x=form[b->focus].ob_x+3;
        form[6].ob_y=form[b->focus].ob_y+form[b->focus].ob_height-3;
        form[6].ob_width=form[b->focus].ob_width-6;form[6].ob_height=1;
        /* Abbreviate only the displayed name; the snapshot retains the full
         * name used by DeleteFile. Keep both ends visible after resizing. */
        limit=(width-16)/8;length=strlen(b->editText);
        if (length<=limit) strcpy(b->target,b->editText);
        else {
            WORD first=(limit-3)/2,last=limit-3-first;
            memcpy(b->target,b->editText,first);memcpy(b->target+first,"...",3);
            strcpy(b->target+first+3,b->editText+length-last);
        }
        form[2].ob_spec=(ULONG)b->target;
    }
}
static WORD sliders(struct Browser *b)
{
    WORD extent=b->dialog && b->dialog!=DIALOG_DELETE ? 0:first_entry(b,b->count+b->parent);
    WORD position=extent ? (LONG)b->first*1000/extent:0;
    WORD size=extent ? (LONG)b->visible*1000/(b->count+b->parent):1000;
    WORD current,unused;
    /* These reads use the caller-local window view. Unchanged setters would
     * still send a request and invalidate the scrollbar in the presenter. */
    if (!wind_get(b->window,WF_VSLSIZE,&current,&unused,&unused,&unused)) return 0;
    if (size!=current && !wind_set(b->window,WF_VSLSIZE,size,0,0,0)) return 0;
    if (!wind_get(b->window,WF_VSLIDE,&current,&unused,&unused,&unused)) return 0;
    return position==current || wind_set(b->window,WF_VSLIDE,position,0,0,0);
}
static WORD redraw(struct Browser *b,const WORD *damage)
{
    WORD okay;
    if (!ExecAESBeginUpdate(b->window)) return 0;
    okay=wind_get(b->window,WF_WXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3]);
    if (okay) {
        layout(b);
        okay=objc_draw(b->dialog && b->dialog!=DIALOG_DELETE ? b->dialogTree:b->tree,
                      0,MAX_DEPTH,damage[0],damage[1],damage[2],damage[3]);
        if (okay && b->dialog==DIALOG_DELETE)
            okay=objc_draw(b->dialogTree,0,MAX_DEPTH,damage[0],damage[1],damage[2],damage[3]);
    }
    if (okay) okay=ExecAESPainted(b->window,damage[0],damage[1],damage[2],damage[3]);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++b->paints;
    return okay;
}
static WORD view_checks(struct Browser *b)
{
    return menu_icheck(b->applicationMenu,MENU_ICONS,b->iconView) && menu_icheck(b->applicationMenu,MENU_LIST,!b->iconView)
        && menu_icheck(b->applicationMenu,MENU_NAME,b->sortNames);
}
static char *decimal(char *to,ULONG value)
{
    char digits[10];WORD n=0;
    do { digits[n++]='0'+value%10;value/=10; } while (value);
    while (n) *to++=digits[--n];
    *to=0;return to;
}
static void selection_status(struct Browser *b)
{
    char *p;
    if (!b->selectionCount) {
        if (b->truncated) strcpy(b->status,"First 256 entries (list full)");
        else strcpy(b->status,b->information);
        return;
    }
    p=decimal(b->status,b->selectionCount);strcpy(p," selected");
    if (b->truncated) strcat(p," (first 256 entries)");
}
static WORD describe(struct Browser *b)
{
    char *p,*read,*write;
    WORD length,i;
    decimal(b->information,b->totalBytes);
    length=strlen(b->information);read=b->information+length;
    p=write=read+(length-1)/3;*write=0;
    for (i=0;read>b->information;) {
        *--write=*--read;
        if (++i==3 && read>b->information) { *--write=',';i=0; }
    }
    strcpy(p," bytes in ");p=decimal(p+10,b->count);strcpy(p," items");
    label(b->target,b->path,64);
    return wind_set_str(b->window,WF_NAME,b->target);
}
static void sort_entries(struct Browser *b)
{
    WORD i,j;
    struct FileEntry *temp=AllocMem(sizeof(*temp),MEMF_PUBLIC);
    if (!temp) return;
    for (i=1;i<b->count;++i) {
        *temp=b->entries[i];j=i;
        while (j && ((temp->kind>0 && b->entries[j-1].kind<=0) ||
            ((temp->kind>0)==(b->entries[j-1].kind>0) && strcmp(temp->name,b->entries[j-1].name)<0))) {
            b->entries[j]=b->entries[j-1];--j;
        }
        b->entries[j]=*temp;
    }
    FreeMem(temp,sizeof(*temp));
}
/* Remap selected names only on the cold directory-enumeration path. */
static WORD refresh_path(struct Browser *b,const char *path,const char *reveal)
{
    WORD i,changed=strcmp(path,b->path)!=0,parentFocus=!changed && b->selected==BROWSER_PARENT;
    ULONG bytes=0;
    char *names=NULL,*next;
    if (reveal) strcpy(b->savedName,reveal);
    else b->savedName[0]=0;
    if (!changed) {
        if (b->selected>=0) strcpy(b->savedName,b->entries[b->selected].name);
        for (i=0;i<b->count;++i) if (selected_entry(b,i)) bytes+=strlen(b->entries[i].name)+1;
        if (bytes) {
            names=AllocMem(bytes,MEMF_PUBLIC);
            if (!names) { strcpy(b->status,"No memory for refresh");return redraw(b,b->work); }
            next=names;
            for (i=0;i<b->count;++i) if (selected_entry(b,i)) {
                strcpy(next,b->entries[i].name);next+=strlen(next)+1;
            }
        }
    }
    if (!FileScanBegin(&b->scan,path,&b->info,b->entries)) {
        if (names) FreeMem(names,bytes);
        strcpy(b->status,"Directory unavailable");return redraw(b,b->work);
    }
    b->refreshPending=0;
    b->totalBytes=0;
    while (FileScanNext(&b->scan)) if (b->info.fib_DirEntryType<0) b->totalBytes+=b->info.fib_Size;
    b->count=b->scan.count;b->truncated=b->scan.truncated;b->selected=-1;
    if (changed && !b->scan.error) { strcpy(b->path,path);b->first=0; }
    b->parent=has_parent(b);
    if (parentFocus && b->parent) b->selected=BROWSER_PARENT;
    if (changed) b->keyboardFocus=0;
    clear_selection(b);
    if (b->sortNames) sort_entries(b);
    for (i=0;i<b->count;++i) {
        if (!strcmp(b->entries[i].name,b->savedName)) {
            b->selected=i;
            if (reveal) mark_entry(b,i,1);
        }
        if (names) for (next=names;next<names+bytes;next+=strlen(next)+1)
            if (!strcmp(b->entries[i].name,next)) { mark_entry(b,i,1);break; }
    }
    if (names) FreeMem(names,bytes);
    if (!describe(b)) return 0;
    selection_status(b);
    if (b->scan.error) strcpy(b->status,"Directory read failed");
    layout(b);
    if (reveal && b->selected>=0) {
        i=display_index(b,b->selected);
        if (i>=b->visible) b->first=first_entry(b,(i/b->columns-b->visible/b->columns+1)*b->columns);
    }
    return sliders(b) && redraw(b,b->work);
}
static WORD refresh(struct Browser *b)
{
    return refresh_path(b,b->path,NULL);
}
static WORD scroll(struct Browser *b,WORD first)
{
    WORD damage[4];
    OBJECT *top=&b->tree[BROWSER_ROW_FIRST];
    OBJECT *bottom=&b->tree[BROWSER_ROW_FIRST+b->visible-1];
    first=first_entry(b,first);
    if (first==b->first) return 1;
    b->first=first;
    /* Include the row buttons' one-pixel borders and the gaps between rows.
     * The root clears old labels inside this clip; summary stays put. */
    damage[0]=b->work[0]+top->ob_x-1;
    damage[1]=b->work[1]+top->ob_y-1;
    damage[2]=b->work[2]-14;
    damage[3]=bottom->ob_y+bottom->ob_height-top->ob_y+2;
    return sliders(b) && redraw(b,damage);
}
/* Model changes redraw only changed visible cells and the opaque status strip. */
static WORD paint_selection(struct Browser *b)
{
    WORD i,index,state,focus,okay=1,area[4];
    WORD oldX=b->tree[BROWSER_FOCUS].ob_x,oldY=b->tree[BROWSER_FOCUS].ob_y;
    WORD oldFlags=b->tree[BROWSER_FOCUS].ob_flags;
    if (!ExecAESBeginUpdate(b->window)) return 0;
    layout_focus(b);
    for (i=0;i<b->visible && okay;++i) {
        OBJECT *row=&b->tree[BROWSER_ROW_FIRST+i];
        index=display_entry(b,b->first+i);
        if (index>=b->count) break;
        state=(index==BROWSER_PARENT ? b->selected==BROWSER_PARENT:selected_entry(b,index)) ? SELECTED:0;
        focus=(b->keyboardFocus && index==b->selected) ||
            (!(oldFlags&HIDETREE) && row->ob_x==oldX && row->ob_y==oldY);
        if (row->ob_state!=state || focus) {
            row->ob_state=state;
            if (focus) {
                area[0]=b->work[0]+row->ob_x-1;area[1]=b->work[1]+row->ob_y-1;
                area[2]=row->ob_width+2;area[3]=row->ob_height+2;
                okay=objc_draw(b->tree,0,MAX_DEPTH,area[0],area[1],area[2],area[3]);
            } else okay=objc_draw(b->tree,BROWSER_ROW_FIRST+i,0,
                b->work[0],b->work[1],b->work[2],b->work[3]);
        }
    }
    selection_status(b);
    area[0]=b->work[0]+8;area[1]=b->work[1];
    area[2]=b->work[2]-16;area[3]=12;
    if (okay) okay=objc_draw(b->tree,0,MAX_DEPTH,area[0],area[1],area[2],area[3]);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++b->paints;
    return okay;
}
/* mode: replace, toggle or add. The lead may be outside the selected set. */
static WORD select_entry(struct Browser *b,WORD index,WORD mode)
{
    WORD first=b->first,was,position=display_index(b,index),count=b->count+b->parent;
    if (!count) return 1;
    if (position<0) position=0;
    if (position>=count) position=count-1;
    index=display_entry(b,position);
    if (position<first) first=position/b->columns*b->columns;
    if (position>=first+b->visible) first=(position/b->columns-b->visible/b->columns+1)*b->columns;
    first=first_entry(b,first);
    was=index==BROWSER_PARENT ? b->selected==BROWSER_PARENT:selected_entry(b,index);
    b->selected=index;
    if (index==BROWSER_PARENT) clear_selection(b);
    else {
        if (mode==0 && was && b->selectionCount==1 && first==b->first &&
            !b->keyboardFocus && (b->tree[BROWSER_FOCUS].ob_flags&HIDETREE)) return 1;
        if (!mode) clear_selection(b);
        mark_entry(b,index,mode==1 ? !was:1);
    }
    selection_status(b);
    if (first!=b->first && !scroll(b,first)) return 0;
    return paint_selection(b);
}
static WORD select_row(struct Browser *b,WORD index)
{
    return select_entry(b,index,0);
}
static WORD select_all(struct Browser *b,WORD state)
{
    WORD i;
    if (b->selectionCount==(state ? b->count:0) && b->selected!=BROWSER_PARENT) return 1;
    if (b->selected==BROWSER_PARENT) b->selected=-1;
    clear_selection(b);
    if (state) for (i=0;i<b->count;++i) mark_entry(b,i,1);
    else b->selected=-1;
    return paint_selection(b);
}

static const OBJECT dialogSource[]={
    {-1,1,6,G_BOX,0,0,0x1170,0,0,216,144},
    {2,-1,-1,G_STRING,0,0,0,8,2,192,8},
    {3,-1,-1,G_BOXTEXT,EDITABLE,0,0,8,16,200,16},
    {4,-1,-1,G_BUTTON,SELECTABLE|DEFAULT|EXIT,0,(ULONG)"OK",8,40,64,16},
    {5,-1,-1,G_BUTTON,SELECTABLE|EXIT,0,(ULONG)"Cancel",96,40,88,16},
    {6,-1,-1,G_STRING,0,0,0,8,134,200,8},
    {0,-1,-1,G_BUTTON,LASTOB|HIDETREE,0,(ULONG)"Skip",80,40,56,16}
};
static WORD dialog_open(struct Browser *b,WORD kind)
{
    WORD i;
    TEDINFO *ted=&b->dialogTed;
    if (b->dialog || ((kind==DIALOG_COPY || kind==DIALOG_DELETE) && b->desktop->job)) return 1;
    if (kind==DIALOG_RENAME) {
        i=single_entry(b);if (i<0) return 1;b->selected=i;
    }
    if (kind==DIALOG_COPY && (!b->selectionCount || b->selectionDirectories || b->desktop->job)) return 1;
    if (kind==DIALOG_DELETE && !b->selectionCount) return 1;
    for (i=0;i<7;++i) b->dialogTree[i]=dialogSource[i];
    if (kind==DIALOG_PATH) b->dialogTree[1].ob_spec=(ULONG)"Path";
    else if (kind==DIALOG_NEW) b->dialogTree[1].ob_spec=(ULONG)"New Folder";
    else b->dialogTree[1].ob_spec=(ULONG)(kind==DIALOG_COPY ? (b->selectionCount>1 ? "Copy to directory":"Copy to (full path)"):"Rename");
    b->dialogTree[2].ob_spec=(ULONG)ted;b->dialogTree[5].ob_spec=(ULONG)b->status;
    b->dialogTed.te_ptext=(ULONG)b->editText;b->dialogTed.te_ptmplt=(ULONG)"";
    b->dialogTed.te_pvalid=(ULONG)"x";b->dialogTed.te_font=IBM;b->dialogTed.te_just=TE_LEFT;
    b->dialogTed.te_color=0x1180;b->dialogTed.te_thickness=-1;
    b->dialogTed.te_txtlen=(kind==DIALOG_PATH || kind==DIALOG_COPY) ? sizeof(b->editText):108;b->dialogTed.te_tmplen=1;
    if (kind!=DIALOG_REPLACE) strcpy(b->editText,kind==DIALOG_PATH ? b->path:kind==DIALOG_RENAME ? b->entries[b->selected].name:"");
    if (kind==DIALOG_COPY) {
        if (b->selectionCount>1) strcpy(b->editText,"WORK:");
        else FileJoin(b->editText,sizeof(b->editText),"WORK:",b->entries[single_entry(b)].name);
    }
    b->dialog=kind;b->focus=2;b->armed=-1;b->dialogError=0;
    if (kind!=DIALOG_DELETE) b->status[0]=0;
    if (kind==DIALOG_DELETE || kind==DIALOG_REPLACE) {
        if (kind==DIALOG_DELETE) {
            if (b->selectionCount==1) strcpy(b->editText,b->entries[single_entry(b)].name);
            else {
                char *p=decimal(b->editText,b->selectionCount-b->selectionDirectories);
                strcpy(p,b->selectionCount-b->selectionDirectories==1 ? " file, ":" files, ");
                p=decimal(p+strlen(p),b->selectionDirectories);
                strcpy(p,b->selectionDirectories==1 ? " folder":" folders");
            }
        }
        b->dialogTree[1].ob_spec=(ULONG)(kind==DIALOG_DELETE ?
            (b->selectionCount>1 ? "Delete selected items?":b->selectionDirectories ? "Delete folder?":"Delete file?"):"Replace this file?");
        b->dialogTree[2].ob_type=G_STRING;b->dialogTree[2].ob_flags=0;
        b->dialogTree[2].ob_spec=(ULONG)b->editText;
        b->dialogTree[3].ob_spec=(ULONG)(kind==DIALOG_DELETE ? "Delete":"Replace");
        b->dialogTree[3].ob_flags=SELECTABLE|EXIT;
        b->dialogTree[4].ob_flags|=DEFAULT;b->dialogTree[4].ob_state=kind==DIALOG_DELETE ? 0:SELECTED;b->focus=4;
        if (kind==DIALOG_DELETE) {
            b->dialogTree[5].ob_spec=(ULONG)"Empty folders only";
            b->dialogTree[5].ob_flags=b->selectionDirectories ? 0:HIDETREE;
        }
    }
    layout(b);
    return sliders(b) && redraw(b,b->work) &&
        (b->focus!=2 || objc_edit(b->dialogTree,2,0,&b->editIndex,ED_INIT));
}
static WORD dialog_end(struct Browser *b)
{
    WORD okay=b->dialog>=DIALOG_COPYING || objc_edit(b->dialogTree,2,0,&b->editIndex,ED_END);
    b->dialog=0;b->armed=-1;layout(b);
    return okay && sliders(b);
}
static WORD dialog_cancel(struct Browser *b)
{
    if (b->desktop && b->desktop->job && b->desktop->job->owner==b) return desktop_job_finish(b->desktop,1);
    if (!dialog_end(b)) return 0;
    selection_status(b);return redraw(b,b->work);
}
static WORD dialog_press(struct Browser *,WORD,WORD);
static WORD dialog_focus(struct Browser *b,WORD focus)
{
    WORD old=b->focus;
    if (b->focus==focus) return 1;
    if (b->focus==2 && !objc_edit(b->dialogTree,2,0,&b->editIndex,ED_END)) return 0;
    if (b->focus!=2) b->dialogTree[b->focus].ob_state=0;
    b->focus=focus;
    if (focus!=2) b->dialogTree[focus].ob_state=b->dialog==DIALOG_DELETE ? 0:SELECTED;
    if (b->dialog==DIALOG_DELETE) {
        layout(b);
        return dialog_press(b,old,0) && dialog_press(b,focus,0);
    }
    if (!redraw(b,b->work)) return 0;
    if (focus==2) return objc_edit(b->dialogTree,2,0,&b->editIndex,ED_INIT);
    return 1;
}
static WORD dialog_press(struct Browser *b,WORD object,WORD pressed)
{
    WORD okay;
    if (object!=3 && object!=4) return 1;
    if (pressed) b->dialogTree[object].ob_state|=SELECTED;
    else b->dialogTree[object].ob_state&=~SELECTED;
    if (!ExecAESBeginUpdate(b->window)) return 0;
    okay=objc_draw(b->dialogTree,object,0,b->work[0],b->work[1],b->work[2],b->work[3]);
    if (okay && object==b->focus) {
        b->dialogTree[6].ob_spec=pressed ? 0x1170:0x1171;
        okay=objc_draw(b->dialogTree,6,0,b->work[0],b->work[1],b->work[2],b->work[3]);
    }
    if (!wind_update(END_UPDATE)) okay=0;
    return okay;
}
static void full_name(struct Browser *b,const char *leaf,char *target)
{
    FileJoin(target,sizeof(b->target),b->path,leaf);
}
static WORD dialog_accept(struct Browser *b)
{
    BPTR lock;
    WORD i,kind=b->dialog,okay=0;
    if (kind==DIALOG_COPY || kind==DIALOG_REPLACE) return desktop_copy_start(b,kind==DIALOG_REPLACE);
    if (kind==DIALOG_DELETE) return desktop_delete(b);
    if (kind==DIALOG_COPYING || kind==DIALOG_DELETING) return 1;
    if (!b->editText[0] || (kind!=DIALOG_PATH &&
        (strchr(b->editText,':') || strchr(b->editText,'/') || strchr(b->editText,'\\') ||
         !strcmp(b->editText,".") || !strcmp(b->editText,"..")))) {
        strcpy(b->status,kind==DIALOG_PATH ? "Enter a directory":"Enter one leaf name");
        return redraw(b,b->work);
    }
    if (kind==DIALOG_PATH) {
        lock=Lock(b->editText,SHARED_LOCK);
        if (lock) {
            okay=Examine(lock,&b->info)!=0;
            b->dialogError=okay ? 0:IoErr();
            if (okay && b->info.fib_DirEntryType<=0) { okay=0;b->dialogError=ERROR_OBJECT_WRONG_TYPE; }
            UnLock(lock);
        } else b->dialogError=IoErr();
    } else {
        full_name(b,b->editText,b->target);
        if (kind==DIALOG_NEW) {
            lock=CreateDir(b->target);okay=lock!=0;b->dialogError=okay ? 0:IoErr();
            if (lock) UnLock(lock);
        } else {
            /* Keep both full paths off the Task stack during the DOS call. */
            char *destination=AllocMem(256UL,MEMF_PUBLIC);
            if (!destination) { strcpy(b->status,"No memory");return redraw(b,b->work); }
            strcpy(destination,b->target);full_name(b,b->entries[b->selected].name,b->target);
            okay=Rename(b->target,destination)!=0;b->dialogError=okay ? 0:IoErr();
            FreeMem(destination,256UL);
        }
    }
    if (!okay) {
        strcpy(b->status,b->dialogError==ERROR_OBJECT_EXISTS ? "Name already exists":
            b->dialogError==ERROR_OBJECT_NOT_FOUND ? "Not found":
            b->dialogError==ERROR_DISK_WRITE_PROTECTED || b->dialogError==ERROR_WRITE_PROTECTED ? "Read-only volume":
            b->dialogError==ERROR_INVALID_COMPONENT_NAME ? "Invalid name":
            b->dialogError==ERROR_DISK_FULL ? "Disk full":
            kind==DIALOG_PATH ? "Directory unavailable":"Operation failed");
        return redraw(b,b->work);
    }
    if (!dialog_end(b)) return 0;
    if (!refresh_path(b,kind==DIALOG_PATH ? b->editText:b->path,NULL)) return 0;
    if (kind!=DIALOG_PATH) {
        for (i=0;i<b->count;++i) if (!strcmp(b->entries[i].name,b->editText)) return select_row(b,i);
    }
    return 1;
}
static WORD dialog_key(struct Browser *b)
{
    WORD next=b->focus,key=b->kr;
    if ((key&255)==27) return dialog_cancel(b);
    if ((b->dialog==DIALOG_COPYING || b->dialog==DIALOG_DELETING)) return (key&255)==13 ? dialog_cancel(b):1;
    form_keybd(b->dialogTree,b->focus,b->focus,key,&next,&key);
    if (!key && next==3 && (b->kr&255)!=9 && b->kr!=0x0f00) return dialog_accept(b);
    if (!key && next==6 && b->dialog==DIALOG_REPLACE && (b->kr&255)!=9 && b->kr!=0x0f00) return desktop_job_choice(b->desktop,0);
    if (!key && next==4 && (b->kr&255)!=9 && b->kr!=0x0f00) return dialog_cancel(b);
    if (!dialog_focus(b,next)) return 0;
    return key && b->focus==2 ? objc_edit(b->dialogTree,2,key,&b->editIndex,ED_CHAR):1;
}
static WORD dialog_click(struct Browser *b,WORD hit)
{
    if ((b->dialog==DIALOG_COPYING || b->dialog==DIALOG_DELETING)) return hit==4 ? dialog_cancel(b):1;
    if (hit==6 && b->dialog==DIALOG_REPLACE) return desktop_job_choice(b->desktop,0);
    if (hit==3) return dialog_accept(b);
    if (hit==4) return dialog_cancel(b);
    if (hit==2 && b->dialog<DIALOG_COPYING) return dialog_focus(b,2);
    return 1;
}
static WORD up(struct Browser *b)
{
    const char *end,*leaf;
    if (!b->parent) return 1;
    end=b->path+strlen(b->path);
    if (end[-1]=='/') --end;
    leaf=end;
    while (leaf>b->path && leaf[-1]!='/' && leaf[-1]!=':') --leaf;
    memcpy(b->editText,leaf,end-leaf);b->editText[end-leaf]=0;
    strcpy(b->target,b->path);FileParent(b->target);
    return refresh_path(b,b->target,b->editText);
}
static WORD open_item(struct Browser *b)
{
    WORD i=single_entry(b);
    if (b->selected==BROWSER_PARENT) return up(b);
    if (i<0) return 1;
    if (!FileJoin(b->target,sizeof(b->target),b->path,b->entries[i].name)) return 1;
    if (b->entries[i].kind>0) {
        if (strlen(b->target)>=sizeof(b->path)) { strcpy(b->status,"Path too long");return redraw(b,b->work); }
        return refresh_path(b,b->target,NULL);
    }
    if (b->child) strcpy(b->status,"Command still running");
    else {
        const char *program=b->desktop ? desktop_association(b->desktop,b->entries[i].name):NULL;
        const char *name=b->entries[i].name;
        UWORD length=strlen(name);
        ULONG child;
        if (!b->desktop && length>=4 && name[length-4]=='.' && (name[length-3]|32)=='t' &&
            (name[length-2]|32)=='x' && (name[length-1]|32)=='t') program="C:TEXT.APP";
        if (program) {
            length=strlen(b->target);
            if (length>127) { strcpy(b->status,"Text path too long");return redraw(b,b->work); }
            memmove(b->target+1,b->target,length);
            b->target[0]='"';b->target[length+1]='"';b->target[length+2]=0;
            child=b->desktop ? desktop_launch(b->desktop,program,b->target,length+2):
                ExecStartProgram(program,b->target,length+2);
        } else child=b->desktop ? desktop_launch(b->desktop,b->target,NULL,0):ExecStartProgram(b->target,NULL,0);
        if (!b->desktop) b->child=child;
        if (child) { ++b->launches;strcpy(b->status,b->desktop ? "Application started":"Running (File > Stop)"); }
        else strcpy(b->status,"Cannot launch this file");
    }
    return redraw(b,b->work);
}
static WORD folder_open(struct Browser *b,OBJECT *source,OBJECT *popup,OBJECT *stock,
                        OBJECT *bar,WORD vdi,WORD x,WORD y,const char *path)
{
    WORD area[4];
    if (!wind_get(0,WF_WXYWH,&area[0],&area[1],&area[2],&area[3])) return 0;
    if (x>area[0]+area[2]-462) x=area[0]+area[2]-462;
    if (x<area[0]) x=area[0];
    if (y>area[1]+area[3]-196) y=area[1]+area[3]-196;
    if (y<area[1]) y=area[1];
    b->window=-1;b->selected=b->armed=-1;b->iconView=b->sortNames=1;
    if (b->desktop) { b->iconView=b->desktop->defaultIcons;b->sortNames=b->desktop->defaultSort; }
    b->menu=popup;b->stock=stock;b->applicationMenu=bar;b->vdi=vdi;
    b->tree=AllocMem((ULONG)BROWSER_OBJECTS*sizeof(OBJECT),MEMF_PUBLIC);
    b->entries=AllocMem((ULONG)sizeof(*b->entries)*BROWSER_ENTRIES,MEMF_PUBLIC);
    if (!b->tree || !b->entries) return 0;
    memcpy(b->tree,source,BROWSER_OBJECTS*sizeof(OBJECT));
    label(b->path,path,127);
    b->window=wind_create(NAME|CLOSER|MOVER|SIZER|UPARROW|DNARROW|VSLIDE|FULLER,x,y,462,196);
    if (b->window<0 || !wind_set_str(b->window,WF_NAME,"Files")) return 0;
    if (!wind_open(b->window,x,y,462,196)) return 0;
    b->opened=1;
    if (!wind_get(b->window,WF_WXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3]) ||
        !refresh(b)) return 0;
    b->ready=1;return 1;
}

static WORD folder_close(struct Browser *b)
{
    b->ready=0;
    if (b->desktop && b->desktop->job && b->desktop->job->owner==b && !desktop_job_finish(b->desktop,1)) return 0;
    if (b->dialog && !dialog_end(b)) return 0;
    if (b->child) {
        ExecBreakProgram(b->child);
        if (!ExecWaitProgram(b->child,&b->result)) return 0;
        b->child=0;
    }
    if (b->opened) { if (!wind_close(b->window)) return 0;b->opened=0; }
    if (b->window>0) { if (!wind_delete(b->window)) return 0;b->window=-1; }
    if (b->entries) { FreeMem(b->entries,(ULONG)sizeof(*b->entries)*BROWSER_ENTRIES);b->entries=NULL; }
    if (b->tree) { FreeMem(b->tree,(ULONG)BROWSER_OBJECTS*sizeof(OBJECT));b->tree=NULL; }
    return 1;
}

/* Dispatch only. The ordinary Files loop and the desktop use the same code. */
static WORD folder_event(struct Browser *b,WORD events)
{
    WORD i,hit,quit=0,result=0;
    if (!wind_get(b->window,WF_WXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3])) return -1;
        if (events&MU_BUTTON) {
            hit=objc_find(b->dialog ? b->dialogTree:b->tree,0,MAX_DEPTH,b->mx,b->my);
            if (b->dialog==DIALOG_DELETE && hit==6) hit=b->focus;
            if (b->mb&1) {
                if (b->keyboardFocus && !b->dialog) {
                    b->keyboardFocus=0;
                    if (!paint_selection(b)) result=2;
                }
                b->down=1;b->armed=hit;b->armedClicks=b->br;b->armedModifiers=b->ks;
                if (b->dialog==DIALOG_DELETE && !dialog_press(b,hit,1)) result=2;
            }
            else {
                b->down=0;
                if (b->dialog==DIALOG_DELETE && !dialog_press(b,b->armed,0)) result=2;
                if (hit==b->armed) {
                    if (b->dialog) { if (!dialog_click(b,hit)) result=2; }
                    else if (hit>=BROWSER_ROW_FIRST && hit<BROWSER_ROW_FIRST+b->visible &&
                             b->first+hit-BROWSER_ROW_FIRST<b->count+b->parent) {
                        i=display_entry(b,b->first+hit-BROWSER_ROW_FIRST);
                        hit=b->selected==i && b->armedClicks==2 && !b->armedModifiers;
                        if (!select_entry(b,i,(b->armedModifiers&3) ? 1:0) || (hit && !open_item(b))) result=2;
                    } else if (!(b->armedModifiers&3) && b->my>=b->work[1]+BROWSER_CONTENT_TOP &&
                               b->my<b->work[1]+b->work[3]-BROWSER_CONTENT_BOTTOM &&
                               (hit==0 || (hit>=BROWSER_ROW_FIRST && hit<BROWSER_STATUS))) {
                        if (!select_all(b,0)) result=2;
                    }
                }
                b->armed=-1;
            }
        }
        if (events&MU_KEYBD) {
            if (b->dialog) { if (!dialog_key(b)) result=2; }
            else if ((b->kr&255)==1 || ((b->ks&4) && ((b->kr&255)=='a' || (b->kr&255)=='A'))) { if (!select_all(b,1)) result=2; }
            else if ((b->kr&255)==27) { if (!up(b)) result=2; }
            else if ((b->kr&255)=='p' || (b->kr&255)=='P') { if (!dialog_open(b,DIALOG_PATH)) result=2; }
            else if ((b->kr&255)=='n' || (b->kr&255)=='N') { if (!dialog_open(b,DIALOG_NEW)) result=2; }
            else if ((b->kr&255)=='r' || (b->kr&255)=='R') { if (!dialog_open(b,DIALOG_RENAME)) result=2; }
            else if ((b->kr&255)==13) { if (!open_item(b)) result=2; }
            else if ((b->kr&255)==12 || ((b->ks&4) && ((b->kr&255)=='l' || (b->kr&255)=='L'))) { if (!refresh(b)) result=2; }
            else if ((b->kr>>8)==0x48 || (b->kr>>8)==0x50 || (b->kr>>8)==0x4b || (b->kr>>8)==0x4d) {
                hit=b->kr>>8;b->keyboardFocus=1;
                i=b->selected==-1 ? 0:display_index(b,b->selected)+(hit==0x48 ? -b->columns:hit==0x50 ? b->columns:hit==0x4b ? -1:1);
                if (i<0) i=0;
                if (i>=b->count+b->parent) i=b->count+b->parent-1;
                i=i<0 ? -1:display_entry(b,i);
                if (!select_entry(b,i,(b->ks&3) ? 2:0)) result=2;
            }
        }
        if ((events&MU_TIMER) && b->child && ExecCollectProgram(b->child,&b->result)) {
            b->child=0;
            if (!b->dialog) strcpy(b->status,b->result.primary ? "Command returned error":"Command finished");
            if (!redraw(b,b->work)) result=2;
        }
        if ((events&MU_MESAG) && b->message[0]==MN_SELECTED) {
            if (!b->dialog || b->message[4]==MENU_QUIT || b->message[4]==MENU_STOP) switch (b->message[4]) {
            case MENU_ALL:case MENU_NONE:if (!select_all(b,b->message[4]==MENU_ALL)) result=2;break;
            case MENU_ICONS:case MENU_LIST:
                b->iconView=b->message[4]==MENU_ICONS;b->first=0;layout(b);
                if (!view_checks(b) || !sliders(b) || !redraw(b,b->work)) result=2;break;
            case MENU_NAME:
                b->sortNames=!b->sortNames;
                if (!view_checks(b) || !refresh(b)) result=2;break;
            case MENU_OPEN:if (!open_item(b)) result=2;break;
            case MENU_REFRESH:if (!refresh(b)) result=2;break;
            case MENU_PARENT:if (!up(b)) result=2;break;
            case MENU_STOP:stop(b);if (!redraw(b,b->work)) result=2;break;
            case MENU_QUIT:quit=1;break;
            case MENU_PATH:if (!dialog_open(b,DIALOG_PATH)) result=2;break;
            case MENU_NEW:if (!dialog_open(b,DIALOG_NEW)) result=2;break;
            case MENU_RENAME:if (!dialog_open(b,DIALOG_RENAME)) result=2;break;
            }
            if (!menu_tnormal(b->applicationMenu,b->message[3],1)) result=2;
        }
        if ((events&MU_MESAG) && b->message[3]==b->window) {
            switch (b->message[0]) {
            case WM_CLOSED:quit=1;break;
            case WM_TOPPED:if (!wind_set(b->window,WF_TOP,0,0,0,0)) result=2;break;
            case WM_FULLED:
                if (!b->full) {
                    if (!wind_get(b->window,WF_CXYWH,&b->restore[0],&b->restore[1],&b->restore[2],&b->restore[3])) { result=2;break; }
                    if (!wind_get(0,WF_WXYWH,&b->message[4],&b->message[5],
                        &b->message[6],&b->message[7])) { result=2;break; }
                } else for (i=0;i<4;++i) b->message[4+i]=b->restore[i];
                b->full=!b->full;
                /* The same geometry acknowledgement handles full/restore. */
            case WM_SIZED:
                if (b->message[6]<240) b->message[6]=240;
                if (b->message[7]<144) b->message[7]=144;
                if (b->message[4]+b->message[6]>640) b->message[4]=640-b->message[6];
                if (b->message[5]+b->message[7]>240) b->message[5]=240-b->message[7];
                /* Fall through: the application accepts and relayouts. */
            case WM_MOVED:
                if (!wind_set(b->window,WF_CXYWH,b->message[4],b->message[5],b->message[6],b->message[7])) result=2;
                if (!wind_get(b->window,WF_WXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3])) result=2;
                layout(b);if (!sliders(b)) result=2;
                break;
            case WM_VSLID:
                if (b->dialog) break;
                if (!scroll(b,(LONG)b->message[4]*first_entry(b,b->count+b->parent)/1000)) result=2;
                break;
            case WM_ARROWED:
                if (b->dialog) break;
                hit=b->message[4];
                if (!scroll(b,b->first+(hit==WA_UPLINE ? -b->columns:hit==WA_DNLINE ? b->columns:
                    hit==WA_UPPAGE ? -b->visible:b->visible))) result=2;
                break;
            case WM_REDRAW:if (!redraw(b,&b->message[4])) result=2;break;
            }
        }
    return result ? -1:quit ? 0:1;
}

WORD BrowserRun(struct Browser *b)
{
    WORD i,cw,ch,bw,bh,events,quit=0,result=1;
    OBJECT *source,*popup,*stock;
    b->id=appl_init();b->window=-1;
    if (b->id<0) return 1;
    if (!rsrc_load("SYS:DESKTOP.RSC") || !rsrc_gaddr(R_TREE,0,(void **)&source) ||
        !rsrc_gaddr(R_TREE,1,(void **)&popup) || !rsrc_gaddr(R_TREE,2,(void **)&stock)) goto finish;
    for (i=0;i<21;++i) b->bar[i]=menuSource[i];
    b->applicationMenu=b->bar;
    if (!menu_bar(b->bar,1)) goto finish;
    b->menuInstalled=1;
    b->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) b->input[i]=1;
    b->input[10]=2;v_opnvwk(b->input,&b->vdi,b->output);
    if (!b->vdi || !folder_open(b,source,popup,stock,b->bar,b->vdi,16,24,"SYS:")) goto finish;
    if (!view_checks(b)) goto finish;
    result=0;
    while (!quit) {
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG|(b->child ? MU_TIMER:0),2,1,b->down ? 0:1,
            0,0,0,0,0,0,0,0,0,0,b->message,100,0,&b->mx,&b->my,&b->mb,&b->ks,&b->kr,&b->br);
        if (!events) {
            if (ExecAESDiagnostic()!=AES_INPUT_LOST) { result=2;break; }
            b->armed=-1;b->down=1;continue;
        }
        i=folder_event(b,events);
        if (i<0 || !menu_state(b)) { result=2;break; }
        quit=!i;
    }
finish:
    if (!folder_close(b)) result=3;
    if (b->menuInstalled) {
        if (!menu_bar(b->bar,0)) result=3;
        else b->menuInstalled=0;
    }
    if (b->vdi) { v_clsvwk(b->vdi);b->vdi=0; }
    if (!appl_exit()) result=3;
    b->id=0;return result;
}

#include "desktop.inc"
