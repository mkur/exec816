/* SPDX-License-Identifier: MIT */
#ifndef GEM_EDIT_H
#define GEM_EDIT_H
#include <gem/objects.h>

typedef struct XEDITINFO XEDITINFO;

/* MagiC edit event layout. Ordinary evnt_multi supplies the returned fields. */
typedef struct {
    WORD mwhich, mx, my, mbutton, kstate, key, mclicks;
    WORD reserved[9], msg[16];
} EVNT;

#define EDITERR_BUFFER_FULL (-200L)

/* Store the returned state in G_EDIT's ob_spec. The APP owns the buffer. */
XEDITINFO *edit_create(void);
/* Attach a writable NUL-terminated buffer to a closed object. Capacity includes NUL. */
void edit_set_buf(OBJECT *tree, WORD object, char *buffer, LONG capacity);
WORD edit_open(OBJECT *tree, WORD object);
void edit_close(OBJECT *tree, WORD object);
void edit_delete(XEDITINFO *edit);
WORD edit_evnt(OBJECT *tree, WORD object, WORD window, EVNT *event, LONG *error);
WORD edit_cursor(OBJECT *tree, WORD object, WORD window, WORD show);
WORD edit_get_cursor(OBJECT *tree, WORD object, char **cursor);
WORD edit_get_buf(OBJECT *tree, WORD object, char **buffer, LONG *capacity, LONG *length);
WORD edit_get_dirty(OBJECT *tree, WORD object);
void edit_set_dirty(OBJECT *tree, WORD object, WORD dirty);
void edit_get_sel(OBJECT *tree, WORD object, char **start, char **end);
#endif
