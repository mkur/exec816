/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef MGVIEW_NATIVE_H
#define MGVIEW_NATIVE_H
#include <gem.h>
#include <compat/gem-rect.h>
#include <compat/gemdos.h>
#include <exec816/aes.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#define TRUE 1
#define FALSE 0
#define SCREEN 0
#define WHITE 0
#define K_CTRL 4
#define AP_TERM 50
#define PA_EXIT 80
#define E_OK 0
#define ENSMEM GEMDOS_ENSMEM
#define EREADF -11
#define RMODE_RD 0
typedef struct {
    WORD mwhich,mx,my,mb,kstate,key,mclicks,msg[8];
} EVNT;
void open_work(void);
WORD top_whdl(void);
void form_xerr(LONG error,const char *path);
void *memchr2(const void *text,size_t length);
#endif
