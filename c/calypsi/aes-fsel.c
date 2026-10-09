/* A synchronous file chooser in its caller; Files shares the directory model. */
#include "aes-fsel-private.h"
#include <proto/exec.h>
#include <string.h>

static void changed(struct ExecAESContext *c,WORD object)
{
    c->form->saved[object]=~c->form->tree[object].ob_state;
}

static void remember(struct ExecAESContext *c)
{
    struct ExecAESForm *f=c->form;
    WORD i;
    f->oldFocus=f->focus;
    for (i=0;i<f->count;++i) f->saved[i]=f->tree[i].ob_state;
}

static void status(struct ExecAESContext *c,const char *text)
{
    strcpy(c->form->fileSelector->status,text); changed(c,FS_STATUS);
}

static void object(struct ExecAESFileSelector *a,WORD i,WORD type,WORD flags,
                   ULONG spec,WORD x,WORD y,WORD w,WORD h)
{
    OBJECT *o=&a->tree[i];
    o->ob_next=i+1; o->ob_head=o->ob_tail=NIL;
    o->ob_type=type; o->ob_flags=flags; o->ob_spec=spec;
    o->ob_x=x; o->ob_y=y; o->ob_width=w; o->ob_height=h;
}

static void text_object(struct ExecAESFileSelector *a,WORD i,WORD t,char *text,
                        WORD capacity,WORD editable,WORD x,WORD y,WORD w,WORD h)
{
    TEDINFO *ted=&a->ted[t];
    ted->te_ptext=(ULONG)text; ted->te_ptmplt=(ULONG)""; ted->te_pvalid=(ULONG)"X";
    ted->te_font=IBM; ted->te_just=TE_LEFT; ted->te_color=editable ? 0x1180:0x1170;
    ted->te_thickness=editable ? -1:0; ted->te_txtlen=capacity; ted->te_tmplen=1;
    object(a,i,G_BOXTEXT,editable ? EDITABLE:0,(ULONG)ted,x,y,w,h);
}

static void tree(struct ExecAESFileSelector *a,WORD w,WORD h)
{
    WORD i;
    object(a,0,G_BOX,0,0x1170,0,0,w,h);
    a->tree[0].ob_next=NIL; a->tree[0].ob_head=1; a->tree[0].ob_tail=FS_OBJECTS-1;
    text_object(a,FS_CAPTION,19,a->title,31,0,8,2,w-16,12);
    object(a,FS_PATH_LABEL,G_STRING,0,(ULONG)"Path:",8,20,40,8);
    text_object(a,FS_PATH,0,a->path,128,1,48,16,w-56,16);
    object(a,FS_FILE_LABEL,G_STRING,0,(ULONG)"File:",8,40,40,8);
    text_object(a,FS_FILE,1,a->file,13,1,48,36,w-104,16);
    object(a,FS_UP,G_BUTTON,SELECTABLE,(ULONG)"Up",w-48,36,40,16);
    object(a,FS_REFRESH,G_BUTTON,SELECTABLE,(ULONG)"Refresh",w-64,56,56,14);
    object(a,FS_LINE_UP,G_BUTTON,SELECTABLE,(ULONG)"^",w-64,74,24,14);
    object(a,FS_LINE_DOWN,G_BUTTON,SELECTABLE,(ULONG)"v",w-32,74,24,14);
    object(a,FS_PAGE_UP,G_BUTTON,SELECTABLE,(ULONG)"<<",w-64,92,24,14);
    object(a,FS_PAGE_DOWN,G_BUTTON,SELECTABLE,(ULONG)">>",w-32,92,24,14);
    text_object(a,FS_STATUS,18,a->status,80,0,8,h-32,w-80,8);
    object(a,FS_OK,G_BUTTON,SELECTABLE|DEFAULT,(ULONG)"OK",8,h-20,64,16);
    object(a,FS_CANCEL,G_BUTTON,SELECTABLE,(ULONG)"Cancel",88,h-20,80,16);
    if ((w-16)/8<30) a->title[(w-16)/8]=0;
    a->visible=(h-88)/12;
    if (a->visible>16) a->visible=16;
    for (i=0;i<16;++i) {
        text_object(a,FS_ROW+i,i+2,a->labels[i],16,0,8,56+i*12,w-80,12);
        a->tree[FS_ROW+i].ob_flags=SELECTABLE|(i<a->visible ? 0:HIDETREE);
    }
    a->tree[FS_OBJECTS-1].ob_flags|=LASTOB;
    a->tree[FS_OBJECTS-1].ob_next=0;
}

static WORD eligible(struct ExecAESFileSelector *a,WORD i)
{
    return i>0 && i<FS_OBJECTS && (a->tree[i].ob_flags&(SELECTABLE|EDITABLE)) &&
        !(a->tree[i].ob_flags&HIDETREE) && !(a->tree[i].ob_state&DISABLED);
}

static void rows(struct ExecAESContext *c)
{
    struct ExecAESFileSelector *a=c->form->fileSelector;
    WORD i,index,n;
    a->first=FileFirst(a->first,a->count,a->visible);
    for (i=0;i<a->visible;++i) {
        index=a->first+i; a->labels[i][0]=0;
        a->tree[FS_ROW+i].ob_state=a->loading || index>=a->count ? DISABLED:
            index==a->selected ? SELECTED:0;
        if (index<a->count) {
            struct FileEntry *entry=&a->entries[a->indices[index]];
            a->labels[i][0]=entry->kind>0 ? '>':' ';
            for (n=0;n<14 && entry->name[n];++n) a->labels[i][n+1]=entry->name[n];
            a->labels[i][n+1]=0;
        }
        changed(c,FS_ROW+i);
    }
    for (i=FS_PATH;i<=FS_PAGE_DOWN;++i)
        if (a->tree[i].ob_flags&(SELECTABLE|EDITABLE))
            a->tree[i].ob_state=a->loading ? DISABLED:0;
    for (i=FS_LINE_UP;i<=FS_PAGE_DOWN;++i)
        if (a->count<=a->visible) a->tree[i].ob_state=DISABLED;
    a->tree[FS_OK].ob_state=a->loading || !a->valid ? DISABLED:0;
}

static WORD list_focus(struct ExecAESFileSelector *a)
{
    return a->count ? FS_ROW+(a->selected>=a->first && a->selected<a->first+a->visible ?
                            a->selected-a->first:0):FS_FILE;
}

static WORD selected(struct ExecAESContext *c,WORD index)
{
    struct ExecAESFileSelector *a=c->form->fileSelector;
    WORD old=a->selected,first=a->first;
    struct FileEntry *entry;
    if (!a->count) return 1;
    if (index<0) index=0; if (index>=a->count) index=a->count-1;
    a->selected=index; a->first=FileExpose(a->first,index,a->visible);
    if (a->first!=first) rows(c);
    else {
        if (old>=first && old<first+a->visible) a->tree[FS_ROW+old-first].ob_state=0;
        a->tree[FS_ROW+index-first].ob_state=SELECTED;
    }
    entry=&a->entries[a->indices[index]];
    if (entry->kind<0 && strlen(entry->name)<sizeof(a->file)) {
        strcpy(a->file,entry->name); changed(c,FS_FILE);
    }
    return ExecAESFormFocus(c,FS_ROW+index-a->first);
}

static void filter(struct ExecAESContext *c)
{
    struct ExecAESFileSelector *a=c->form->fileSelector;
    WORD i;
    a->count=FileFilter(a->entries,a->scan.count,a->mask,a->indices);
    a->selected=NIL;
    for (i=0;i<a->count;++i)
        if (!strcmp(a->savedName,a->entries[a->indices[i]].name)) a->selected=i;
    a->first=FileFirst(a->first,a->count,a->visible);
    rows(c);
}

/* No fresh-input wait while a directory lock is live. */
static WORD events(struct ExecAESContext *c,WORD polling)
{
    struct ExecAESForm *f=c->form;
    struct ExecAESFileSelector *a=f->fileSelector;
    WORD event,proceed;
    c->intin[1]=1; c->intin[2]=1; c->intin[3]=f->down ? 0:1;
    event=polling ? ExecAESPoll(c,MU_KEYBD|MU_BUTTON|MU_MESAG,f->message):
        ExecAESEvents(c,MU_KEYBD|MU_BUTTON|MU_MESAG,0,f->message);
    if (!event) {
        if (c->diagnostic==AES_INPUT_LOST) {
            ExecAESFormCancelPress(f); f->down=1; c->diagnostic=AES_OK;
            if (!ExecAESFormPaint(c,0)) return -1;
            if (polling && (c->diagnostic=ExecAESInputArm(c,MU_KEYBD|MU_BUTTON))!=AES_OK) return -1;
            return 0;
        }
        return c->diagnostic==AES_OK ? 0:-1;
    }
    f->mx=c->intout[1]; f->my=c->intout[2]; f->buttons=c->intout[3]; f->key=c->intout[5];
    if (event&MU_MESAG) {
        proceed=ExecAESFormMessage(c);
        if (proceed!=1) {
            if (!proceed && c->diagnostic==AES_OK) a->result=0;
            return -1;
        }
    }
    return event;
}

/* Loading accepts only Cancel; all other controls are visibly inactive. */
static WORD scan_events(struct ExecAESContext *c)
{
    struct ExecAESForm *f=c->form;
    WORD event=events(c,1),hit,armed;
    if (event<0) return 0;
    if (!event) return 1;
    if (event&MU_BUTTON) {
        hit=objc_find(f->tree,0,MAX_DEPTH,f->mx,f->my);
        if (f->buttons&1) {
            f->down=1;
            if (hit==FS_CANCEL) {
                f->armed=hit; f->pressedState=f->tree[hit].ob_state;
                f->tree[hit].ob_state^=SELECTED;
            }
        } else {
            f->down=0; armed=f->armed; ExecAESFormCancelPress(f);
            if (hit==FS_CANCEL && hit==armed) { f->fileSelector->result=0; return 0; }
        }
    }
    if ((event&MU_KEYBD) && (f->key&255)==27) {
        if (f->armed!=NIL) ExecAESFormCancelPress(f);
        else { f->fileSelector->result=0; return 0; }
    }
    return ExecAESFormPaint(c,0);
}

static WORD navigate(struct ExecAESContext *c,WORD refresh)
{
    struct ExecAESForm *f=c->form;
    struct ExecAESFileSelector *a=f->fileSelector;
    WORD same,proceed=1,focus=f->focus;
    if (!FileSplit(a->path,a->requested,a->filter)) {
        status(c,"Invalid path"); return 1;
    }
    same=!strcmp(a->requested,a->directory);
    if (same && a->valid && !refresh && !strcmp(a->filter,a->mask)) return 2;
    a->savedName[0]=0;
    if (same && a->selected>=0) strcpy(a->savedName,a->entries[a->indices[a->selected]].name);
    if (same && a->valid && !refresh) {
        strcpy(a->mask,a->filter); filter(c);
        FileJoin(a->path,128,a->directory,a->mask); changed(c,FS_PATH);
        status(c,a->scan.truncated ? "First 256 only":"");
        return 2;
    }
    if (!ExecAESFormFocus(c,NIL)) return 0;
    a->loading=1; rows(c); status(c,"Loading...");
    if (!ExecAESFormPaint(c,0)) { proceed=0; goto finish; }
    remember(c);
    if (!scan_events(c)) { proceed=0; goto finish; }
    if (!FileScanBegin(&a->scan,a->requested,&a->info,a->entries)) {
        status(c,"Cannot open dir");
        if (a->scan.error==ERROR_BREAK) { c->diagnostic=AES_RESOURCE; proceed=0; }
        goto finish;
    }
    strcpy(a->directory,a->requested); strcpy(a->mask,a->filter);
    FileJoin(a->path,128,a->directory,a->mask); changed(c,FS_PATH);
    a->count=0; a->valid=0; a->selected=NIL; if (!same) a->first=0;
    rows(c);
    if (!ExecAESFormPaint(c,0)) { proceed=0; goto finish; }
    remember(c);
    do {
        if (!scan_events(c)) { proceed=0; break; }
        remember(c);
    } while (FileScanNext(&a->scan));
    if (proceed) {
        if (a->scan.error) {
            status(c,"Read failed");
            if (a->scan.error==ERROR_BREAK) { c->diagnostic=AES_RESOURCE; proceed=0; }
        } else {
            a->valid=1; filter(c); proceed=2;
            status(c,a->scan.truncated ? "First 256 only":"");
        }
    }
finish:
    FileScanEnd(&a->scan); ExecAESInputDisarm(c); a->loading=0;
    rows(c);
    if (proceed && !ExecAESFormFocus(c,eligible(a,focus) ? focus:FS_PATH)) proceed=0;
    return proceed;
}

static WORD activate(struct ExecAESContext *c,WORD hit)
{
    struct ExecAESForm *f=c->form;
    struct ExecAESFileSelector *a=f->fileSelector;
    WORD index,first;
    if (hit==FS_CANCEL) { a->result=0; return 0; }
    if (hit==FS_PATH || hit==FS_FILE) return ExecAESFormFocus(c,hit);
    if (hit==FS_UP) {
        strcpy(a->requested,a->directory); FileParent(a->requested);
        if (!FileJoin(a->path,128,a->requested,a->mask)) { status(c,"Path too long"); return 1; }
        changed(c,FS_PATH); return navigate(c,1);
    }
    if (hit==FS_REFRESH) return navigate(c,1);
    if (hit>=FS_LINE_UP && hit<=FS_PAGE_DOWN) {
        first=a->first+(hit==FS_LINE_UP ? -1:hit==FS_LINE_DOWN ? 1:
                        hit==FS_PAGE_UP ? -a->visible:a->visible);
        a->first=FileFirst(first,a->count,a->visible); rows(c);
        return ExecAESFormFocus(c,hit);
    }
    if (hit>=FS_ROW || hit==FS_OK) {
        if (hit==FS_OK) {
            index=navigate(c,0);
            if (index!=2) return index;
        }
        if (hit>=FS_ROW && !selected(c,a->first+hit-FS_ROW)) return 0;
        index=a->selected;
        if (index>=0 && a->entries[a->indices[index]].kind>0) {
            if (!FileJoin(a->requested,128,a->directory,a->entries[a->indices[index]].name) ||
                !FileJoin(a->path,128,a->requested,a->mask)) {
                status(c,"Path too long"); return 1;
            }
            changed(c,FS_PATH); return navigate(c,1);
        }
        if (hit==FS_OK) {
            /* Failed path edits retain the old view, but cannot be accepted. */
            if (!FileSplit(a->path,a->requested,a->filter) || !a->valid ||
                strcmp(a->directory,a->requested) || strcmp(a->mask,a->filter)) return 1;
            if (!FileLeaf(a->file)) { status(c,"Use 8.3 filename"); return 1; }
            a->result=1; return 0;
        }
    }
    return 1;
}

static WORD key(struct ExecAESContext *c)
{
    static const WORD order[]={FS_PATH,FS_FILE,FS_ROW,FS_UP,FS_REFRESH,
        FS_LINE_UP,FS_LINE_DOWN,FS_PAGE_UP,FS_PAGE_DOWN,FS_OK,FS_CANCEL};
    struct ExecAESForm *f=c->form;
    struct ExecAESFileSelector *a=f->fileSelector;
    WORD ch=f->key&255,i,next,step,current=f->focus>=FS_ROW ? FS_ROW:f->focus;
    if (ch==27) {
        if (f->armed!=NIL) { ExecAESFormCancelPress(f); return 1; }
        a->result=0; return 0;
    }
    if (f->armed!=NIL) return 1;
    if (ch==9 || f->key==0x0f00) {
        for (i=0;i<11 && order[i]!=current;++i) {}
        if (i==11) i=0;
        step=f->key==0x0f00 ? -1:1;
        do {
            i+=step; if (i<0) i=10; if (i>10) i=0;
            next=order[i]==FS_ROW ? (a->count ? list_focus(a):NIL):order[i];
        } while (!eligible(a,next));
        return next>=FS_ROW ? selected(c,a->first+next-FS_ROW):ExecAESFormFocus(c,next);
    }
    if (f->focus>=FS_ROW && (f->key==0x4800 || f->key==0x5000))
        return selected(c,a->selected+(f->key==0x4800 ? -1:1));
    if (ch==13) {
        if (f->focus==FS_PATH) {
            next=navigate(c,0);
            if (!next) return 0;
            if (next==2 && a->count) return selected(c,a->selected<0 ? 0:a->selected);
            return ExecAESFormFocus(c,next==2 ? FS_FILE:FS_PATH);
        }
        return activate(c,f->focus==FS_FILE || f->focus>=FS_ROW ? FS_OK:f->focus);
    }
    if (ch==' ' && f->edit==NIL) return activate(c,f->focus);
    if (f->edit!=NIL) {
        if (f->edit==FS_FILE && a->selected>=0) {
            if (a->selected>=a->first && a->selected<a->first+a->visible)
                a->tree[FS_ROW+a->selected-a->first].ob_state=0;
            a->selected=NIL;
        }
        return objc_edit(f->tree,f->edit,f->key,&f->index,ED_CHAR);
    }
    return 1;
}

static WORD run(struct ExecAESContext *c)
{
    struct ExecAESForm *f=c->form;
    struct ExecAESFileSelector *a=f->fileSelector;
    WORD event,hit,armed,proceed;
    UWORD diagnostic;
    f->running=1; f->count=FS_OBJECTS; f->focus=f->oldFocus=f->edit=f->armed=NIL; f->down=1;
    a->result=-1; rows(c); remember(c);
    if (!ExecAESFormPaint(c,1) || !navigate(c,1)) goto finish;
    if (!ExecAESFormFocus(c,a->valid ? FS_FILE:FS_PATH) || !ExecAESFormPaint(c,0)) goto finish;
    for (;;) {
        remember(c); event=events(c,0);
        if (event<0) break;
        proceed=1;
        if (event&MU_BUTTON) {
            hit=objc_find(f->tree,0,MAX_DEPTH,f->mx,f->my);
            if (f->buttons&1) {
                f->down=1;
                if (eligible(a,hit)) {
                    f->armed=hit; f->pressedState=f->tree[hit].ob_state;
                    if (!(f->tree[hit].ob_flags&EDITABLE)) f->tree[hit].ob_state^=SELECTED;
                }
            } else {
                f->down=0; armed=f->armed; ExecAESFormCancelPress(f);
                if (hit==armed && eligible(a,hit)) proceed=activate(c,hit);
            }
        }
        if (proceed && (event&MU_KEYBD)) proceed=key(c);
        if (!proceed || !ExecAESFormPaint(c,0)) break;
    }
finish:
    diagnostic=c->diagnostic; FileScanEnd(&a->scan); ExecAESInputDisarm(c);
    ExecAESFormCancelPress(f);
    if (!ExecAESFormFocus(c,NIL)) { diagnostic=c->diagnostic; a->result=-1; }
    f->running=0; c->diagnostic=diagnostic;
    return diagnostic==AES_OK && a->result>=0;
}

void ExecAESFileFree(struct ExecAESFileSelector *a)
{
    FileScanEnd(&a->scan);
    if (a->entries) FreeMem(a->entries,(ULONG)sizeof(*a->entries)*FILE_LIST_LIMIT);
    FreeMem(a,sizeof(*a));
}

WORD ExecAESFileSelect(char *path,char *file,WORD *button,const char *title)
{
    struct ExecAESContext *c=ExecAESContext();
    struct ExecAESFileSelector *a;
    GRECT r;
    WORD n,w=352,h=184,okay;
    *button=0;
    if (!c) return 0;
    if (!c->identity) { c->diagnostic=AES_IDENTITY; return 0; }
    if (c->busy || c->form || c->editTree || c->updateDepth || c->mouseDepth ||
        (c->view && c->view->handle && !c->view->shown)) { c->diagnostic=AES_BUSY; return 0; }
    for (n=0;n<128 && path[n];++n) {}
    if (n==128) { c->diagnostic=AES_MALFORMED; return 0; }
    for (n=0;n<13 && file[n];++n) {}
    if (n==13) { c->diagnostic=AES_MALFORMED; return 0; }
    if (c->view && c->view->shown) {
        w=c->view->work.right-c->view->work.left; h=c->view->work.bottom-c->view->work.top;
    }
    if (w<208 || h<128) { c->diagnostic=AES_RESOURCE; return 0; }
    a=AllocMem(sizeof(*a),MEMF_PUBLIC|MEMF_CLEAR);
    if (!a) { c->diagnostic=AES_RESOURCE; return 0; }
    a->entries=AllocMem((ULONG)sizeof(*a->entries)*FILE_LIST_LIMIT,MEMF_PUBLIC);
    if (!a->entries) { c->diagnostic=AES_RESOURCE; goto failure; }
    strcpy(a->path,path); strcpy(a->file,file); a->selected=NIL;
    if (!title) title="File selector";
    for (n=0;n<30 && title[n];++n) a->title[n]=title[n]; a->title[n]=0;
    tree(a,w,h);
    if (!form_center(a->tree,&r.g_x,&r.g_y,&r.g_w,&r.g_h) ||
        !ExecAESFormBegin(c,&r,"File selector")) goto failure;
    c->form->fileSelector=a; c->form->tree=a->tree;
    c->form->originalX=a->tree[0].ob_x; c->form->originalY=a->tree[0].ob_y;
    okay=run(c);
    /* Retain output storage until retirement succeeds. A failed FINISH keeps
     * the session attached for the existing retry/appl_exit path. */
    c->form->fileSelector=NULL;
    if (!ExecAESFormFinish(c)) { c->form->fileSelector=a; return 0; }
    if (okay) { strcpy(path,a->path); strcpy(file,a->file); *button=a->result; }
    ExecAESFileFree(a); return okay;
failure:
    ExecAESFileFree(a); return 0;
}
