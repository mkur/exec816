#ifndef EXEC816_AES_FORM_PRIVATE_H
#define EXEC816_AES_FORM_PRIVATE_H
#include "aes-private.h"

/* One caller-owned session. Setup arrays live here rather than on the Task
 * stack. Window/workstation ownership survives a failed cleanup for retry. */
struct ExecAESForm {
    OBJECT *tree;
    GRECT area;
    WORD originalX, originalY, window;
    UBYTE ownWindow, ownWorkstation, ready, running, ownView;
    WORD workIn[11], workOut[57];
};
#endif
