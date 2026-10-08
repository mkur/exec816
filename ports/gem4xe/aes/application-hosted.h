/* Hosted declarations for the selected GEM4XE AES code. GPL-3.0-only. */
#ifndef EXEC_APP_OBJECTS_HOSTED_H
#define EXEC_APP_OBJECTS_HOSTED_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <gem.h>
#define ob_get_par App_ob_get_par
#define ob_offset App_ob_offset
#define ob_relxywh App_ob_relxywh
#define ob_actxywh App_ob_actxywh
#define everyobj App_everyobj
#define ob_find App_ob_find
#define just_draw App_just_draw
#define ob_change App_ob_change
#define fm_button App_fm_button
#define r_set App_r_set
#define inside App_inside
#define gr_inside App_gr_inside
#define gr_box App_gr_box
#define gr_rect App_gr_rect
#define gr_crack App_gr_crack
#define expand_string App_expand_string
#define gr_just App_gr_just
#define gl_clip App_gl_clip
#define gl_wchar App_gl_wchar
#define gl_hchar App_gl_hchar
#define gsx_moff App_gsx_moff
#define gsx_mon App_gsx_mon
#define gsx_box App_gsx_box
#define gsx_attr App_gsx_attr
#define gsx_fcolor App_gsx_fcolor
#define gsx_chkclip App_gsx_chkclip
#define gsx_tblt App_gsx_tblt
#define bb_fill App_bb_fill
#define WidgetFill App_WidgetFill
#define WidgetText App_WidgetText
#define G_BOXCHAR 27
#define G_IMAGE 23
#define G_ICON 31
#define G_CICON 33
#define G_USERDEF 24
#define OUTLINED 16
#define WHITE 0
#define BLACK 1
#define IP_HOLLOW 0
#define IP_SOLID 7
#define IP_4PATT 4
#define FIS_HOLLOW 0
#define FIS_SOLID 1
#define FIS_PATTERN 2
#define MD_REPLACE 1
#define MD_TRANS 2
#define MD_XOR 3
#define IBM 3
#define INTIN_SIZE 64
#define intin AppObjectIntin
#define SPEC_PTR(spec) ((const char *)(ULONG)(spec))
typedef void (*OBJ_ROUTINE)(OBJECT *, WORD, WORD, WORD);
extern GRECT gl_clip;
extern WORD gl_wchar,gl_hchar,intin[INTIN_SIZE];
WORD ob_get_par(OBJECT *,WORD);
void ob_offset(OBJECT *,WORD,WORD *,WORD *);
void ob_relxywh(OBJECT *,WORD,GRECT *);
void ob_actxywh(OBJECT *,WORD,GRECT *);
void everyobj(OBJECT *,WORD,WORD,OBJ_ROUTINE,WORD,WORD,WORD);
WORD ob_find(OBJECT *,WORD,WORD,WORD,WORD);
void just_draw(OBJECT *,WORD,WORD,WORD);
void ob_change(OBJECT *,WORD,UWORD,WORD);
WORD fm_button(OBJECT *,WORD,WORD,WORD *);
void r_set(GRECT *,WORD,WORD,WORD,WORD);
WORD inside(WORD,WORD,const GRECT *);
void gr_inside(GRECT *,WORD);
void gr_box(WORD,WORD,WORD,WORD,WORD);
void gr_rect(WORD,WORD,const GRECT *);
void gr_crack(UWORD,WORD *,WORD *,WORD *,WORD *,WORD *);
WORD expand_string(WORD *,const char *);
WORD gr_just(WORD,WORD,const char *,WORD,WORD,GRECT *);
void gsx_moff(void);
void gsx_mon(void);
void gsx_box(const GRECT *);
void gsx_attr(WORD,WORD,WORD);
void gsx_fcolor(WORD);
WORD gsx_chkclip(const GRECT *);
void gsx_tblt(WORD,WORD,WORD,WORD);
void bb_fill(WORD,WORD,WORD,WORD,WORD,WORD,WORD);
void WidgetFill(WORD,WORD,WORD,WORD,const GRECT *);
void WidgetText(WORD,WORD,const WORD *,WORD,WORD,WORD);
#endif
