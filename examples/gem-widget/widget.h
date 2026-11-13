/* SPDX-License-Identifier: MIT */
#ifndef GEM_WIDGET_H
#define GEM_WIDGET_H
#include <gem.h>
#include <stdint.h>

enum { WIDGET_ROOT, WIDGET_LABEL, WIDGET_BUTTON, WIDGET_HELP, WIDGET_OBJECTS };
/* Static application storage on both targets; GEM calls keep the Task stack
 * for call depth. Observation reads these fields outside application drawing. */
struct Widget {
    WORD id,window,opened;
    volatile WORD ready;
    volatile uint32_t actions,paints;
    WORD message[8],work[4];
    OBJECT tree[WIDGET_OBJECTS];
    char label[16];
    WORD vdi,input[11],output[57];
};
WORD WidgetRun(struct Widget *app);
#endif
