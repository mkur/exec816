/* SPDX-License-Identifier: MIT */
#ifndef GEM_OBJECTS_H
#define GEM_OBJECTS_H
#pragma pack(push, 2)
typedef struct { WORD g_x,g_y,g_w,g_h; } GRECT;
typedef struct {
    WORD ob_next,ob_head,ob_tail;
    UWORD ob_type,ob_flags,ob_state;
    ULONG ob_spec;
    WORD ob_x,ob_y,ob_width,ob_height;
} OBJECT;
typedef struct {
    ULONG te_ptext,te_ptmplt,te_pvalid;
    WORD te_font,te_fontid,te_just,te_color,te_fontsize,te_thickness;
    WORD te_txtlen,te_tmplen;
} TEDINFO;
#pragma pack(pop)
#define G_BOX 20
#define G_TEXT 21
#define G_BOXTEXT 22
#define TE_LEFT 0
#define TE_RIGHT 1
#define TE_CNTR 2
#define IBM 3
#define G_IBOX 25
#define G_BUTTON 26
#define G_STRING 28
#define G_TITLE 32
#define SELECTABLE 1
#define DEFAULT 2
#define EXIT 4
#define RBUTTON 16
#define LASTOB 32
#define HIDETREE 128
#define NORMAL 0
#define SELECTED 1
#define DISABLED 8
#define ROOT 0
#define NIL (-1)
#define MAX_DEPTH 8
#define GEM_OBJECT_LIMIT 32
WORD objc_draw(OBJECT *,WORD,WORD,WORD,WORD,WORD,WORD);
WORD objc_find(OBJECT *,WORD,WORD,WORD,WORD);
WORD objc_offset(OBJECT *,WORD,WORD *,WORD *);
WORD objc_change(OBJECT *,WORD,WORD,WORD,WORD,WORD,WORD,WORD,WORD);
WORD form_center(OBJECT *,WORD *,WORD *,WORD *,WORD *);
/* Windowed subset: commit an accepted activation, no input wait or drawing. */
WORD form_button(OBJECT *,WORD,WORD,WORD *);
WORD form_keybd(OBJECT *,WORD,WORD,WORD,WORD *,WORD *);
#define R_TREE 0
WORD rsrc_load(const char *);
WORD rsrc_free(void);
WORD rsrc_gaddr(WORD,WORD,void **);
WORD rsrc_obfix(OBJECT *,WORD);
typedef struct {
    LONG mn_tree; /* GEM4XE 32-bit address representation. */
    WORD mn_menu,mn_item,mn_scroll,mn_keystate;
} MENU;
WORD menu_bar(OBJECT *,WORD);
WORD menu_popup(const MENU *,WORD,WORD,MENU *);
WORD menu_ienable(OBJECT *,WORD,WORD);
WORD menu_tnormal(OBJECT *,WORD,WORD);
WORD menu_text(OBJECT *,WORD,const char *);
#endif
