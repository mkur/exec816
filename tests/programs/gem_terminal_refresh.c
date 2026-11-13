/* Production platform decisions and real Exec resources, controlled endpoints. */
#include "../../examples/gem-terminal/terminal.h"
#include <exec816/aes.h>
#include <string.h>
static struct Terminal app;
static struct MsgPort controller;
static UWORD controllerPresent=1;
static struct Task *consumer;
static UWORD pending,capacity,mode,race,live=1,chosen;
static ULONG units[2],revision[2]={1,1},ack[2];
UWORD TerminalRefreshChecks,TerminalQueries,TerminalDirectories,TerminalCopies,TerminalAdmissions;
#define REQUIRE(c) do { ++TerminalRefreshChecks;if (!(c)) return TerminalRefreshChecks; } while (0)

LONG EXEC_CALL TerminalRefreshServe(ULONG request)
{
    struct ShellSessionMessage *r=(struct ShellSessionMessage *)request;
    if (r->operation==SESSION_QUERY) {
        struct ShellSessionQuery *q=(struct ShellSessionQuery *)r->payload;
        UWORD i;
        ++TerminalQueries;memset(q,0,sizeof(*q));
        for (i=0;i<2;++i) if (live&(1U<<i)) {
            q->entries[i].identity=units[i]+1;q->entries[i].unit=units[i];
            q->entries[i].state=SESSION_STATE_READY;q->entries[i].selected=i==chosen;
        }
        if (race) { race=0;pending=1;Signal(consumer,app.wake); }
    }
    r->primary=0;
    return 0;
}
struct MsgPort *EXEC_CALL FindPort(CONST_STRPTR name) { return controllerPresent ? &controller:NULL; }
void EXEC_CALL PutMsg(struct MsgPort *port,struct Message *message)
{
    struct ShellSessionMessage *r=(struct ShellSessionMessage *)message;
    if (r->operation==255) controllerPresent=0;
    TerminalRefreshServe((ULONG)r);ReplyMsg(message);
}
ULONG EXEC_CALL ExecConsoleView(ULONG op,ULONG first,ULONG second)
{
    UWORD index=(UWORD)first-1;
    if (op==EXEC_CONSOLE_VIEW_OP_WATCH_DIRECTORY) { pending=1;Signal(FindTask(NULL),first);return 9; }
    if (op==EXEC_CONSOLE_VIEW_OP_TAKE_DIRECTORY) { UWORD old=pending;pending=0;return old; }
    if (op==EXEC_CONSOLE_VIEW_OP_DIRECTORY) {
        struct ExecConsoleViewDirectory *d=(struct ExecConsoleViewDirectory *)first;
        ++TerminalDirectories;memset(d,0,sizeof(*d));d->live=live;d->units[0]=units[0];d->units[1]=units[1];return 0;
    }
    if (op==EXEC_CONSOLE_VIEW_OP_SUBSCRIBE) {
        ++TerminalAdmissions;if (capacity) return 0;
        index=first==units[0] ? 0:1;ack[index]=0;return index+1;
    }
    if (op==EXEC_CONSOLE_VIEW_OP_BIND_WINDOW && mode==4) return EXEC_CONSOLE_VIEW_CLOSED;
    if (op==EXEC_CONSOLE_VIEW_OP_PENDING) return revision[index]!=ack[index];
    if (op==EXEC_CONSOLE_VIEW_OP_SNAPSHOT) {
        struct ExecConsoleViewSnapshot *p=(struct ExecConsoleViewSnapshot *)second;
        if (mode==1) return EXEC_CONSOLE_VIEW_BUSY;
        if (mode==3) return EXEC_CONSOLE_VIEW_CLOSED;
        p->width=64;p->height=20;p->column=p->row=p->mode=0;p->route=1;
        p->count=64;p->revision=revision[index]+(mode==2 && p->first>0);
        memset(p->cells,'X',64);++TerminalCopies;return 0;
    }
    if (op==EXEC_CONSOLE_VIEW_OP_ACKNOWLEDGE) ack[index]=second;
    return 0;
}
WORD wind_set(WORD handle,WORD field,WORD a,WORD b,WORD c,WORD d) { return 1; }
WORD ExecAESWait(struct ExecAESWaitSpec *s)
{
    s->received=SetSignal(0,s->signalMask)&s->signalMask;
    return s->received ? MU_EXEC : (s->flags&MU_TIMER) ? MU_TIMER:MU_MESAG;
}
static void settled(void)
{
    struct TerminalSession *s=&app.sessions[app.selected];
    ExecConsoleViewAcknowledge(s->view,s->revision);s->coherent=0;s->damageRows=0;app.dirty=0;
}
static void change(void) { pending=1;Signal(consumer,app.wake); }
LONG EXEC_CALL TerminalRefreshProbe(ULONG unused)
{
    UWORD queries,copies,admissions,i;
    ULONG before=AvailMem(0),allocated=FindTask(NULL)->tc_SigAlloc;
    consumer=FindTask(NULL);app.selected=-1;app.window=1;
    REQUIRE(TerminalPlatformOpen(&app));
    REQUIRE(TerminalPlatformRefresh(&app) && app.selected==0);
    REQUIRE(TerminalQueries==1 && TerminalDirectories==1 && !app.retry);
    settled();queries=TerminalQueries;copies=TerminalCopies;
    for (i=0;i<3;++i) REQUIRE(TerminalPlatformRefresh(&app));
    REQUIRE(TerminalQueries==queries && TerminalCopies==copies);
    TerminalPlatformWait(&app);TerminalPlatformWait(&app);
    REQUIRE(app.wait.flags==(MU_MESAG|MU_BUTTON) && !app.wait.milliseconds);
    ++revision[0];Signal(consumer,app.wake);
    REQUIRE(TerminalPlatformRefresh(&app) && TerminalCopies>copies && TerminalQueries==queries);
    settled();copies=TerminalCopies;
    ++revision[0];change();
    REQUIRE(TerminalPlatformRefresh(&app) && TerminalQueries==++queries && TerminalDirectories==queries && TerminalCopies>copies);
    settled();race=1;change();
    REQUIRE(TerminalPlatformRefresh(&app) && TerminalQueries==++queries && pending);
    REQUIRE(TerminalPlatformRefresh(&app) && TerminalQueries==++queries && !pending);
    /* New selected view cannot be admitted yet: keep its immutable identity. */
    live=3;units[1]=77;chosen=1;capacity=1;change();
    REQUIRE(TerminalPlatformRefresh(&app) && TerminalQueries==++queries);
    REQUIRE(app.retry==TERM_RETRY_SUBSCRIBE && app.selected==0 && app.selection==1);
    admissions=TerminalAdmissions;
    for (i=0;i<3;++i) {
        TerminalPlatformWait(&app);
        REQUIRE((app.wait.flags&MU_TIMER) && app.wait.milliseconds==100);
        REQUIRE(TerminalPlatformRefresh(&app) && TerminalQueries==queries);
    }
    REQUIRE(TerminalAdmissions==admissions+3);
    capacity=0;
    REQUIRE(TerminalPlatformRefresh(&app) && app.selected==1 && app.selection==78 && !app.retry);
    settled();TerminalPlatformWait(&app);
    REQUIRE(!(app.wait.flags&MU_TIMER) && TerminalQueries==queries);
    ++revision[1];mode=1;
    REQUIRE(TerminalPlatformRefresh(&app) && app.retry==TERM_RETRY_COPY);
    TerminalPlatformWait(&app);REQUIRE(app.wait.flags&MU_TIMER);
    REQUIRE(TerminalPlatformRefresh(&app) && TerminalQueries==queries);
    mode=0;REQUIRE(TerminalPlatformRefresh(&app) && !app.retry);settled();
    ++revision[1];mode=2;
    REQUIRE(TerminalPlatformRefresh(&app) && app.retry==TERM_RETRY_COPY && !app.sessions[1].coherent);
    mode=0;REQUIRE(TerminalPlatformRefresh(&app) && !app.retry);settled();
    ++revision[0];copies=TerminalCopies;
    REQUIRE(TerminalPlatformRefresh(&app) && !app.retry && TerminalCopies==copies);
    TerminalPlatformWait(&app);REQUIRE(!(app.wait.flags&MU_TIMER) && TerminalQueries==queries);
    mode=3;++revision[1];
    REQUIRE(TerminalPlatformRefresh(&app) && !app.sessions[1].view && app.selected==-1 && !app.retry && app.metadataDirty);
    live=1;chosen=0;mode=0;
    REQUIRE(TerminalPlatformRefresh(&app) && app.selected==0 && !app.retry);
    settled();live=3;units[1]=88;chosen=1;change();
    REQUIRE(TerminalPlatformRefresh(&app) && app.sessions[1].unit==88 && app.selection==89 && app.selected==1);
    settled();
    mode=4;
    REQUIRE(TerminalPlatformSelect(&app,0) && app.selected==1 && app.metadataDirty);
    mode=0;REQUIRE(TerminalPlatformRefresh(&app) && !app.retry);
    REQUIRE(TerminalPlatformAction(&app,255,0));
    REQUIRE(!TerminalPlatformRefresh(&app));
    TerminalPlatformClose(&app);
    REQUIRE(!app.replies && !app.wake && !app.directoryWatch);
    REQUIRE(AvailMem(0)==before && FindTask(NULL)->tc_SigAlloc==allocated);
    return 0;
}
int main(void) { return 0; }
