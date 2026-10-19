/* Native runtime declarations for retained legacy source; not OS emulation. */
#ifndef QED_MINTBIND_H
#define QED_MINTBIND_H
#include "qed-native.h"
LONG Malloc(LONG bytes);
LONG Mfree(void *memory);
#endif
