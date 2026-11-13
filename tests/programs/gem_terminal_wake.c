/* SPDX-License-Identifier: MIT */
/* Real Exec resources and production Terminal platform code. Console/AES
 * endpoints below observe teardown ordering and wait parameters only. */
#include "../../examples/gem-terminal/terminal.h"
#include <exec816/aes.h>
#include <string.h>

static struct Terminal app;
static WORD unbound,unsubscribed,orderOkay,watchFailure,unwatched;
UWORD TerminalWakeChecks;

#define REQUIRE(c) do { ++TerminalWakeChecks; if (!(c)) return TerminalWakeChecks; } while (0)

ULONG EXEC_CALL ExecConsoleView(ULONG operation,ULONG first,ULONG second)
{
    struct Task *self=FindTask(NULL);
    if (operation==EXEC_CONSOLE_VIEW_OP_WATCH_DIRECTORY) {
        if (!first || !(self->tc_SigAlloc&first)) orderOkay=0;
        return watchFailure ? 0:3;
    } else if (operation==EXEC_CONSOLE_VIEW_OP_UNWATCH_DIRECTORY) {
        if (first!=3 || !app.wake || !(self->tc_SigAlloc&app.wake)) orderOkay=0;
        unwatched=1;
    } else if (operation==EXEC_CONSOLE_VIEW_OP_UNBIND_WINDOW) {
        unbound=1;
    } else if (operation==EXEC_CONSOLE_VIEW_OP_UNSUBSCRIBE) {
        if (!unbound || !app.wake || !(self->tc_SigAlloc&app.wake)) orderOkay=0;
        ++unsubscribed;
    } else orderOkay=0;
    return 0;
}

/* This models external-mask selection, not the real AES timer/input service. */
WORD ExecAESWait(struct ExecAESWaitSpec *spec)
{
    spec->received=SetSignal(0,spec->signalMask)&spec->signalMask;
    return spec->received ? MU_EXEC:MU_TIMER;
}

LONG EXEC_CALL TerminalWakeProbe(ULONG unused)
{
    struct Task *self=FindTask(NULL);
    ULONG allocated=self->tc_SigAlloc,before=AvailMem(0),reply,wake;
    struct Message *message;
    BYTE bits[16],bit;
    UWORD count=0,i;
    memset(&app,0,sizeof(app));
    TerminalPlatformClose(&app);
    REQUIRE(self->tc_SigAlloc==allocated && AvailMem(0)==before);
    while ((bit=AllocSignal(-1))!=-1) bits[count++]=bit;
    REQUIRE(count>0 && count<=16);
    REQUIRE(!TerminalPlatformOpen(&app));
    REQUIRE(app.replies==NULL && !app.wake && AvailMem(0)==before);
    REQUIRE(self->tc_SigAlloc==0xffffffffUL);
    TerminalPlatformClose(&app);
    FreeSignal(bits[--count]);
    wake=self->tc_SigAlloc;
    REQUIRE(!TerminalPlatformOpen(&app));
    REQUIRE(app.replies==NULL && !app.wake && AvailMem(0)==before);
    REQUIRE(self->tc_SigAlloc==wake);
    TerminalPlatformClose(&app);
    for (i=0;i<count;++i) FreeSignal(bits[i]);
    REQUIRE(self->tc_SigAlloc==allocated);
    watchFailure=1;
    REQUIRE(!TerminalPlatformOpen(&app));
    REQUIRE(!app.replies && !app.wake && !app.directoryWatch);
    REQUIRE(self->tc_SigAlloc==allocated && AvailMem(0)==before);
    watchFailure=0;
    REQUIRE(TerminalPlatformOpen(&app) && app.directoryWatch==3);
    reply=1UL<<app.replies->mp_SigBit;wake=app.wake;
    REQUIRE(reply!=wake && wake==(1UL<<app.wakeBit));
    REQUIRE(self->tc_SigAlloc==(allocated|reply|wake));
    message=AllocMem(sizeof(*message),MEMF_PUBLIC|MEMF_CLEAR);
    REQUIRE(message!=NULL);
    /* The reply arrives before WaitPort: message collection leaves its bit. */
    message->mn_ReplyPort=app.replies;
    ReplyMsg(message);
    REQUIRE(WaitPort(app.replies)==message && GetMsg(app.replies)==message);
    FreeMem(message,sizeof(*message));
    REQUIRE((SetSignal(0,0)&(reply|wake))==reply);
    REQUIRE(TerminalPlatformWait(&app)==MU_TIMER);
    REQUIRE(app.wait.flags==(MU_MESAG|MU_BUTTON));
    REQUIRE(app.wait.milliseconds==0 && app.wait.signalMask==wake);
    app.retry=TERM_RETRY_SUBSCRIBE;
    REQUIRE(TerminalPlatformWait(&app)==MU_TIMER);
    REQUIRE(app.wait.flags==(MU_MESAG|MU_BUTTON|MU_TIMER) && app.wait.milliseconds==100);
    app.retry=0;
    REQUIRE(app.wait.buttonClicks==1 && app.wait.buttonMask==1 && app.wait.buttonState==1);
    REQUIRE((SetSignal(0,0)&(reply|wake))==reply);
    Signal(self,wake);
    REQUIRE(TerminalPlatformWait(&app)==(WORD)MU_EXEC && app.wait.received==wake);
    REQUIRE((SetSignal(0,0)&(reply|wake))==reply);
    Signal(self,wake);
    REQUIRE(Wait(wake)==wake && (SetSignal(0,0)&reply)==reply);
    app.window=1;app.sessions[0].view=1;app.sessions[3].view=2;
    unbound=unsubscribed=unwatched=0;orderOkay=1;
    Signal(self,wake);
    TerminalPlatformClose(&app);
    REQUIRE(orderOkay && unbound && unsubscribed==2 && unwatched && !app.directoryWatch);
    REQUIRE(app.replies==NULL && !app.wake && app.wakeBit==-1);
    REQUIRE(!app.sessions[0].view && !app.sessions[3].view);
    REQUIRE(!(SetSignal(0,0)&wake));
    REQUIRE(self->tc_SigAlloc==allocated && AvailMem(0)==before);
    app.window=-1;
    TerminalPlatformClose(&app);
    REQUIRE(self->tc_SigAlloc==allocated && AvailMem(0)==before);
    for (i=0;i<3;++i) {
        REQUIRE(TerminalPlatformOpen(&app));
        TerminalPlatformClose(&app);
        REQUIRE(self->tc_SigAlloc==allocated && AvailMem(0)==before);
    }
    return 0;
}

int main(void) { return 0; }
