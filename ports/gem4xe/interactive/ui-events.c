/* Application-owned normalized queue. Task producers publish under Forbid;
 * interrupts retain raw records in INPUT and never traverse this queue. */
#include "ui.h"
#include "ui-events.h"
#include <string.h>
extern struct InputLease input, mouseInput;
static ULONG mouseAcquisition, mouseRoute, mouseSession;
static struct InputEvent events[UI_EVENT_CAPACITY] __attribute__((aligned(2)));
static struct InputEvent lossEvent, cancelEvent;
static UWORD head, tail, closed=1;
volatile UWORD uiQueued, uiLoss, uiCancel, uiOverflow, uiCoalesced;

void UiEventsOpen(void)
{
    Forbid();
    head=tail=uiQueued=uiLoss=uiCancel=0;
    closed=0;
    Permit();
}
void UiEventsClose(void)
{
    Forbid();
    closed=1;
    mouseAcquisition=mouseRoute=mouseSession=0;
    head=tail=uiQueued=uiLoss=uiCancel=0;
    Permit();
}
static UWORD current(const struct InputEvent *e)
{
    return !closed && input.state==INPUT_ACTIVE && input.route &&
           e->acquisition==input.acquisition && e->route==input.route;
}
/* Caller holds Forbid across identity validation and publication. */
static UWORD publish(const struct InputEvent *e)
{
    UWORD result=INPUT_OK, last=(head+UI_EVENT_CAPACITY-1)&(UI_EVENT_CAPACITY-1);
    if (e->kind==INPUT_EVENT_CANCEL) {
        memcpy(&cancelEvent,e,sizeof(*e)); uiCancel=1;
    } else if (e->kind==INPUT_EVENT_LOSS) {
        memcpy(&lossEvent,e,sizeof(*e)); uiLoss=1;
        head=tail=uiQueued=0;
    } else if (uiQueued && e->kind==INPUT_EVENT_POINTER &&
               events[last].kind==INPUT_EVENT_POINTER && events[last].acquisition==e->acquisition &&
               events[last].route==e->route && events[last].buttons==e->buttons &&
               events[last].qualifiers==e->qualifiers && events[last].flags==e->flags) {
        UWORD firstTick=events[last].tick;
        memcpy(&events[last],e,sizeof(*e));
        events[last].tick=firstTick; ++uiCoalesced;
    } else if (uiQueued==UI_EVENT_CAPACITY) {
        memset(&lossEvent,0,sizeof(lossEvent));
        lossEvent.acquisition=e->acquisition; lossEvent.route=e->route;
        lossEvent.kind=INPUT_EVENT_LOSS; lossEvent.code=INPUT_LOSS_NORMALIZED;
        lossEvent.flags=e->flags&INPUT_INJECTED;
        head=tail=uiQueued=0; uiLoss=1; ++uiOverflow;
        result=INPUT_EXHAUSTED;
    } else {
        memcpy(&events[head],e,sizeof(*e));
        head=(head+1)&(UI_EVENT_CAPACITY-1); ++uiQueued;
    }
    Signal(input.owner.task,input.wakeMask);
    return result;
}
/* Record the complete source identity before canonicalizing into the GUI's
 * existing keyboard/session queue. Late samples cannot borrow a new session. */
UWORD UiMouseOpen(void)
{
    UWORD status=INPUT_INVALID_OWNER;
    Forbid();
    if (!closed && boot.session && input.state==INPUT_ACTIVE && input.route &&
        mouseInput.state==INPUT_ACTIVE && mouseInput.route &&
        mouseInput.owner.task==input.owner.task) {
        UiMouseClose();
        mouseAcquisition=mouseInput.acquisition;
        mouseRoute=mouseInput.route;
        mouseSession=boot.session;
        status=INPUT_OK;
    }
    Permit();
    return status;
}
void UiMouseClose(void)
{
    UWORD n, kept=0, index, destination;
    Forbid();
    mouseAcquisition=mouseRoute=mouseSession=0;
    UiDisarmPointer();
    /* Remove old normalized pointer records too. Keyboard records and durable
     * cancel/loss notices survive this bounded Task-only queue walk. */
    for (n=0;n<uiQueued;++n) {
        index=(tail+n)&(UI_EVENT_CAPACITY-1);
        if (events[index].kind==INPUT_EVENT_POINTER || events[index].kind==INPUT_EVENT_BUTTON) continue;
        destination=(tail+kept)&(UI_EVENT_CAPACITY-1);
        if (destination!=index) memcpy(&events[destination],&events[index],sizeof(events[index]));
        ++kept;
    }
    uiQueued=kept; head=(tail+kept)&(UI_EVENT_CAPACITY-1);
    Permit();
}
UWORD UiPostMouse(const struct InputEvent *e)
{
    struct InputEvent copy;
    UWORD status=INPUT_INVALID_OWNER;
    if (!GemUpperExtent(e,sizeof(*e)) || e->reserved || e->qualifiers ||
        (e->flags&~INPUT_TICK_VALID) || (!(e->flags&INPUT_TICK_VALID) && e->tick) ||
        e->x<0 || e->x>639 || e->y<0 || e->y>239 || (e->buttons&~INPUT_LEFT) ||
        (e->kind==INPUT_EVENT_POINTER ? e->code!=0 :
         e->kind==INPUT_EVENT_BUTTON ? e->code!=INPUT_LEFT :
         e->kind==INPUT_EVENT_LOSS ? (e->code<INPUT_LOSS_RAW || e->code>INPUT_LOSS_HARDWARE || e->flags || e->tick) : 1))
        return INPUT_BAD_ARGUMENT;
    Forbid();
    if (mouseSession && (mouseSession!=boot.session || mouseInput.state!=INPUT_ACTIVE ||
        mouseInput.acquisition!=mouseAcquisition || mouseInput.route!=mouseRoute)) UiMouseClose();
    if (!closed && mouseSession && mouseSession==boot.session &&
        mouseInput.state==INPUT_ACTIVE && mouseInput.acquisition==mouseAcquisition &&
        mouseInput.route==mouseRoute && e->acquisition==mouseAcquisition && e->route==mouseRoute &&
        input.state==INPUT_ACTIVE && input.route) {
        memcpy(&copy,e,sizeof(copy));
        copy.acquisition=input.acquisition; copy.route=input.route;
        status=publish(&copy);
    }
    Permit();
    return status;
}
UWORD UiPostCaptured(const struct InputEvent *e)
{
    UWORD status;
    Forbid();
    status=current(e) ? publish(e) : INPUT_INVALID_OWNER;
    Permit();
    return status;
}
UWORD UiPostPointer(const struct InputEvent *e)
{
    UWORD status;
    if (!GemUpperExtent(e,sizeof(*e)) || e->reserved ||
        (e->flags&~(INPUT_TICK_VALID|INPUT_INJECTED)) || (!(e->flags&INPUT_TICK_VALID) && e->tick) || (e->qualifiers&~3) ||
        e->x<0 || e->x>639 || e->y<0 || e->y>239 || (e->buttons&~INPUT_LEFT) ||
        (e->kind!=INPUT_EVENT_POINTER && e->kind!=INPUT_EVENT_BUTTON) ||
        (e->kind==INPUT_EVENT_POINTER ? e->code!=0 : e->code!=INPUT_LEFT)) return INPUT_BAD_ARGUMENT;
    Forbid();
    status=current(e) ? publish(e) : INPUT_INVALID_OWNER;
    Permit();
    return status;
}
UWORD UiTakeEvent(struct InputEvent *e)
{
    UWORD status=INPUT_OK;
    Forbid();
    if (uiCancel) { memcpy(e,&cancelEvent,sizeof(*e)); uiCancel=0; }
    else if (uiLoss) { memcpy(e,&lossEvent,sizeof(*e)); uiLoss=0; }
    else if (uiQueued) {
        memcpy(e,&events[tail],sizeof(*e));
        tail=(tail+1)&(UI_EVENT_CAPACITY-1); --uiQueued;
    } else status=INPUT_EMPTY;
    Permit();
    return status;
}
UWORD UiEventsPending(void) { return uiCancel || uiLoss || uiQueued; }
