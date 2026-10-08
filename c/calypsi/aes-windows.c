#include "aes-private.h"
#include <proto/exec.h>
#include <gem.h>

static WORD window_call(UWORD op, WORD a, WORD b, WORD d, WORD e, WORD f, WORD g)
{
    struct ExecAESContext *c = ExecAESContext();
    WORD fail = op == AES_OP_CREATE ? -1 : 0;
    if (c == NULL) return fail;
    if (c->busy) { c->diagnostic = AES_BUSY; return fail; }
    if (c->identity == 0) { c->diagnostic = AES_IDENTITY; return fail; }
    if (op == AES_OP_CREATE && c->view == NULL) {
        c->view = AllocMem(sizeof(*c->view), MEMF_PUBLIC | MEMF_CLEAR);
        if (c->view == NULL) { c->diagnostic = AES_RESOURCE; return -1; }
        c->request.view = c->view;
    }
    c->request.intin[0] = a; c->request.intin[1] = b;
    c->request.intin[2] = d; c->request.intin[3] = e;
    c->request.intin[4] = f; c->request.intin[5] = g;
    return ExecAESSubmit(c, op);
}

WORD wind_create(WORD kind, WORD x, WORD y, WORD w, WORD h)
{ return window_call(AES_OP_CREATE, kind, x, y, w, h, 0); }

WORD wind_open(WORD handle, WORD x, WORD y, WORD w, WORD h)
{ return window_call(AES_OP_OPEN, handle, x, y, w, h, 0); }

WORD wind_close(WORD handle)
{ return window_call(AES_OP_CLOSE, handle, 0, 0, 0, 0, 0); }

WORD wind_delete(WORD handle)
{
    WORD result = window_call(AES_OP_DELETE, handle, 0, 0, 0, 0, 0);
    if (result) {
        struct ExecAESContext *c = ExecAESContext();
        FreeMem(c->view, sizeof(*c->view));
        c->view = NULL;
        c->request.view = NULL;
        c->visibleIndex = 0;
    }
    return result;
}

WORD wind_set(WORD handle, WORD field, WORD w1, WORD w2, WORD w3, WORD w4)
{ return window_call(AES_OP_SET, handle, field, w1, w2, w3, w4); }

WORD wind_set_str(WORD handle, WORD field, const char *str)
{
    ULONG pointer = (ULONG)str;
    return wind_set(handle, field, (WORD)(pointer >> 16), (WORD)pointer, 0, 0);
}

WORD wind_get(WORD handle, WORD field, WORD *o1, WORD *o2, WORD *o3, WORD *o4)
{
    struct ExecAESContext *c = ExecAESContext();
    struct AESWindowView *v;
    struct AESRect *rect = NULL;
    *o1 = *o2 = *o3 = *o4 = 0;
    if (c == NULL || !ExecAESEnter(c)) return 0;
    Forbid();
    v = c->view;
    if (handle == 0 && field == WF_WXYWH) { *o2 = 16; *o3 = 640; *o4 = 224; }
    else if (field == WF_TOP && (handle == 0 || (v != NULL && handle == v->handle)))
        *o1 = c->directory->topWindow;
    else if (v == NULL || handle <= 0 || handle != v->handle)
        c->diagnostic = AES_IDENTITY;
    else switch (field) {
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

WORD wind_calc(WORD type, WORD kind, WORD x, WORD y, WORD w, WORD h,
               WORD *ox, WORD *oy, WORD *ow, WORD *oh)
{
    struct ExecAESContext *c = ExecAESContext();
    LONG left = x, top = y, width = w, height = h;
    *ox = *oy = *ow = *oh = 0;
    if (c == NULL) return 0;
    if (c->busy) { c->diagnostic = AES_BUSY; return 0; }
    c->diagnostic = AES_UNSUPPORTED;
    if (kind != AES_WINDOW_KIND || (type != WC_BORDER && type != WC_WORK)) return 0;
    if (type == WC_BORDER) { left -= 8; top -= 16; width += 16; height += 24; }
    else { left += 8; top += 16; width -= 16; height -= 24; }
    c->diagnostic = AES_MALFORMED;
    if (w <= 0 || h <= 0 || left < -32768L || left > 32767 ||
        top < -32768L || top > 32767 || width <= 0 || width > 32767 ||
        height <= 0 || height > 32767) return 0;
    *ox = (WORD)left; *oy = (WORD)top; *ow = (WORD)width; *oh = (WORD)height;
    c->diagnostic = AES_OK;
    return 1;
}
