/* Caller-owned preparation storage; never shared between AES contexts. */
#ifndef EXEC_AES_PAINT_PRIVATE_H
#define EXEC_AES_PAINT_PRIVATE_H
#include <gem.h>
#include "object-prepared.h"

struct ExecEditPaint {
    OBJECT object;
    TEDINFO ted;
    char text[64];
    GRECT paper,caret;
    WORD active,paperPen,inkPen;
};
struct ExecIconPaint {
    ICONBLK icon;
    const CICON *colour;
    WORD x,y,labelX,labelY,foreground,background;
};
struct ExecObjectPaint {
    struct ObjectPrepared object;
    union {
        struct ExecEditPaint edit;
        struct ExecIconPaint icon;
    } extra;
};
struct ExecAESContext;
void ExecAESPrepareEdit(struct ExecAESContext *,OBJECT *,WORD,WORD,WORD,
                        struct ExecObjectPaint *);
void ExecAESPaintEdit(const struct ExecObjectPaint *);
#endif
