#ifndef UI_EVENTS_H
#define UI_EVENTS_H
#include <exec/input.h>
#define UI_EVENT_CAPACITY 32
void UiEventsOpen(void);
void UiEventsClose(void);
UWORD UiPostCaptured(const struct InputEvent *event);
UWORD UiPostPointer(const struct InputEvent *event);
UWORD UiTakeEvent(struct InputEvent *event);
UWORD UiEventsPending(void);
extern volatile UWORD uiQueued, uiLoss, uiCancel, uiOverflow, uiCoalesced;
#endif
