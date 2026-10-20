/* Persistent desktop. One event loop and one bounded array of folder models. */
static WORD desktop_job_step(struct Desktop *);
static WORD desktop_copy_admit(struct Browser *,const char *,WORD);
static WORD desktop_drag_cancel(struct Desktop *,WORD);
static WORD job_same_directory(const char *,const char *);
#include "settings.inc"

enum { DESK_TITLE=21,DESK_BOX=22,DESK_NEW=23,DESK_PANEL=24,DESK_CALC=25,
       DESK_TEXT=26,DESK_COUNTER=27,DESK_SAVE=28,DESK_QUIT=29,
       DESK_COPY=30,DESK_DELETE=31,DESK_ABOUT=32 };
struct Desktop GEMDesk;
static const char *desktopLabels[DESKTOP_ICONS]={"SYS:","WORK:","RAM:","C:","Panel","Calculator","Text","Counter"};
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
    if (!ExecAESBeginUpdate(d->window)) return 0;
    okay=wind_get(d->window,WF_WORKXYWH,&d->work[0],&d->work[1],&d->work[2],&d->work[3]);
    if (okay) okay=objc_draw(d->tree,0,MAX_DEPTH,damage[0],damage[1],damage[2],damage[3]);
    if (okay) okay=ExecAESPainted(d->window,damage[0],damage[1],damage[2],damage[3]);
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
    if (previous>0) {
        d->tree[previous].ob_state=0;
        d->icons[previous-1].monoblk.ib_char=0x1800;
    }
    d->selected=selected;d->tree[selected].ob_state=SELECTED;
    d->icons[selected-1].monoblk.ib_char=0x1000;
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
        wind_get(b->window,WF_WORKXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3]);
        if (b->dialog && b->focus==2) objc_edit(b->dialogTree,2,0,&b->editIndex,ED_INIT);
        return menu_state(b) && view_checks(b);
    }
    if (!menu_enable(d->bar,DESK_COPY,0) || !menu_enable(d->bar,DESK_DELETE,0)) return 0;
    for (i=MENU_OPEN;i<=MENU_RENAME;++i)
        if (!menu_enable(d->bar,i,0)) return 0;
    for (i=MENU_ICONS;i<=MENU_NONE;++i)
        if (!menu_enable(d->bar,i,0)) return 0;
    return 1;
}
static WORD desktop_close_folder(struct Desktop *d,struct Browser *b)
{
    WORD i;
    if ((d->drag.source==b->window || d->drag.target==b->window) &&
        !desktop_drag_cancel(d,d->down)) return 0;
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
    child=program_start(name,args,length);
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
    WORD i;
    OBJECT *o;
    ICONBLK *ib;
    static const OBJECT root={-1,1,DESKTOP_ICONS+1,G_BOX,0,0,0x1178,0,0,640,240};
    static const OBJECT icon={0,-1,-1,G_ICON,0,0,0,0,0,96,26};
    static const WORD kinds[DESKTOP_ICONS]={4,4,12,5,6,7,8,9};
    d->tree[0]=root;
    wind_get(0,WF_WXYWH,&d->tree[0].ob_x,&d->tree[0].ob_y,
        &d->tree[0].ob_width,&d->tree[0].ob_height);
    for (i=0;i<DESKTOP_ICONS;++i) {
        d->icons[i]=*(CICONBLK *)d->stock[kinds[i]].ob_spec;
        ib=&d->icons[i].monoblk;
        ib->ib_ptext=(ULONG)desktopLabels[i];
        ib->ib_xicon=32;ib->ib_yicon=0;
        ib->ib_wtext=strlen(desktopLabels[i])*8+8;
        ib->ib_xtext=(96-ib->ib_wtext)/2;ib->ib_ytext=18;
        ib->ib_htext=8;
        o=&d->tree[i+1];
        *o=icon;
        o->ob_type=G_CICON;
        o->ob_next=i+2;
        o->ob_flags=0;
        o->ob_spec=(ULONG)&d->icons[i];o->ob_y=i*28;
    }
    d->tree[DESKTOP_ICONS+1]=menuSource[7];
    o=&d->tree[DESKTOP_ICONS+1];o->ob_next=0;o->ob_flags=LASTOB;
    o->ob_spec=(ULONG)d->status;o->ob_x=120;o->ob_y=d->tree[0].ob_height-10;o->ob_width=512;o->ob_height=8;
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
    d->bar[DESK_BOX].ob_next=4;d->bar[DESK_BOX].ob_head=DESK_ABOUT;d->bar[DESK_BOX].ob_tail=DESK_QUIT;
    d->bar[DESK_BOX].ob_x=136;d->bar[DESK_BOX].ob_width=152;
    d->bar[DESK_BOX].ob_height=90;
    for (i=DESK_NEW;i<=DESK_QUIT;++i) {
        d->bar[i]=menuSource[7];
        d->bar[i].ob_next=i==DESK_QUIT ? DESK_BOX:i+1;
        d->bar[i].ob_flags=0;
        d->bar[i].ob_state=0;
        d->bar[i].ob_spec=(ULONG)labels[i-DESK_NEW];
        d->bar[i].ob_y=12+(i-DESK_NEW)*11;d->bar[i].ob_width=150;
    }
    /* File > Quit closes the active folder; Desk > Quit ends this Task. */
    d->bar[MENU_QUIT].ob_spec=(ULONG)"Close Window";
    d->bar[5].ob_width=160;
    for (i=MENU_OPEN;i<=MENU_RENAME;++i) d->bar[i].ob_width=158;
    d->bar[5].ob_tail=DESK_DELETE;d->bar[5].ob_height=112;d->bar[MENU_PARENT].ob_next=DESK_COPY;
    d->bar[DESK_COPY]=menuSource[7];d->bar[DESK_COPY].ob_next=DESK_DELETE;
    d->bar[DESK_COPY].ob_spec=(ULONG)"Copy...";d->bar[DESK_COPY].ob_y=89;d->bar[DESK_COPY].ob_width=158;
    d->bar[DESK_DELETE]=d->bar[DESK_COPY];d->bar[DESK_DELETE].ob_next=5;
    d->bar[DESK_DELETE].ob_spec=(ULONG)"Delete...";d->bar[DESK_DELETE].ob_y=100;d->bar[DESK_DELETE].ob_flags=0;
    d->bar[DESK_ABOUT]=menuSource[7];d->bar[DESK_ABOUT].ob_next=DESK_NEW;
    d->bar[DESK_ABOUT].ob_spec=(ULONG)"About Exec816...";d->bar[DESK_ABOUT].ob_y=1;
    d->bar[DESK_ABOUT].ob_width=150;d->bar[DESK_ABOUT].ob_flags=LASTOB;
    return menu_bar(d->bar,1);
}
#include "desktop-drag.inc"

static WORD desktop_dispatch(struct Desktop *d,struct Browser *b,WORD events)
{
    WORD result;
    if (!b) return 1;
    if (d->drag.source==b->window && d->drag.phase) {
        if (events&MU_KEYBD) return 1;
        if ((events&MU_MESAG) && d->message[0]==MN_SELECTED)
            return menu_tnormal(d->bar,d->message[3],1);
        if ((events&MU_MESAG) && d->message[0]!=WM_REDRAW && d->message[0]!=WM_CLOSED)
            return 1;
    }
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
/* A dialog keeps its snapshot and typed input until it ends. */
static WORD desktop_refresh_views(struct Desktop *d)
{
    WORD i,changed=0;
    for (i=0;i<DESKTOP_FOLDERS;++i) {
        struct Browser *b=d->folders[i];
        if (b && b->ready && b->refreshPending && !b->dialog &&
            b->window!=d->drag.source && b->window!=d->drag.target) {
            b->refreshPending=0;
            if (!refresh(b)) return 0;
            changed=1;
        }
    }
    return !changed || !d->active || menu_state(d->active);
}
WORD DesktopRun(void)
{
    struct Desktop *d=&GEMDesk;
    struct Browser *b;
    WORD i,cw,ch,bw,bh,events,hit,busy,running,about=0,result=1;
    d->window=-1;d->armed=d->selected=-1;
    d->id=appl_init();if (d->id<0) return 1;
    if (!rsrc_load("RAM:DESKTOP.RSC") || !rsrc_gaddr(R_TREE,0,(void **)&d->source) ||
        !rsrc_gaddr(R_TREE,1,(void **)&d->popup) || !rsrc_gaddr(R_TREE,2,(void **)&d->stock)) goto finish;
    d->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) d->input[i]=1;
    d->input[10]=2;v_opnvwk(d->input,&d->vdi,d->output);
    if (!d->vdi || !desktop_bar(d)) goto finish;
    d->installed=1;desktop_tree(d);
    d->window=wind_create(0,d->tree[0].ob_x,d->tree[0].ob_y,d->tree[0].ob_width,d->tree[0].ob_height);
    if (d->window<0 || !ExecAESDesktop(d->window) ||
        !wind_set(d->window,AES_WF_EXEC_PRESERVE,1,0,0,0) || !wind_open(d->window,
        d->tree[0].ob_x,d->tree[0].ob_y,d->tree[0].ob_width,d->tree[0].ob_height)) goto finish;
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
        if (!desktop_refresh_views(d)) { result=2;break; }
        busy=desktop_children(d);
        if (!desktop_status(d)) { result=2;break; }
        running=d->job && d->job->state!=JOB_REPLACE;
        hit=d->drag.phase==DRAG_ARMED ? 3:0;
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG|((busy || running || about) ? MU_TIMER:0)|
            ((d->drag.phase==DRAG_ARMED || d->drag.phase==DRAG_TRACKING) ? MU_M1:0),2,1,d->down ? 0:1,
            1,d->drag.lastX-hit,d->drag.lastY-hit,hit*2+1,hit*2+1,
            0,0,0,0,0,d->message,(running || about) ? 0:100,0,&d->mx,&d->my,&d->mb,&d->ks,&d->kr,&d->br);
        if (!events) {
            if (ExecAESDiagnostic()!=AES_INPUT_LOST) { result=2;break; }
            if (!desktop_drag_cancel(d,1)) { result=2;break; }
            d->armed=-1;d->down=1;continue;
        }
        if (events&MU_BUTTON) d->down=(d->mb&1)!=0;
        events=desktop_drag_input(d,events);
        if (events<0) { result=2;break; }
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
                            if (hit<=DESKTOP_VOLUMES) desktop_new(d,desktopLabels[hit-1]);
                            else desktop_launch(d,desktopPrograms[hit-DESKTOP_VOLUMES-1],NULL,0);
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
                if (d->selected<=DESKTOP_VOLUMES) desktop_new(d,desktopLabels[d->selected-1]);
                else desktop_launch(d,desktopPrograms[d->selected-DESKTOP_VOLUMES-1],NULL,0);
            }
        }
        if (events&MU_MESAG) {
            if (d->message[0]==DESKTOP_DROP) {
                if (!desktop_drag_deliver(d)) { result=2;break; }
            } else if (d->message[0]==MN_SELECTED && d->message[3]==DESK_TITLE) {
                i=d->message[4];
                if (!menu_tnormal(d->bar,DESK_TITLE,1)) { result=2;break; }
                if (i==DESK_ABOUT) about=1;
                else if (i==DESK_NEW) desktop_new(d,d->active ? d->active->path:"SYS:");
                else if (i>=DESK_PANEL && i<=DESK_COUNTER) desktop_launch(d,desktopPrograms[i-DESK_PANEL],NULL,0);
                else if (i==DESK_SAVE) {
                    settings_save(d);
                } else if (i==DESK_QUIT) d->quit=1;
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
                if (!desktop_dispatch(d,b,MU_MESAG)) { result=2;break; }
            }
        }
        if (about && !d->quit && !(events&MU_MESAG)) {
            /* Retire queued redraws before borrowing the active window for
             * a synchronous form. An unrelated message interrupts the form;
             * the ordinary loop must dispatch it before retrying About. */
            about=0;
            wind_get(d->active ? d->active->window:d->window,WF_WORKXYWH,&cw,&ch,&bw,&bh);
            if (!form_alert(1,"[1][Exec816 Desktop|Multitasking on the 65816|GEM4XE widgets and VDI|VBXE colour graphics][OK]")) {
                d->error=ExecAESDiagnostic();about=d->error==AES_PENDING;
                if (!about && d->error!=AES_OK) strcpy(d->status,"Cannot open About");
            }
        }
        if (d->job && !d->quit && !desktop_job_step(d)) { result=2;break; }
    }
finish:
    d->ready=0;
    if (!desktop_drag_cancel(d,0)) result=3;
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

/* One application-owned batch; DOS retains all device/transport policy. */
static void job_error(struct DesktopFileJob *job)
{
    if (!job->error) { job->error=IoErr();if (!job->error) job->error=ERROR_BAD_STREAM_NAME; }
}
static void job_close(struct DesktopFileJob *job)
{
    WORD i;
    for (i=0;i<2;++i) {
        BPTR handle=i ? job->input:job->output;
        if (handle && !Close(handle)) {
            LONG error=IoErr();if (!error) error=ERROR_BAD_STREAM_NAME;
            if (!job->cleanupError) job->cleanupError=error;
            if (!job->error) job->error=error;
        }
    }
    job->input=job->output=0;
}
static void job_summary(struct DesktopFileJob *job,WORD cancel)
{
    struct Browser *b=job->owner;
    char *p=b->status;
    const char *name=job->source,*scan;
    strcpy(p,job->operation==FILE_COPY ? "Copy ":"Delete ");p+=strlen(p);
    strcpy(p,job->error ? "failed":cancel ? "cancelled":"complete");p+=strlen(p);
    if (job->error) {
        strcpy(p," (");p=decimal(p+2,(ULONG)job->error);strcpy(p,"): ");p+=3;
        if (job->error==ERROR_DIR_NOT_EMPTY) { strcpy(p,"Folder is not empty; ");p+=21; }
        for (scan=name;*scan;++scan) if (*scan==':' || *scan=='/' || *scan=='\\') name=scan+1;
        label(p,name,24);p+=strlen(p);
    }
    strcpy(p,"; ");p=decimal(p+2,job->completed);strcpy(p," done, ");p=decimal(p+7,job->skipped);
    strcpy(p," skipped, ");p=decimal(p+10,job->total-job->completed-job->skipped);strcpy(p," left");p+=5;
    if (job->keepComplete) strcpy(p,"; complete temp kept");
    else if (job->cleanupError) { strcpy(p,"; cleanup error ");decimal(p+16,(ULONG)job->cleanupError); }
}
/* Compare entered paths without opening locks or resolving volume aliases. */
static WORD job_same_directory(const char *a,const char *b)
{
    WORD n=strlen(a),m=strlen(b),i;
    if (n && a[n-1]=='/') --n;
    if (m && b[m-1]=='/') --m;
    if (n!=m) return 0;
    for (i=0;i<n;++i) {
        char x=a[i],y=b[i];
        if (x>='a' && x<='z') x-='a'-'A';
        if (y>='a' && y<='z') y-='a'-'A';
        if (x!=y) return 0;
    }
    return 1;
}
static WORD desktop_job_finish(struct Desktop *d,WORD cancel)
{
    struct DesktopFileJob *job=d->job;
    struct Browser *b;
    WORD okay,i;
    if (!job) return 1;
    b=job->owner;job_close(job);
    if (job->temporaryOwned && !job->keepComplete) {
        if (!DeleteFile(job->temporary)) {
            job->cleanupError=IoErr();if (!job->cleanupError) job->cleanupError=ERROR_BAD_STREAM_NAME;
            if (!job->error) job->error=job->cleanupError;
        } else job->temporaryOwned=0;
    }
    d->error=job->error;d->job=NULL;
    for (i=0;i<DESKTOP_FOLDERS;++i) {
        struct Browser *view=d->folders[i];
        if (view && ((job->operation==FILE_DELETE && job_same_directory(view->path,b->path)) ||
                     (job->operation==FILE_COPY && job_same_directory(view->path,job->destination)))) view->refreshPending=1;
    }
    if (job->buffer) { FreeMem(job->buffer,COPY_BUFFER_BYTES);job->buffer=NULL; }
    okay=dialog_end(b);
    if (okay && b->ready && b->refreshPending) { b->refreshPending=0;okay=refresh(b); }
    job_summary(job,cancel);
    if (job->error) {
        char *p;
        strcpy(d->status,"File operation failed (");p=decimal(d->status+23,(ULONG)job->error);strcpy(p,")");
        if (job->keepComplete) strcpy(p+1,"; complete temp kept");
        else if (job->cleanupError) { strcpy(p+1,"; cleanup error ");decimal(p+17,(ULONG)job->cleanupError); }
        if (job->error==ERROR_DIR_NOT_EMPTY) strcpy(d->status,"Folder is not empty");
    }
    FreeMem(job,sizeof(*job));
    return okay && (!b->ready || redraw(b,b->work)) && (!d->active || menu_state(d->active));
}
static WORD job_progress(struct DesktopFileJob *job)
{
    struct Browser *b=job->owner;
    WORD area[4];
    char *p;
    if (job->operation==FILE_DELETE) {
        p=decimal(b->status,job->completed);strcpy(p," deleted, ");
        p=decimal(p+10,job->total-job->completed);strcpy(p," left");
    } else {
        p=decimal(b->status,job->completed+job->skipped+1);
        strcpy(p,"/");p=decimal(p+1,job->total);strcpy(p,"; ");
        p=decimal(p+2,job->copied);strcpy(p," bytes copied");
    }
    area[0]=b->work[0]+8;area[1]=b->work[1]+b->work[3]-10;
    area[2]=b->work[2]-16;area[3]=8;
    return redraw(b,area);
}
static WORD job_dialog(struct DesktopFileJob *job,WORD replace)
{
    struct Browser *b=job->owner;
    WORD kind=replace ? DIALOG_REPLACE:job->operation==FILE_DELETE ? DIALOG_DELETING:DIALOG_COPYING;
    WORD same=b->dialog==kind && b->dialogTree[2].ob_type==G_STRING;
    WORD area[4],i;
    if (!same) {
        for (i=0;i<7;++i) b->dialogTree[i]=dialogSource[i];
        b->dialogTree[5].ob_spec=(ULONG)b->status;
    }
    b->dialog=kind;b->focus=4;b->armed=-1;
    b->dialogTree[1].ob_spec=(ULONG)(replace ? "Replace this file?":job->operation==FILE_DELETE ? "Deleting (Escape cancels)":"Copying (Escape cancels)");
    b->dialogTree[2].ob_type=G_STRING;b->dialogTree[2].ob_flags=0;
    b->dialogTree[2].ob_spec=(ULONG)job->target;
    b->dialogTree[3].ob_flags=replace ? SELECTABLE|EXIT:HIDETREE;
    b->dialogTree[3].ob_spec=(ULONG)"Replace";b->dialogTree[3].ob_state=0;
    b->dialogTree[4].ob_flags=SELECTABLE|EXIT|DEFAULT;b->dialogTree[4].ob_state=SELECTED;
    b->dialogTree[4].ob_x=144;b->dialogTree[4].ob_width=64;
    b->dialogTree[6].ob_flags=LASTOB|(replace ? SELECTABLE|EXIT:HIDETREE);
    b->dialogTree[6].ob_state=0;
    if (!same) return sliders(b) && redraw(b,b->work);
    area[0]=b->work[0]+8;area[1]=b->work[1]+16;
    area[2]=b->work[2]-16;area[3]=16;
    return redraw(b,area);
}
static WORD job_open_copy(struct Desktop *d)
{
    struct DesktopFileJob *job=d->job;
    BPTR lock=Lock(job->temporary,SHARED_LOCK);
    if (lock) { UnLock(lock);job->error=ERROR_OBJECT_EXISTS; }
    else if (IoErr()!=ERROR_OBJECT_NOT_FOUND) job_error(job);
    if (!job->error) {
        job->input=Open(job->source,MODE_OLDFILE);
        if (!job->input) job_error(job);
        else {
            job->output=Open(job->temporary,MODE_NEWFILE);
            if (!job->output) job_error(job);
            else job->temporaryOwned=1;
        }
    }
    if (job->error) return desktop_job_finish(d,0);
    job->state=JOB_TRANSFER;
    return job_dialog(job,0) && job_progress(job);
}
static WORD desktop_job_choice(struct Desktop *d,WORD replace)
{
    struct DesktopFileJob *job=d->job;
    if (!replace) {
        job->pending[(UWORD)job->index>>3]&=~(1U<<(job->index&7));
        ++job->skipped;job->state=JOB_NEXT;
        return job_dialog(job,0);
    }
    return job_open_copy(d);
}
static WORD job_next(struct Desktop *d)
{
    struct DesktopFileJob *job=d->job;
    struct Browser *b=job->owner;
    BPTR lock;
    do { ++job->index; } while (job->index<b->count && !(job->pending[(UWORD)job->index>>3]&(1U<<(job->index&7))));
    if (job->index==b->count) return desktop_job_finish(d,0);
    if (!FileJoin(job->source,sizeof(job->source),b->path,b->entries[job->index].name)) {
        job->error=ERROR_INVALID_COMPONENT_NAME;return desktop_job_finish(d,0);
    }
    if (job->operation==FILE_DELETE) {
        strcpy(job->target,job->source);
        if (!DeleteFile(job->source)) { job_error(job);return desktop_job_finish(d,0); }
        mark_entry(b,job->index,0);
        job->pending[(UWORD)job->index>>3]&=~(1U<<(job->index&7));
        ++job->completed;
        return job_dialog(job,0) && job_progress(job);
    }
    if (job->total>1 && !FileJoin(job->target,sizeof(job->target),job->destination,b->entries[job->index].name)) {
        job->error=ERROR_INVALID_COMPONENT_NAME;return desktop_job_finish(d,0);
    }
    strcpy(job->temporary,job->target);FileParent(job->temporary);
    if (!FileJoin(job->temporary,sizeof(job->temporary),job->temporary,"EXECCOPY.TMP")) {
        job->error=ERROR_INVALID_COMPONENT_NAME;return desktop_job_finish(d,0);
    }
    if (!strcmp(job->target,job->temporary)) { job->error=ERROR_OBJECT_EXISTS;return desktop_job_finish(d,0); }
    job->replacing=0;
    lock=Lock(job->target,SHARED_LOCK);
    if (lock) {
        if (!Examine(lock,&b->info)) job_error(job);
        else if (b->info.fib_DirEntryType>0) job->error=ERROR_OBJECT_WRONG_TYPE;
        else job->replacing=1;
        UnLock(lock);
    } else if (IoErr()!=ERROR_OBJECT_NOT_FOUND) job_error(job);
    if (job->error) return desktop_job_finish(d,0);
    if (job->replacing) { job->state=JOB_REPLACE;return job_dialog(job,1); }
    return job_open_copy(d);
}
static WORD desktop_copy_start(struct Browser *b,WORD replace)
{
    struct Desktop *d=b->desktop;
    BPTR lock;
    if (replace) return desktop_job_choice(d,1);
    if (!d || b->selectionCount<1 || b->selectionDirectories || d->job) return 1;
    d->error=0;
    if (!b->editText[0]) { strcpy(b->status,"Enter a destination");return redraw(b,b->work); }
    if (b->selectionCount>1) {
        lock=Lock(b->editText,SHARED_LOCK);
        if (lock) {
            if (!Examine(lock,&b->info)) d->error=IoErr();
            else if (b->info.fib_DirEntryType<=0) d->error=ERROR_OBJECT_WRONG_TYPE;
            UnLock(lock);
        } else d->error=IoErr();
        if (d->error) { strcpy(b->status,"Destination must be a directory");return redraw(b,b->work); }
    }
    return desktop_copy_admit(b,b->editText,0);
}
/* Both entry points publish one existing job; only menu Copy has an editor. */
static WORD desktop_copy_admit(struct Browser *b,const char *destination,WORD directory)
{
    struct Desktop *d=b->desktop;
    struct DesktopFileJob *job;
    if (d->job || !b->selectionCount || b->selectionDirectories) return 1;
    d->error=0;
    job=AllocMem(sizeof(*job),MEMF_PUBLIC|MEMF_CLEAR);
    if (job) job->buffer=AllocMem(COPY_BUFFER_BYTES,MEMF_PUBLIC);
    if (!job || !job->buffer) {
        if (job) FreeMem(job,sizeof(*job));
        strcpy(b->status,"No memory for copy");return redraw(b,b->work);
    }
    job->owner=b;job->operation=FILE_COPY;job->state=JOB_NEXT;job->index=-1;
    job->total=b->selectionCount;memcpy(job->pending,b->selection,sizeof(job->pending));
    if (directory && job->total==1) {
        if (!FileJoin(job->target,sizeof(job->target),destination,b->entries[single_entry(b)].name)) {
            FreeMem(job->buffer,COPY_BUFFER_BYTES);FreeMem(job,sizeof(*job));
            strcpy(d->status,"Drop path is too long");return 1;
        }
        strcpy(job->destination,destination);
    } else if (job->total>1) strcpy(job->destination,destination);
    else { strcpy(job->target,destination);strcpy(job->destination,destination);FileParent(job->destination); }
    if (!directory && !objc_edit(b->dialogTree,2,0,&b->editIndex,ED_END)) {
        FreeMem(job->buffer,COPY_BUFFER_BYTES);FreeMem(job,sizeof(*job));return 0;
    }
    if (directory) {
        WORD i;
        for (i=0;i<7;++i) b->dialogTree[i]=dialogSource[i];
        b->dialogTree[5].ob_spec=(ULONG)b->status;
    }
    d->job=job;b->dialog=DIALOG_COPYING;b->focus=4;
    return job_next(d);
}
static WORD desktop_job_step(struct Desktop *d)
{
    struct DesktopFileJob *job=d->job;
    LONG count,written;
    if (!job || job->state==JOB_REPLACE) return 1;
    if (job->state==JOB_NEXT) return job_next(d);
    count=Read(job->input,job->buffer,COPY_BUFFER_BYTES);
    if (count<0) { job_error(job);return desktop_job_finish(d,0); }
    if (count) {
        written=Write(job->output,job->buffer,count);
        if (written!=count) { job_error(job);return desktop_job_finish(d,0); }
        job->copied+=(ULONG)count;
        return job_progress(job);
    }
    job_close(job);
    if (job->error) return desktop_job_finish(d,0);
    if (job->replacing && !DeleteFile(job->target)) job_error(job);
    if (!job->error && !Rename(job->temporary,job->target)) job_error(job);
    if (job->error) { job->keepComplete=1;return desktop_job_finish(d,0); }
    job->temporaryOwned=0;
    job->pending[(UWORD)job->index>>3]&=~(1U<<(job->index&7));
    ++job->completed;job->state=JOB_NEXT;
    return 1;
}
static WORD desktop_delete(struct Browser *b)
{
    struct DesktopFileJob *job;
    struct Desktop *d=b->desktop;
    if (d->job || !b->selectionCount) return 1;
    job=AllocMem(sizeof(*job),MEMF_PUBLIC|MEMF_CLEAR);
    if (!job) { strcpy(b->status,"No memory for delete");return redraw(b,b->work); }
    job->owner=b;job->operation=FILE_DELETE;job->state=JOB_NEXT;job->index=-1;
    job->total=b->selectionCount;memcpy(job->pending,b->selection,sizeof(job->pending));
    d->job=job;d->error=0;
    return job_dialog(job,0);
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
