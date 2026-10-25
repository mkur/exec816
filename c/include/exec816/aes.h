#ifndef EXEC816_AES_H
#define EXEC816_AES_H
#include <exec816/aes-wire.h>
#include <devices/timer.h>
#include <exec816/aes-wait.h>

struct ExecAESTimer {
    struct MsgPort *port;
    struct TimerClockRequest *query, *alarm;
    UBYTE state, opened;
    UWORD error;
};
struct ExecVDIWorkstation;
struct ExecAESForm;

/* Runtime hooks, separate from GEM application entry points. The startup
 * controller retains the service until every attached Task has detached. */
struct ExecAESContext {
    struct AESRequest request; /* Original binding address is also its packet. */
    struct MsgPort *service;
    struct MsgPort *replies;
    struct MsgPort *receiving;
    struct AESDelivery *records;
    struct AESDirectory *directory;
    struct AESEndpoint *endpoint;
    WORD control[5];
    WORD intin[AES_INTIN_WORDS], intout[AES_INTOUT_WORDS], words[AES_MESSAGE_WORDS];
    LONG addrin[3], addrout[1];
    UWORD diagnostic;
    UBYTE busy;
    ULONG identity, sequence;
    WORD gemId;
    struct ExecAESTimer timer;
    struct AESWindowView *view;
    UWORD visibleIndex;
    ULONG visibleRevision;
    struct ExecVDIWorkstation *workstation;
    struct ExecAESResource *resource;
    WORD deferredMessage[8];
    UBYTE messagePending;
    ULONG menuTree;
    ULONG messageEpoch, messageMenuEpoch;
    ULONG deferredEpoch, deferredMenuEpoch;
    ULONG editTree;
    WORD editObject, editIndex, editScroll;
    struct ExecAESForm *form;
    UWORD updateDepth, mouseDepth;
    ULONG repairEpoch;
    struct AESRect repair;
    WORD repairWindow;
    struct AESWindowView *views[AES_WINDOWS];
    WORD eventWindow,keyWindow;
};

BOOL ExecAESAttach(struct MsgPort *service);
BOOL ExecAESDetach(void);
struct ExecAESContext *ExecAESContext(void);
UWORD ExecAESDiagnostic(void);
/* Optional repaint completion, after drawing and before outer END_UPDATE.
 * Coordinates are screen x/y/width/height; only visible intersections count. */
WORD ExecAESBeginUpdate(WORD window);
WORD ExecAESPainted(WORD window,WORD x,WORD y,WORD width,WORD height);
WORD ExecAESPaintedChanges(WORD window);
/* Declare logical damage before drawing, independently of visible/user clips.
 * Empty dimensions explicitly declare no additional damage in this UPDATE. */
WORD ExecAESInvalidate(WORD window,WORD x,WORD y,WORD width,WORD height);
/* Borrow the owning window's read-only presentation snapshot. Fresh within
 * UPDATE, with final epoch/completeness published by END. Retired at delete. */
const struct AESWindowView *ExecAESWindowView(WORD window);
/* Session preference: AES_MOUSE_QUERY, AES_MOUSE_OFF or AES_MOUSE_MILD.
 * Returns the chosen profile, or -1 on failure. Held gestures finish first. */
WORD ExecAESMouseProfile(WORD profile);
/* Exec extensions: pinned borderless background and captured input owner. */
WORD ExecAESDesktop(WORD handle);
WORD ExecAESInputWindow(WORD event);
/* One presenter-followed outline under BEG_MCTRL; all zero arguments stop it. */
WORD ExecAESDragOutline(WORD window,WORD dx,WORD dy,WORD width,WORD height);
BOOL ExecAESPointer(const void *pointer, ULONG bytes);
#endif
