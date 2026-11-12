/* SPDX-License-Identifier: MIT */
#include "terminal.h"
#include <exec816/aes.h>
#include <string.h>

static WORD copy(struct TerminalSession *);

/* Port lookup and enqueue are indivisible with controller quiescence. The root
 * withdraws this port and replies queued requests before waiting for us. */
static WORD exchange(struct Terminal *app,UBYTE operation,ULONG identity)
{
    struct MsgPort *port;
    struct ShellSessionMessage *r=&app->request;
    memset(r,0,sizeof(*r));
    r->message.mn_Node.ln_Type=NT_MESSAGE;
    r->message.mn_Length=sizeof(*r);r->message.mn_ReplyPort=app->replies;
    r->operation=operation;r->session=identity;
    if (operation==SESSION_QUERY) {
        r->payload=(void EXEC_PTR *)&app->directory;r->capacity=sizeof(app->directory);
    } else if (operation==SESSION_CREATE) {
        static UBYTE directory[SESSION_PATH_BYTES];
        directory[0]=0;r->payload=(void EXEC_PTR *)directory;r->capacity=sizeof(directory);
    }
    Forbid();port=FindPort("Shell.sessions");
    if (port) PutMsg(port,&r->message);
    Permit();
    if (!port) return 0;
    WaitPort(app->replies);
    if (GetMsg(app->replies)!=&r->message) return 0;
    return r->primary==0;
}

WORD TerminalPlatformOpen(struct Terminal *app)
{
    app->replies=CreateMsgPort();
    if (!app->replies) return 0;
    app->wake=1UL<<app->replies->mp_SigBit;
    return 1;
}

void TerminalPlatformClose(struct Terminal *app)
{
    UWORD i;
    if (app->window>0) ExecConsoleViewUnbindWindow(app->window);
    for (i=0;i<EXEC_CONSOLE_VIEW_SLOTS;++i) if (app->sessions[i].view) {
        ExecConsoleViewUnsubscribe(app->sessions[i].view);app->sessions[i].view=0;
    }
    if (app->replies) { DeleteMsgPort(app->replies);app->replies=NULL; }
    app->wake=0;

}

WORD TerminalPlatformSelect(struct Terminal *app,WORD index)
{
    struct TerminalSession *session=&app->sessions[index];
    WORD copied;
    if (!session->view || ExecConsoleViewBindWindow(session->view,app->window)) return 0;
    app->selected=index;app->dirty=1;
    copied=copy(session);
    session->damageRows=(1UL<<session->height)-1;
    return copied>=0;
}

/* Retained cells are copied only here. The GEM application owns these buffers.
 * A mixed generation may be shown, but never acknowledges an unpainted revision. */
static WORD copy(struct TerminalSession *session)
{
    struct ExecConsoleViewSnapshot packet;
    ULONG revision=0;
    UWORD first=0;
    session->coherent=1;
    do {
        UWORD status,count;
        packet.first=first;
        status=ExecConsoleViewSnapshot(session->view,&packet);
        if (status==EXEC_CONSOLE_VIEW_CLOSED) return -1;
        if (status!=EXEC_CONSOLE_VIEW_OK) { session->coherent=0;return 0; }
        if (packet.width>TERM_WIDTH || packet.height>TERM_HEIGHT) return -1;
        if (!first) revision=packet.revision;
        else if (revision!=packet.revision) session->coherent=0;
        count=packet.width*packet.height;
        if (packet.first+packet.count>count) return -1;
        if (session->column!=packet.column || session->row!=packet.row) {
            if (session->row<TERM_HEIGHT) session->damageRows|=1UL<<session->row;
            if (packet.row<TERM_HEIGHT) session->damageRows|=1UL<<packet.row;
        }
        if (memcmp(session->cells+first,packet.cells,packet.count)) {
            UWORD row;
            for (row=first/packet.width;row<=(first+packet.count-1)/packet.width;++row)
                session->damageRows|=1UL<<row;
        }
        memcpy(session->cells+first,packet.cells,packet.count);
        first+=packet.count;
        session->width=packet.width;session->height=packet.height;
        session->column=packet.column;session->row=packet.row;session->mode=packet.mode;
        session->route=packet.route;
    } while (first<session->width*session->height);
    session->revision=revision;
    return 1;
}

WORD TerminalPlatformRefresh(struct Terminal *app)
{
    UWORD i,j;
    WORD selected=-1,activated=-1;
    ULONG selection=0;
    if (!exchange(app,SESSION_QUERY,0) || ExecConsoleViewDirectory(&app->sources)) return 0;
    for (i=0;i<EXEC_CONSOLE_VIEW_SLOTS;++i) {
        struct TerminalSession *session=&app->sessions[i];
        ULONG unit=app->sources.units[i],identity=0;
        UWORD live=app->sources.live&(1U<<i);
        for (j=0;j<SESSION_CAPACITY;++j) {
            const struct ShellSessionInfo *info=&app->directory.entries[j];
            if (info->state && info->unit==unit && live) {
                identity=info->identity;
                if (info->selected) { selected=i;selection=identity; }
            }
        }
        if (session->view && (!live || session->unit!=unit)) {
            if (app->selected==i) { ExecConsoleViewUnbindWindow(app->window);app->selected=-1; }
            ExecConsoleViewUnsubscribe(session->view);memset(session,0,sizeof(*session));app->dirty=1;
        }
        if (!session->view && live) {
            session->view=ExecConsoleViewSubscribe(unit,app->wake);
            if (session->view) { session->unit=unit;app->dirty=1; }
        }
        session->identity=identity;
        if (session->view && app->selected==i && ExecConsoleViewPending(session->view)) {
            UWORD width=session->width,height=session->height,mode=session->mode;
            if (copy(session)>0) {
                if (width!=session->width || height!=session->height || mode!=session->mode) {
                    app->dirty|=1;session->damageRows=(1UL<<session->height)-1;
                }
                if (session->damageRows) app->dirty|=2;
                if (!app->dirty && session->coherent)
                    ExecConsoleViewAcknowledge(session->view,session->revision);
            }
        }
        if (live && unit==app->sources.activation) activated=i;
    }
    if (selected>=0 && (selection!=app->selection || app->selected<0))
        if (!TerminalPlatformSelect(app,selected)) return 0;
    app->selection=selection;
    if (app->activation!=app->sources.serial) {
        app->activation=app->sources.serial;
        if (activated>=0) {
            if (!TerminalPlatformSelect(app,activated)) return 0;
            wind_set(app->window,WF_TOP,0,0,0,0);
        }
    }
    return 1;
}

WORD TerminalPlatformAction(struct Terminal *app,UBYTE operation,ULONG identity)
{
    return exchange(app,operation,identity);
}

WORD TerminalPlatformWait(struct Terminal *app)
{
    struct ExecAESWaitSpec *s=&app->wait;
    memset(s,0,sizeof(*s));
    s->flags=MU_MESAG|MU_BUTTON|MU_TIMER;s->milliseconds=100;
    s->signalMask=app->wake;s->buttonClicks=1;s->buttonMask=1;s->buttonState=1;
    return ExecAESWait(s);
}
