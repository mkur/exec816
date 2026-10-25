#include "aes-private.h"
#include <proto/exec.h>
#include <gem.h>
#include <exec816/desktop-geometry.h>
#include <exec816/console.h>

WORD EXEC_CALL ExecAESConsole(WORD window,ULONG unit)
{
    return wind_set(window,AES_WF_EXEC_CONSOLE,(WORD)(unit>>16),(WORD)unit,0,0);
}

struct AESWindowView *ExecAESFindView(struct ExecAESContext *c, WORD handle)
{
    UWORD i;
    if (c->view && c->view->handle==handle) return c->view;
    for (i=0; i<AES_WINDOWS; ++i)
        if (c->views[i] && c->views[i]->handle==handle) return c->views[i];
    return NULL;
}

const struct AESWindowView *ExecAESWindowView(WORD window)
{
    struct ExecAESContext *c=ExecAESContext();
    return c ? ExecAESFindView(c,window):NULL;
}

BOOL ExecAESWindowEpoch(struct ExecAESContext *c, WORD handle, ULONG epoch)
{
    struct AESWindowView *v=ExecAESFindView(c,handle);
    return v && epoch && v->epoch==epoch;
}

/* Invalidation may overestimate changed pixels; completion never does. */
void ExecAESChanged(struct ExecAESContext *c,LONG left,LONG top,LONG right,LONG bottom)
{
    struct AESWindowView *v=c->view;
    struct AESRect *r=&v->change;
    struct AESRequest *q=&c->request;
    UWORD i=0,covered=0;
    if (left<v->work.left) left=v->work.left;
    if (top<v->work.top) top=v->work.top;
    if (right>v->work.right) right=v->work.right;
    if (bottom>v->work.bottom) bottom=v->work.bottom;
    if (left>=right || top>=bottom) return;
    while (i<q->paintCount) {
        struct AESPaintReport *p=&q->paints[i];
        if (p->handle==v->handle && left<p->rect.right && right>p->rect.left &&
            top<p->rect.bottom && bottom>p->rect.top)
            *p=q->paints[--q->paintCount];
        else ++i;
    }
    if (v->changed&AES_CHANGE_DECLARED) for (i=0;i<q->invalidationCount;++i) {
        struct AESPaintReport *p=&q->invalidations[i];
        if (p->handle==v->handle && p->epoch==v->paintEpoch &&
            left>=p->rect.left && top>=p->rect.top && right<=p->rect.right && bottom<=p->rect.bottom) {
            covered=1;break;
        }
    }
    if (!covered) v->changed|=AES_CHANGE_UNDECLARED;
    if (!(v->changed&AES_CHANGE_RECT)) {
        r->left=left;r->top=top;r->right=right;r->bottom=bottom;v->changed|=AES_CHANGE_RECT;
    } else {
        if (left<r->left) r->left=left;
        if (top<r->top) r->top=top;
        if (right>r->right) r->right=right;
        if (bottom>r->bottom) r->bottom=bottom;
    }
}

WORD ExecAESInvalidate(WORD window,WORD x,WORD y,WORD width,WORD height)
{
    struct ExecAESContext *c=ExecAESContext();
    struct AESWindowView *v;
    struct AESPaintReport *p;
    struct AESRect *r;
    UWORD i;
    LONG left=x,top=y,right=(LONG)x+width,bottom=(LONG)y+height;
    if (!c || !(v=ExecAESFindView(c,window)) || !v->updates) return 0;
    if (width<0 || height<0) { c->diagnostic=AES_MALFORMED;return 0; }
    if (left<v->work.left) left=v->work.left;
    if (top<v->work.top) top=v->work.top;
    if (right>v->work.right) right=v->work.right;
    if (bottom>v->work.bottom) bottom=v->work.bottom;
    if (!width || !height || left>=right || top>=bottom) {
        v->changed|=AES_CHANGE_DECLARED;return 1;
    }
    if (c->request.invalidationCount==AES_INVALIDATION_REPORTS) {
        c->diagnostic=AES_OVERFLOW;return 0;
    }
    p=&c->request.invalidations[c->request.invalidationCount++];
    p->handle=window;p->epoch=v->paintEpoch;
    p->rect.left=left;p->rect.top=top;p->rect.right=right;p->rect.bottom=bottom;
    i=0;
    while (i<c->request.paintCount) {
        struct AESPaintReport *paint=&c->request.paints[i];
        if (paint->handle==window && left<paint->rect.right && right>paint->rect.left &&
            top<paint->rect.bottom && bottom>paint->rect.top)
            *paint=c->request.paints[--c->request.paintCount];
        else ++i;
    }
    r=&v->change;
    if (!(v->changed&AES_CHANGE_RECT)) {
        r->left=left;r->top=top;r->right=right;r->bottom=bottom;
    } else {
        if (left<r->left) r->left=left;
        if (top<r->top) r->top=top;
        if (right>r->right) r->right=right;
        if (bottom>r->bottom) r->bottom=bottom;
    }
    v->changed|=AES_CHANGE_DECLARED|AES_CHANGE_RECT;
    return 1;
}

/* The caller promises complete pixels inside this clip. A journal miss only
 * loses cache eligibility; it must not turn a successful GEM paint into error. */
static WORD painted(struct ExecAESContext *c,struct AESWindowView *v,
                    WORD x,WORD y,WORD width,WORD height)
{
    UWORD i;
    LONG right=(LONG)x+width,bottom=(LONG)y+height,l,t,r,b;
    if (c->request.paintFailed || c->diagnostic!=AES_OK) {
        c->request.paintFailed=1;return 0;
    }
    if (width<=0 || height<=0) return 1;
    for (i=0;i<v->visibleCount && c->request.paintCount<AES_PAINT_REPORTS;++i) {
        struct AESPaintReport *p;
        struct AESRect *a=&v->visible[i];
        l=x>a->left ? x:a->left;t=y>a->top ? y:a->top;
        r=right<a->right ? right:a->right;b=bottom<a->bottom ? bottom:a->bottom;
        if (l>=r || t>=b) continue;
        p=&c->request.paints[c->request.paintCount++];
        p->handle=v->handle;p->epoch=v->paintEpoch;
        p->rect.left=l;p->rect.top=t;p->rect.right=r;p->rect.bottom=b;
    }
    return 1;
}

WORD ExecAESPainted(WORD window,WORD x,WORD y,WORD width,WORD height)
{
    struct ExecAESContext *c=ExecAESContext();
    struct AESWindowView *v;
    if (!c || !(v=ExecAESFindView(c,window)) || !v->updates) return 0;
    return painted(c,v,x,y,width,height);
}

/* The caller finished every change. Only a complete starting image proves
 * that untouched pixels between disjoint edits are also current. */
WORD ExecAESPaintedChanges(WORD window)
{
    struct ExecAESContext *c=ExecAESContext();
    struct AESWindowView *v;
    if (!c || !(v=ExecAESFindView(c,window)) || !v->updates) return 0;
    if (!v->pixelsReady || !(v->changed&AES_CHANGE_RECT)) return 1;
    return painted(c,v,v->change.left,v->change.top,
        v->change.right-v->change.left,v->change.bottom-v->change.top);
}

WORD ExecAESDesktop(WORD handle)
{ return wind_set(handle,AES_WF_EXEC_DESKTOP,0,0,0,0); }

WORD ExecAESInputWindow(WORD event)
{
    struct ExecAESContext *c=ExecAESContext();
    return c ? (event==MU_KEYBD ? c->keyWindow:c->eventWindow) : 0;
}

WORD ExecAESWindowCall(struct ExecAESContext *c,UWORD op, WORD a, WORD b, WORD d, WORD e, WORD f, WORD g)
{
    struct AESWindowView *view;
    UWORD slot=0;
    WORD result, fail = op == AES_OP_CREATE ? -1 : 0;
    if (c == NULL) return fail;
    if (c->busy) { c->diagnostic = AES_BUSY; return fail; }
    if (c->identity == 0) { c->diagnostic = AES_IDENTITY; return fail; }
    if (op == AES_OP_CREATE) {
        while (slot<AES_WINDOWS && c->views[slot]) ++slot;
        if (slot==AES_WINDOWS) { c->diagnostic=AES_RESOURCE; return -1; }
        view=AllocMem(sizeof(*view),MEMF_PUBLIC|MEMF_CLEAR);
        if (!view) { c->diagnostic=AES_RESOURCE; return -1; }
    } else {
        view=ExecAESFindView(c,a);
        if (!view) { c->diagnostic=AES_IDENTITY; return fail; }
    }
    c->request.view=view;
    c->request.intin[0] = a; c->request.intin[1] = b;
    c->request.intin[2] = d; c->request.intin[3] = e;
    c->request.intin[4] = f; c->request.intin[5] = g;
    result=ExecAESSubmit(c,op);
    if (op==AES_OP_CREATE) {
        if (result>0) c->views[slot]=view;
        else { FreeMem(view,sizeof(*view)); c->request.view=c->view; return result; }
    }
    c->view=view;
    c->visibleIndex=0;
    return result;
}

WORD wind_create(WORD kind, WORD x, WORD y, WORD w, WORD h)
{ return ExecAESWindowCall(ExecAESContext(),AES_OP_CREATE, kind, x, y, w, h, 0); }

WORD wind_open(WORD handle, WORD x, WORD y, WORD w, WORD h)
{ return ExecAESWindowCall(ExecAESContext(),AES_OP_OPEN, handle, x, y, w, h, 0); }

WORD wind_close(WORD handle)
{ return ExecAESWindowCall(ExecAESContext(),AES_OP_CLOSE, handle, 0, 0, 0, 0, 0); }

WORD ExecAESWindowFind(struct ExecAESContext *c, WORD x, WORD y)
{
    if (!c) return 0;
    if (c->busy) { c->diagnostic = AES_BUSY; return 0; }
    c->request.intin[0]=x;c->request.intin[1]=y;
    return ExecAESSubmit(c,AES_OP_FIND);
}

WORD wind_find(WORD x, WORD y)
{ return ExecAESWindowFind(ExecAESContext(), x, y); }

WORD ExecAESDragOutline(WORD window,WORD dx,WORD dy,WORD width,WORD height)
{
    struct ExecAESContext *c = ExecAESContext();
    if (!c) return 0;
    if (c->busy) { c->diagnostic = AES_BUSY; return 0; }
    c->request.intin[0]=window;c->request.intin[1]=dx;c->request.intin[2]=dy;
    c->request.intin[3]=width;c->request.intin[4]=height;
    return ExecAESSubmit(c,AES_OP_DRAG_OUTLINE);
}

WORD ExecAESWindowDelete(struct ExecAESContext *c, WORD handle)
{
    WORD result = ExecAESWindowCall(c,AES_OP_DELETE, handle, 0, 0, 0, 0, 0);
    if (result) {
        UWORD i;
        for (i=0; i<AES_WINDOWS; ++i)
            if (c->views[i]==c->view) c->views[i]=NULL;
        FreeMem(c->view, sizeof(*c->view));
        c->view = NULL;
        for (i=0; i<AES_WINDOWS; ++i)
            if (c->views[i]) { c->view=c->views[i]; break; }
        c->request.view = c->view;
        c->visibleIndex = 0;
    }
    return result;
}

WORD wind_delete(WORD handle)
{ return ExecAESWindowDelete(ExecAESContext(), handle); }

WORD wind_set(WORD handle, WORD field, WORD w1, WORD w2, WORD w3, WORD w4)
{ return ExecAESWindowCall(ExecAESContext(),AES_OP_SET, handle, field, w1, w2, w3, w4); }

WORD wind_set_str(WORD handle, WORD field, const char *str)
{
    ULONG pointer = (ULONG)str;
    return wind_set(handle, field, (WORD)(pointer >> 16), (WORD)pointer, 0, 0);
}

WORD ExecAESWindowGet(struct ExecAESContext *c, WORD handle, WORD field, WORD *o1, WORD *o2, WORD *o3, WORD *o4)
{
    struct AESWindowView *v;
    struct AESRect *rect = NULL;
    *o1 = *o2 = *o3 = *o4 = 0;
    if (c == NULL || !ExecAESEnter(c)) return 0;
    Forbid();
    v = ExecAESFindView(c,handle);
    if (v) { c->view=v;c->request.view=v; }
    if (handle == 0 && field == WF_WXYWH) { *o2 = DESKTOP_MENU_BAR_HEIGHT; *o3 = 640; *o4 = 240-DESKTOP_MENU_BAR_HEIGHT; }
    else if (field == WF_TOP && (handle == 0 || (v != NULL && handle == v->handle)))
        *o1 = c->directory->topWindow;
    else if (v == NULL || handle <= 0 || handle != v->handle)
        c->diagnostic = AES_IDENTITY;
    else switch (field) {
    case WF_VSLIDE: *o1 = v->vslide; break;
    case WF_VSLSIZE: *o1 = v->vsize; break;
    case WF_KIND: *o1 = v->kind; break;
    case WF_WXYWH: rect = &v->work; break;
    case WF_CXYWH: rect = &v->bounds; break;
    case WF_FIRSTXYWH:
    case WF_NEXTXYWH:
        if (!v->updates) { c->diagnostic = AES_BUSY; break; }
        if (field == WF_FIRSTXYWH) {
            c->visibleIndex = 0;
            c->visibleRevision = v->revision;
        } else if (c->visibleRevision != v->revision) {
            c->diagnostic = AES_BUSY; break;
        }
        if (c->visibleIndex < v->visibleCount)
            rect = &v->visible[c->visibleIndex++];
        break;
    default: c->diagnostic = AES_UNSUPPORTED;
    }
    if (rect != NULL) {
        *o1 = rect->left; *o2 = rect->top;
        *o3 = rect->right - rect->left; *o4 = rect->bottom - rect->top;
    }
    Permit();
    c->busy = 0;
    return c->diagnostic == AES_OK;
}

WORD wind_get(WORD handle, WORD field, WORD *o1, WORD *o2, WORD *o3, WORD *o4)
{ return ExecAESWindowGet(ExecAESContext(), handle, field, o1, o2, o3, o4); }

WORD ExecAESWindowCalc(struct ExecAESContext *c, WORD type, WORD kind, WORD x, WORD y, WORD w, WORD h,
               WORD *ox, WORD *oy, WORD *ow, WORD *oh)
{
    LONG left = x, top = y, width = w, height = h;
    WORD leftInset=kind ? DESKTOP_WORK_LEFT:0;
    WORD right = kind & (UPARROW|DNARROW|VSLIDE) ? DESKTOP_FRAME_GADGET_WIDTH:DESKTOP_WORK_RIGHT;
    WORD inset = DESKTOP_WORK_TOP + (kind & INFO ? DESKTOP_FRAME_INFO_HEIGHT:0);
    WORD bottom = kind & SIZER ? DESKTOP_FRAME_GADGET_HEIGHT:DESKTOP_WORK_BOTTOM;
    *ox = *oy = *ow = *oh = 0;
    if (c == NULL) return 0;
    if (c->busy) { c->diagnostic = AES_BUSY; return 0; }
    c->diagnostic = AES_UNSUPPORTED;
    if ((kind && (kind & AES_WINDOW_KIND) != AES_WINDOW_KIND) || (kind & ~AES_WINDOW_SUPPORTED) ||
        (type != WC_BORDER && type != WC_WORK)) return 0;
    if (!kind) right=inset=bottom=0;
    if (type == WC_BORDER) { left -= leftInset; top -= inset;
        width += leftInset+right;
        height += inset+bottom; }
    else { left += leftInset; top += inset;
        width -= leftInset+right;
        height -= inset+bottom; }
    c->diagnostic = AES_MALFORMED;
    if (w <= 0 || h <= 0 || left < -32768L || left > 32767 ||
        top < -32768L || top > 32767 || width <= 0 || width > 32767 ||
        height <= 0 || height > 32767) return 0;
    *ox = (WORD)left; *oy = (WORD)top; *ow = (WORD)width; *oh = (WORD)height;
    c->diagnostic = AES_OK;
    return 1;
}

WORD wind_calc(WORD type, WORD kind, WORD x, WORD y, WORD w, WORD h,
               WORD *ox, WORD *oy, WORD *ow, WORD *oh)
{ return ExecAESWindowCalc(ExecAESContext(), type, kind, x, y, w, h, ox, oy, ow, oh); }
