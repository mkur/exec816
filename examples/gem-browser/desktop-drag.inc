/* One captured gesture and one copied AES completion, owned by this Task. */
static WORD drag_status(struct Browser *b)
{
    WORD area[4];
    if (!b || !b->ready) return 1;
    if (!wind_get(b->window,WF_WORKXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3])) return 0;
    area[0]=b->work[0]+8;area[1]=b->work[1];
    area[2]=b->work[2]-16;area[3]=12;
    return redraw(b,area);
}

static WORD drag_restore(struct Desktop *d,WORD handle)
{
    struct Browser *b=desktop_folder(d,handle);
    if (!b) return 1;
    selection_status(b);
    return drag_status(b);
}

/* Logical retirement can precede a queued notification. Keep its slot until
 * that notification is consumed so a later gesture cannot inherit it. */
static WORD desktop_drag_cancel(struct Desktop *d,WORD release)
{
    struct DesktopDrag *g=&d->drag;
    struct Browser *b=desktop_folder(d,g->source);
    WORD queued=g->phase==DRAG_QUEUED || g->phase==DRAG_CANCELLED,okay=1;
    if (g->held) {
        if (!ExecAESDragOutline(0,0,0,0,0)) okay=0;
        if (!wind_update(END_MCTRL)) okay=0;
        g->held=0;
    }
    if (b) { b->armed=-1;b->down=0; }
    if (g->target && !drag_restore(d,g->target)) okay=0;
    g->source=g->target=0;g->destination[0]=0;
    g->phase=queued ? DRAG_CANCELLED:release ? DRAG_RELEASE:0;
    return okay;
}

/* Global stacking is authoritative; only then inspect this Task's content.
 * No filesystem call or focus change belongs on the hover path. */
static WORD drag_target(struct Desktop *d)
{
    struct DesktopDrag *g=&d->drag;
    struct Browser *b;
    WORD handle=wind_find(d->mx,d->my),hit=-1,target=0;
    b=desktop_folder(d,handle);g->destination[0]=0;
    if (b && handle!=g->source && !b->dialog) {
        if (!wind_get(handle,WF_WORKXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3])) return 0;
        if (d->mx>=b->work[0] && d->mx<b->work[0]+b->work[2] &&
            d->my>=b->work[1]+BROWSER_CONTENT_TOP && d->my<b->work[1]+b->work[3]-BROWSER_CONTENT_BOTTOM) {
            hit=objc_find(b->tree,0,MAX_DEPTH,d->mx,d->my);
            if (hit>=BROWSER_ROW_FIRST && hit<BROWSER_ROW_FIRST+b->visible &&
                b->first+hit-BROWSER_ROW_FIRST<b->count+b->parent) {
                hit=display_entry(b,b->first+hit-BROWSER_ROW_FIRST);
                if (hit>=0 && b->entries[hit].kind>0) {
                    if (FileJoin(g->destination,sizeof(g->destination),b->path,b->entries[hit].name)) target=handle;
                    else if (!d->down) strcpy(d->status,"Drop path is too long");
                }
            } else if (hit==0 || (hit>=BROWSER_ROW_FIRST && hit<BROWSER_STATUS)) {
                hit=-1;strcpy(g->destination,b->path);target=handle;
            }
        }
    }
    b=desktop_folder(d,g->source);
    if (target && b && job_same_directory(b->path,g->destination)) target=0;
    if (!target) g->destination[0]=0;
    if (target==g->target && hit==g->hover) return 1;
    if (g->target && !drag_restore(d,g->target)) return 0;
    g->target=target;g->hover=hit;
    b=desktop_folder(d,target);
    if (b) {
        strcpy(b->status,"Drop to copy into ");
        label(b->status+18,hit<0 ? b->path:b->entries[hit].name,63);
        if (!drag_status(b)) return 0;
    }
    return 1;
}

static WORD drag_start(struct Desktop *d)
{
    struct DesktopDrag *g=&d->drag;
    struct Browser *b=desktop_folder(d,g->source);
    OBJECT *row;
    if (!b || b->dialog || d->job) return desktop_drag_cancel(d,d->down);
    if (selected_entry(b,g->entry) && b->selectionDirectories)
        return desktop_drag_cancel(d,d->down);
    if (!selected_entry(b,g->entry) && !select_entry(b,g->entry,0)) return 0;
    b->armed=-1;b->down=0;
    g->phase=DRAG_TRACKING;
    if (d->down) {
        if (!wind_update(BEG_MCTRL)) return 0;
        g->held=1;
        row=&b->tree[BROWSER_ROW_FIRST+display_index(b,g->entry)-b->first];
        if (!ExecAESDragOutline(b->window,-8,-4,
            row->ob_width>80 ? 80:row->ob_width,row->ob_height>32 ? 32:row->ob_height) &&
            ExecAESDiagnostic()!=AES_BUSY) return 0;
    }
    return 1;
}

static WORD drag_post(struct Desktop *d)
{
    struct DesktopDrag *g=&d->drag;
    WORD words[8]={DESKTOP_DROP,d->id,0,g->target,g->source,d->mx,d->my,d->ks};
    if (!g->target) return desktop_drag_cancel(d,0);
    if (g->held) {
        if (!ExecAESDragOutline(0,0,0,0,0) || !wind_update(END_MCTRL)) return 0;
        g->held=0;
    }
    if (!drag_restore(d,g->target)) return 0;
    g->phase=DRAG_QUEUED;
    if (!appl_write(d->id,16,words)) {
        g->phase=0;
        if (!desktop_drag_cancel(d,0)) return 0;
        strcpy(d->status,"Drop not accepted: message queue full");
    }
    return 1;
}

/* Return remaining ordinary events; -1 is an operational drawing/API error. */
static WORD desktop_drag_input(struct Desktop *d,WORD events)
{
    struct DesktopDrag *g=&d->drag;
    struct Browser *b;
    WORD hit,release=(events&MU_BUTTON) && !d->down;
    if (g->phase && (events&MU_KEYBD) && (d->kr&255)==27) {
        if (!desktop_drag_cancel(d,d->down)) return -1;
        events&=~MU_KEYBD;
    }
    if (g->phase==DRAG_RELEASE) {
        if (release) g->phase=0;
        return events&~MU_BUTTON;
    }
    if (g->phase==DRAG_QUEUED || g->phase==DRAG_CANCELLED) return events&~MU_BUTTON;
    if (!g->phase) {
        if (!(events&MU_BUTTON) || !d->down || d->job) return events;
        b=desktop_folder(d,ExecAESInputWindow(MU_BUTTON));
        if (!b || b->dialog) return events;
        hit=objc_find(b->tree,0,MAX_DEPTH,d->mx,d->my);
        if (hit<BROWSER_ROW_FIRST || hit>=BROWSER_ROW_FIRST+b->visible) return events;
        hit=display_entry(b,b->first+hit-BROWSER_ROW_FIRST);
        if (hit<0 || hit>=b->count || b->entries[hit].kind>0) return events;
        g->phase=DRAG_ARMED;g->source=b->window;g->entry=hit;g->target=0;g->hover=-1;
        g->pressX=g->lastX=d->mx;g->pressY=g->lastY=d->my;
        return events;
    }
    if (!(events&(MU_BUTTON|MU_M1))) return events;
    if (g->phase==DRAG_ARMED) {
        if (d->mx>=g->pressX+4 || d->mx<=g->pressX-4 ||
            d->my>=g->pressY+4 || d->my<=g->pressY-4) {
            if (!drag_start(d)) return -1;
        } else {
            if (release) { g->phase=0;g->source=0; }
            return events;
        }
    }
    if (g->phase==DRAG_TRACKING) {
        g->lastX=d->mx;g->lastY=d->my;
        if (!drag_target(d) || (release && !drag_post(d))) return -1;
    }
    return events&~MU_BUTTON;
}

static WORD desktop_drag_deliver(struct Desktop *d)
{
    struct DesktopDrag *g=&d->drag;
    struct Browser *b;
    WORD okay=1;
    if (g->phase==DRAG_QUEUED) {
        b=desktop_folder(d,g->source);
        if (b && desktop_folder(d,g->target)) okay=desktop_copy_admit(b,g->destination,1);
    }
    g->phase=0;g->source=g->target=0;
    return okay;
}
