/* SPDX-License-Identifier: MIT
 * Source adapters for the native QED port; public GEM records stay unchanged.
 */
#ifndef QED_NATIVE_H
#define QED_NATIVE_H
#include <gem.h>
#include <proto/exec.h>

#ifndef _WORD
#define _WORD short
#define _UWORD unsigned short
#endif
#define QED_NEAR
#ifndef __CDECL
#define __CDECL
#endif
/* Port-local legacy raster descriptor; no public raster operation is exposed. */
typedef struct {
    void *fd_addr;
    WORD fd_w,fd_h,fd_wdwidth,fd_stand,fd_nplanes,fd_r1,fd_r2,fd_r3;
} MFDB;
#include "qed-gem-extra.h"
#include <support.h>
#define WF_HSLSIZE 15
WORD objc_change_grect(OBJECT *,WORD,WORD,const GRECT *,WORD,WORD);

/* gemlib supplies one long timer argument; Exec's public call uses two words. */
static WORD QedEvntMulti(WORD flags, WORD clicks, WORD mask, WORD state,
    WORD m1f, WORD m1x, WORD m1y, WORD m1w, WORD m1h,
    WORD m2f, WORD m2x, WORD m2y, WORD m2w, WORD m2h,
    WORD *message, LONG milliseconds,
    WORD *mx, WORD *my, WORD *buttons, WORD *keys, WORD *key, WORD *count)
{
    return evnt_multi(flags,clicks,mask,state,m1f,m1x,m1y,m1w,m1h,
        m2f,m2x,m2y,m2w,m2h,message,(UWORD)milliseconds,
        (UWORD)((ULONG)milliseconds>>16),mx,my,buttons,keys,key,count);
}
#define evnt_multi QedEvntMulti
#endif
