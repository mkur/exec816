#include "../../c/calypsi/aes-paint-private.h"
#include <exec/types.h>
__attribute__((section("exec_layout")))
const UWORD ObjectPaintLayout[]={
    sizeof(struct ObjectPrepared),
    sizeof(struct ExecObjectPaint),
    sizeof(struct ExecEditPaint)
};
