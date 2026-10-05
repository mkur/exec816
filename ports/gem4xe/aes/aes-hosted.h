/* Hosted declarations for the selected GEM4XE AES code. GPL-3.0-only. */
#ifndef EXEC_AES_HOSTED_H
#define EXEC_AES_HOSTED_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <exec/widget-types.h>
#ifdef __CALYPSI_CORE_65816__
#include <exec/types.h>
#else
typedef int16_t WORD;
typedef uint16_t UWORD;
#endif
#define FAR
#pragma pack(push, 2)
#include "aes-objects.h"
#pragma pack(pop)
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
#define intin WidgetIntin
#define SPEC_PTR(spec) WidgetSpec(spec)
typedef void (*OBJ_ROUTINE)(OBJECT *, WORD, WORD, WORD);
extern GRECT gl_clip;
extern WORD gl_wchar,gl_hchar,intin[INTIN_SIZE];
const char *WidgetSpec(uint32_t offset);
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
void gsx_moff(void);
void gsx_mon(void);
void gsx_box(const GRECT *);
void gsx_attr(WORD,WORD,WORD);
void gsx_fcolor(WORD);
WORD gsx_chkclip(const GRECT *);
void gsx_tblt(WORD,WORD,WORD,WORD);
void bb_fill(WORD,WORD,WORD,WORD,WORD,WORD,WORD);
#endif
