/* Persistent desktop. One event loop and one bounded array of folder models. */
static WORD desktop_copy_step(struct Desktop *);
#include "settings.inc"

enum { DESK_TITLE=21,DESK_BOX=22,DESK_NEW=23,DESK_PANEL=24,DESK_CALC=25,
       DESK_TEXT=26,DESK_COUNTER=27,DESK_SAVE=28,DESK_QUIT=29,
       DESK_COPY=30,DESK_DELETE=31 };
struct Desktop GEMDesk;
static const char *desktopLabels[DESKTOP_ICONS]={"SYS:","WORK:","C:","Panel","Calculator","Text","Counter"};
static const char *desktopPrograms[4]={"C:PANEL.APP","C:CALC.APP","C:TEXT.APP","C:COUNTER.APP"};

static struct Browser *desktop_folder(struct Desktop *d,WORD handle)
{
    WORD i;
    for (i=0;i<DESKTOP_FOLDERS;++i)
        if (d->folders[i] && d->folders[i]->window==handle) return d->folders[i];
    return NULL;
}
static WORD desktop_draw(struct Desktop *d,const WORD *damage)
{
    WORD okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(d->window,WF_WORKXYWH,&d->work[0],&d->work[1],&d->work[2],&d->work[3]);
    if (okay) okay=objc_draw(d->tree,0,MAX_DEPTH,damage[0],damage[1],damage[2],damage[3]);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++d->paints;
    return okay;
}
static WORD desktop_status(struct Desktop *d)
{
    WORD area[4]={120,230,512,8};
    if (!strcmp(d->status,d->publishedStatus)) return 1;
    if (!desktop_draw(d,area)) return 0;
    strcpy(d->publishedStatus,d->status);return 1;
}
static WORD desktop_select(struct Desktop *d,WORD selected)
{
    WORD previous=d->selected,i,area[4];
    OBJECT *object;
    if (selected==previous) return 1;
    if (previous>0) d->tree[previous].ob_state=0;
    d->selected=selected;d->tree[selected].ob_state=SELECTED;
    for (i=0;i<2;++i) {
        WORD index=i ? selected:previous;
        if (index<1) continue;
        object=&d->tree[index];
        area[0]=d->tree[0].ob_x+object->ob_x;
        area[1]=d->tree[0].ob_y+object->ob_y;
        area[2]=object->ob_width;area[3]=object->ob_height;
        if (!desktop_draw(d,area)) return 0;
    }
    return 1;
}
static WORD desktop_menu(struct Desktop *d,struct Browser *b)
{
    WORD i;
    if (d->active && d->active!=b && d->active->dialog && d->active->focus==2) {
        struct Browser *old=d->active;
        wind_get(old->window,WF_WORKXYWH,&old->work[0],&old->work[1],&old->work[2],&old->work[3]);
        objc_edit(old->dialogTree,2,0,&old->editIndex,ED_END);
    }
    d->active=b;
    if (b) {
        /* The shared bar may have been changed by another folder. */
        b->menuEnabled=-1;
        wind_get(b->window,WF_WORKXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3]);
        if (b->dialog && b->focus==2) objc_edit(b->dialogTree,2,0,&b->editIndex,ED_INIT);
        return menu_state(b) && view_checks(b);
    }
    menu_ienable(d->bar,DESK_COPY,0);menu_ienable(d->bar,DESK_DELETE,0);
    for (i=MENU_OPEN;i<=MENU_RENAME;++i)
        if (!menu_ienable(d->bar,i,0)) return 0;
    for (i=MENU_ICONS;i<=MENU_NONE;++i)
        if (!menu_ienable(d->bar,i,0)) return 0;
    return 1;
}
static WORD desktop_close_folder(struct Desktop *d,struct Browser *b)
{
    WORD i;
    if (!folder_close(b)) return 0;
    for (i=0;i<DESKTOP_FOLDERS;++i) if (d->folders[i]==b) d->folders[i]=NULL;
    if (d->active==b) d->active=NULL;
    FreeMem(b,sizeof(*b));
    {
        WORD top,x,y,z;
        if (wind_get(0,WF_TOP,&top,&x,&y,&z)) d->active=desktop_folder(d,top);
    }
    return desktop_menu(d,d->active);
}
static WORD desktop_new(struct Desktop *d,const char *path)
{
    WORD i;
    struct Browser *b;
    for (i=0;i<DESKTOP_FOLDERS && d->folders[i];++i) {}
    if (i==DESKTOP_FOLDERS) { strcpy(d->status,"Three folder windows are already open");return 1; }
    b=AllocMem(sizeof(*b),MEMF_PUBLIC|MEMF_CLEAR);
    if (!b) { strcpy(d->status,"No memory for another folder");return 1; }
    b->desktop=d;b->id=d->id;
    if (!folder_open(b,d->source,d->popup,d->stock,d->bar,d->vdi,120+i*24,24+i*4,path)) {
        folder_close(b);FreeMem(b,sizeof(*b));
        strcpy(d->status,"No room for another window");return 1;
    }
    d->folders[i]=b;
    return desktop_menu(d,b);
}
static ULONG desktop_launch(struct Desktop *d,const char *name,const char *args,UWORD length)
{
    WORD i;
    ULONG child;
    for (i=0;i<DESKTOP_CHILDREN;++i) if (!d->children[i]) break;
    if (i==DESKTOP_CHILDREN) { strcpy(d->status,"Collect or close an application first");return 0; }
    child=ExecStartProgram(name,args,length);
    if (child) { d->children[i]=child;++d->launches;strcpy(d->status,"Application started"); }
    else strcpy(d->status,"Cannot launch: no Task slot or file unavailable");
    return child;
}
static WORD desktop_children(struct Desktop *d)
{
    WORD i,busy=0;
    for (i=0;i<DESKTOP_CHILDREN;++i) if (d->children[i]) {
        if (ExecCollectProgram(d->children[i],&d->result)) {
            d->children[i]=0;
            strcpy(d->status,d->result.primary ? "Application returned an error":"Application finished");
        } else busy=1;
    }
    return busy;
}
static void desktop_tree(struct Desktop *d)
{
    WORD i,kind;
    OBJECT *o;
    static const OBJECT root={-1,1,DESKTOP_ICONS+1,G_BOX,0,0,0x1178,0,16,640,224};
    static const OBJECT icon={0,-1,-1,G_ICON,0,0,0,8,0,104,32};
    d->tree[0]=root;
    for (i=0;i<DESKTOP_ICONS;++i) {
        kind=i<3 ? 1:2;
        d->icons[i]=*(ICONBLK *)d->stock[kind].ob_spec;
        d->icons[i].ib_ptext=(ULONG)desktopLabels[i];
        d->icons[i].ib_xicon=32;d->icons[i].ib_yicon=0;
        d->icons[i].ib_xtext=0;d->icons[i].ib_ytext=22;
        d->icons[i].ib_wtext=104;d->icons[i].ib_htext=8;
        o=&d->tree[i+1];
        *o=icon;
        o->ob_next=i+2;
        o->ob_flags=0;
        o->ob_spec=(ULONG)&d->icons[i];o->ob_y=i*32;
    }
    d->tree[DESKTOP_ICONS+1]=menuSource[7];
    o=&d->tree[DESKTOP_ICONS+1];o->ob_next=0;o->ob_flags=LASTOB;
    o->ob_spec=(ULONG)d->status;o->ob_x=120;o->ob_y=214;o->ob_width=512;o->ob_height=8;
}
static WORD desktop_bar(struct Desktop *d)
{
    WORD i;
    static const char *labels[]={"New Window","Control Panel","Calculator","Text","Counter","Save Settings","Quit Desktop"};
    for (i=0;i<21;++i) d->bar[i]=menuSource[i];
    d->bar[2].ob_tail=DESK_TITLE;d->bar[13].ob_next=DESK_TITLE;
    d->bar[4].ob_tail=DESK_BOX;d->bar[14].ob_next=DESK_BOX;
    d->bar[MENU_NONE].ob_flags=0;
    d->bar[DESK_TITLE]=menuSource[13];
    d->bar[DESK_TITLE].ob_spec=(ULONG)"Desk";d->bar[DESK_TITLE].ob_x=128;
    d->bar[DESK_BOX]=menuSource[5];
    d->bar[DESK_BOX].ob_next=4;d->bar[DESK_BOX].ob_head=DESK_NEW;d->bar[DESK_BOX].ob_tail=DESK_QUIT;
    d->bar[DESK_BOX].ob_x=136;d->bar[DESK_BOX].ob_width=152;
    for (i=DESK_NEW;i<=DESK_QUIT;++i) {
        d->bar[i]=menuSource[7];
        d->bar[i].ob_next=i==DESK_QUIT ? DESK_BOX:i+1;
        d->bar[i].ob_flags=0;
        d->bar[i].ob_state=0;
        d->bar[i].ob_spec=(ULONG)labels[i-DESK_NEW];
        d->bar[i].ob_y=1+(i-DESK_NEW)*16;d->bar[i].ob_width=150;
    }
    /* File > Quit closes the active folder; Desk > Quit ends this Task. */
    d->bar[MENU_QUIT].ob_spec=(ULONG)"Close Window";
    d->bar[5].ob_width=128;
    for (i=MENU_OPEN;i<=MENU_RENAME;++i) d->bar[i].ob_width=126;
    d->bar[5].ob_tail=DESK_DELETE;d->bar[5].ob_height=146;d->bar[MENU_RENAME].ob_next=DESK_COPY;
    d->bar[DESK_COPY]=menuSource[7];d->bar[DESK_COPY].ob_next=DESK_DELETE;
    d->bar[DESK_COPY].ob_spec=(ULONG)"Copy...";d->bar[DESK_COPY].ob_y=113;d->bar[DESK_COPY].ob_width=126;
    d->bar[DESK_DELETE]=d->bar[DESK_COPY];d->bar[DESK_DELETE].ob_next=5;
    d->bar[DESK_DELETE].ob_spec=(ULONG)"Delete...";d->bar[DESK_DELETE].ob_y=129;d->bar[DESK_DELETE].ob_flags=LASTOB;
    return menu_bar(d->bar,1);
}
static WORD desktop_dispatch(struct Desktop *d,struct Browser *b,WORD events)
{
    WORD result;
    if (!b) return 1;
    memcpy(b->message,d->message,sizeof(b->message));
    b->mx=d->mx;b->my=d->my;b->mb=d->mb;b->ks=d->ks;b->kr=d->kr;b->br=d->br;
    if ((events&MU_MESAG) && b->message[0]==MN_SELECTED && (b->message[4]==DESK_COPY || b->message[4]==DESK_DELETE)) {
        /* folder_event selects its own view; these commands bypass it. */
        if (!wind_get(b->window,WF_WORKXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3])) return 0;
        if (b->message[4]==DESK_COPY) result=dialog_open(b,DIALOG_COPY);
        else result=dialog_open(b,DIALOG_DELETE);
        if (!menu_tnormal(d->bar,b->message[3],1)) return 0;
        return result && menu_state(b);
    }
    result=folder_event(b,events);
    if (b==d->active) { d->defaultIcons=b->iconView;d->defaultSort=b->sortNames; }
    if (result<0) return 0;
    if (!result) return desktop_close_folder(d,b);
    return b!=d->active || menu_state(b);
}
WORD DesktopRun(void)
{
    struct Desktop *d=&GEMDesk;
    struct Browser *b;
    WORD i,cw,ch,bw,bh,events,hit,busy,result=1;
    d->window=-1;d->armed=d->selected=-1;
    d->id=appl_init();if (d->id<0) return 1;
    if (!rsrc_load("SYS:DESKTOP.RSC") || !rsrc_gaddr(R_TREE,0,(void **)&d->source) ||
        !rsrc_gaddr(R_TREE,1,(void **)&d->popup) || !rsrc_gaddr(R_TREE,2,(void **)&d->stock)) goto finish;
    d->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) d->input[i]=1;
    d->input[10]=2;v_opnvwk(d->input,&d->vdi,d->output);
    if (!d->vdi || !desktop_bar(d)) goto finish;
    d->installed=1;desktop_tree(d);
    d->window=wind_create(0,0,16,640,224);
    if (d->window<0 || !ExecAESDesktop(d->window) || !wind_open(d->window,0,16,640,224)) goto finish;
    d->opened=1;
    settings_load(d);ExecAESMouseProfile(d->mouse);
    if (!d->settingsLoaded) { if (!desktop_new(d,"SYS:")) goto finish; }
    else for (i=0;i<d->savedCount;++i) {
        struct DesktopFolder *f=&d->saved[i];
        if (!desktop_new(d,f->path)) goto finish;
        b=d->active;
        if (b) {
            b->iconView=f->icons;b->sortNames=f->sort;
            if (!wind_set(b->window,WF_CURRXYWH,f->bounds[0],f->bounds[1],f->bounds[2],f->bounds[3]) ||
                !wind_get(b->window,WF_WORKXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3]) || !refresh(b)) goto finish;
        }
    }
    if (!desktop_menu(d,d->active)) goto finish;
    d->ready=1;result=0;
    while (!d->quit) {
        busy=desktop_children(d);
        if (!desktop_status(d)) { result=2;break; }
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG|((busy || d->copy) ? MU_TIMER:0),2,1,d->down ? 0:1,
            0,0,0,0,0,0,0,0,0,0,d->message,d->copy ? 0:100,0,&d->mx,&d->my,&d->mb,&d->ks,&d->kr,&d->br);
        if (!events) {
            if (ExecAESDiagnostic()!=AES_INPUT_LOST) { result=2;break; }
            d->armed=-1;d->down=1;continue;
        }
        if (events&MU_BUTTON) {
            d->down=(d->mb&1)!=0;
            i=ExecAESInputWindow(MU_BUTTON);b=desktop_folder(d,i);
            if (b) {
                if (b!=d->active && !desktop_menu(d,b)) { result=2;break; }
                if (!desktop_dispatch(d,b,MU_BUTTON)) { result=2;break; }
            } else if (i==d->window) {
                hit=objc_find(d->tree,0,MAX_DEPTH,d->mx,d->my);
                if (d->down) { d->armed=hit;d->clicks=d->br; }
                else {
                    if (hit>0 && hit<=DESKTOP_ICONS && hit==d->armed) {
                        if (!desktop_select(d,hit)) { result=2;break; }
                        if (d->clicks==2) {
                            if (hit<=3) desktop_new(d,desktopLabels[hit-1]);
                            else desktop_launch(d,desktopPrograms[hit-4],NULL,0);
                        }
                    }
                    d->armed=-1;
                }
            }
        }
        if (events&MU_KEYBD) {
            i=ExecAESInputWindow(MU_KEYBD);b=desktop_folder(d,i);
            if (b) { if (!desktop_dispatch(d,b,MU_KEYBD)) { result=2;break; } }
            else if ((d->kr&255)==13 && d->selected>0) {
                if (d->selected<=3) desktop_new(d,desktopLabels[d->selected-1]);
                else desktop_launch(d,desktopPrograms[d->selected-4],NULL,0);
            }
        }
        if (events&MU_MESAG) {
            if (d->message[0]==MN_SELECTED && d->message[3]==DESK_TITLE) {
                i=d->message[4];
                if (i==DESK_NEW) desktop_new(d,d->active ? d->active->path:"SYS:");
                else if (i>=DESK_PANEL && i<=DESK_COUNTER) desktop_launch(d,desktopPrograms[i-DESK_PANEL],NULL,0);
                else if (i==DESK_SAVE) {
                    settings_save(d);
                } else if (i==DESK_QUIT) d->quit=1;
                if (!menu_tnormal(d->bar,DESK_TITLE,1)) { result=2;break; }
            } else if (d->message[0]==MN_SELECTED) {
                if (!desktop_dispatch(d,d->active,MU_MESAG)) { result=2;break; }
                if (!d->active) menu_tnormal(d->bar,d->message[3],1);
            } else if (d->message[3]==d->window) {
                if (d->message[0]==WM_CLOSED) d->quit=1;
                else if (d->message[0]==WM_TOPPED) {
                    if (!wind_set(d->window,WF_TOP,0,0,0,0) || !desktop_menu(d,NULL)) { result=2;break; }
                } else if (d->message[0]==WM_REDRAW && !desktop_draw(d,&d->message[4])) { result=2;break; }
            } else {
                b=desktop_folder(d,d->message[3]);
                if (b && d->message[0]==WM_TOPPED && !desktop_menu(d,b)) { result=2;break; }
                if (!desktop_dispatch(d,b,MU_MESAG)) { result=2;break; }
            }
        }
        if (d->copy && !d->quit && !desktop_copy_step(d)) { result=2;break; }
    }
finish:
    d->ready=0;
    for (i=0;i<DESKTOP_CHILDREN;++i) if (d->children[i]) ExecBreakProgram(d->children[i]);
    for (i=0;i<DESKTOP_CHILDREN;++i) if (d->children[i]) {
        if (!ExecWaitProgram(d->children[i],&d->result)) return 3;
        d->children[i]=0;
    }
    for (i=0;i<DESKTOP_FOLDERS;++i) if (d->folders[i] && !desktop_close_folder(d,d->folders[i])) result=3;
    if (d->opened && wind_close(d->window)) d->opened=0;
    if (d->window>0 && !d->opened) wind_delete(d->window);
    if (d->installed) menu_bar(d->bar,0);
    if (d->vdi) v_clsvwk(d->vdi);
    if (!appl_exit()) result=3;
    return result;
}

/* One regular-file copy, advanced between event decisions. The temporary file
 * preserves an existing destination until the user-confirmed final replacement. */
static void copy_error(struct DesktopCopy *job)
{
    if (!job->error) { job->error=IoErr();if (!job->error) job->error=ERROR_BAD_STREAM_NAME; }
}
static WORD desktop_copy_finish(struct Desktop *d,WORD cancel)
{
    struct DesktopCopy *job=d->copy;
    struct Browser *b;
    WORD okay,keep=0;
    LONG error;
    if (!job) return 1;
    b=job->owner;
    if (job->output && !Close(job->output)) copy_error(job);
    if (job->input && !Close(job->input)) copy_error(job);
    job->input=job->output=0;
    if (!cancel && !job->error) {
        if (job->replacing && !DeleteFile(job->target)) copy_error(job);
        if (!job->error && !Rename(job->temporary,job->target)) copy_error(job);
        /* A completed copy survives a failed final rename for manual recovery. */
        keep=job->error!=0;
    }
    if ((cancel || job->error) && !keep && !DeleteFile(job->temporary)) copy_error(job);
    error=job->error;d->error=error;d->copy=NULL;
    FreeMem(job,sizeof(*job));
    okay=dialog_end(b);
    if (!error && !cancel && okay) okay=refresh(b);
    if (keep) strcpy(b->status,"Complete copy kept as EXECCOPY.TMP; replace failed");
    else if (error) {
        char *p;
        strcpy(b->status,"Copy failed, DOS error ");p=b->status+22;decimal(p,(ULONG)error);
    } else strcpy(b->status,cancel ? "Copy cancelled":"Copy complete");
    return okay && redraw(b,b->work) && (!d->active || menu_state(d->active));
}
static WORD desktop_copy_start(struct Browser *b,WORD replace)
{
    struct Desktop *d=b->desktop;
    struct DesktopCopy *job;
    BPTR lock;
    LONG error=0;
    if (!d || b->selected<0 || b->entries[b->selected].kind>0) return 1;
    if (d->copy) { strcpy(b->status,"Another copy is running");return redraw(b,b->work); }
    if (!b->editText[0]) { strcpy(b->status,"Enter a full destination path");return redraw(b,b->work); }
    job=AllocMem(sizeof(*job),MEMF_PUBLIC|MEMF_CLEAR);
    if (!job) { strcpy(b->status,"No memory for copy");return redraw(b,b->work); }
    job->owner=b;
    full_name(b,b->entries[b->selected].name,job->source);strcpy(job->target,b->editText);
    strcpy(job->temporary,job->target);FileParent(job->temporary);
    /* FileJoin allows its output to be the directory input. */
    FileJoin(job->temporary,sizeof(job->temporary),job->temporary,"EXECCOPY.TMP");
    lock=Lock(job->temporary,SHARED_LOCK);
    if (lock) { UnLock(lock);error=ERROR_OBJECT_EXISTS; }
    else if (IoErr()!=ERROR_OBJECT_NOT_FOUND) error=IoErr();
    if (!error) {
        lock=Lock(job->target,SHARED_LOCK);
        if (lock) {
            if (!Examine(lock,&b->info)) error=IoErr();
            else if (b->info.fib_DirEntryType>0) error=ERROR_OBJECT_WRONG_TYPE;
            else job->replacing=1;
            UnLock(lock);
        } else if (IoErr()!=ERROR_OBJECT_NOT_FOUND) error=IoErr();
    }
    if (!error && job->replacing && !replace) {
        FreeMem(job,sizeof(*job));
        if (!objc_edit(b->dialogTree,2,0,&b->editIndex,ED_END)) return 0;
        b->dialog=0;
        return dialog_open(b,DIALOG_REPLACE);
    }
    if (!error) {
        job->input=Open(job->source,MODE_OLDFILE);
        if (!job->input) error=IoErr();
        else { job->output=Open(job->temporary,MODE_NEWFILE);if (!job->output) error=IoErr(); }
    }
    if (error) {
        if (job->input) Close(job->input);
        d->error=error;FreeMem(job,sizeof(*job));
        strcpy(b->status,error==ERROR_OBJECT_EXISTS ? "EXECCOPY.TMP already exists":
            error==ERROR_OBJECT_WRONG_TYPE ? "Destination must be a file":"Cannot start copy");
        return redraw(b,b->work) && (b->focus!=2 || objc_edit(b->dialogTree,2,0,&b->editIndex,ED_INIT));
    }
    if (b->focus==2) objc_edit(b->dialogTree,2,0,&b->editIndex,ED_END);
    d->copy=job;b->dialog=DIALOG_COPYING;b->focus=4;
    b->dialogTree[1].ob_spec=(ULONG)"Copying (Escape cancels)";
    b->dialogTree[2].ob_type=G_STRING;b->dialogTree[2].ob_flags=0;b->dialogTree[2].ob_spec=(ULONG)b->editText;
    b->dialogTree[3].ob_flags=HIDETREE;b->dialogTree[4].ob_state=SELECTED;
    strcpy(b->status,"0 bytes copied");return redraw(b,b->work);
}
static WORD desktop_copy_step(struct Desktop *d)
{
    struct DesktopCopy *job=d->copy;
    LONG count,written;
    WORD area[4];
    char *p;
    if (!job) return 1;
    count=Read(job->input,job->buffer,sizeof(job->buffer));
    if (count<0) { copy_error(job);return desktop_copy_finish(d,0); }
    if (!count) return desktop_copy_finish(d,0);
    written=Write(job->output,job->buffer,count);
    if (written!=count) { copy_error(job);return desktop_copy_finish(d,0); }
    job->copied+=(ULONG)count;
    /* Keep byte traffic separate from GUI work: update progress every 4 KiB. */
    if ((job->copied&4095)!=0) return 1;
    p=decimal(job->owner->status,job->copied);strcpy(p," bytes copied");
    area[0]=job->owner->work[0]+8;area[1]=job->owner->work[1]+job->owner->work[3]-10;
    area[2]=job->owner->work[2]-16;area[3]=8;
    return redraw(job->owner,area);
}
static WORD desktop_delete(struct Browser *b)
{
    LONG error;
    if (!dialog_end(b)) return 0;
    if (b->selected<0) return 1;
    full_name(b,b->entries[b->selected].name,b->target);
    if (DeleteFile(b->target)) return refresh(b);
    error=IoErr();b->desktop->error=error;
    strcpy(b->status,error==ERROR_DIR_NOT_EMPTY ? "Directory is not empty":
        error==ERROR_DISK_WRITE_PROTECTED || error==ERROR_WRITE_PROTECTED ? "Read-only volume":"Delete failed");
    return redraw(b,b->work);
}
static const char *desktop_association(struct Desktop *d,const char *name)
{
    WORD i,n=strlen(name),j;
    if (n<4 || name[n-4]!='.') return NULL;
    for (i=0;i<2;++i) {
        for (j=0;j<3;++j)
            if ((name[n-3+j]|32)!=(d->associations[i].extension[j]|32)) break;
        if (j==3 && d->associations[i].program[0]) return d->associations[i].program;
    }
    return NULL;
}
