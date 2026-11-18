/* SPDX-License-Identifier: MIT */
#ifndef GEM_EDIT_H
#define GEM_EDIT_H
#include <gem/objects.h>

typedef struct XEDITINFO XEDITINFO;

/* Store the returned state in G_EDIT's ob_spec. The APP owns the buffer. */
XEDITINFO *edit_create(void);
/* Attach a writable NUL-terminated buffer to a closed object. Capacity includes NUL. */
void edit_set_buf(OBJECT *tree, WORD object, char *buffer, LONG capacity);
WORD edit_open(OBJECT *tree, WORD object);
void edit_close(OBJECT *tree, WORD object);
void edit_delete(XEDITINFO *edit);
#endif
