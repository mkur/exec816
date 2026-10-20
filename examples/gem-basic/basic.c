/* SPDX-License-Identifier: MIT */
#include "basic.h"
#include <exec816/aes.h>

WORD BasicOpen(struct BasicApp *a)
{
    WORD i,bw,bh;
    a->window=-1;a->id=appl_init();
    if (a->id<0) return 0;
    a->vdi=graf_handle(&a->cellw,&a->cellh,&bw,&bh);
    for (i=0;i<10;++i) a->input[i]=1;
    a->input[10]=2;v_opnvwk(a->input,&a->vdi,a->output);
    if (!a->vdi) return 0;
    a->window=wind_create(BASIC_WINDOW_KIND,0,0,480,192);
    if (a->window<0 || !wind_set_str(a->window,WF_NAME,"FastBasic") ||
        !wind_set(a->window,AES_WF_EXEC_PRESERVE,1,0,0,0) ||
        !wind_open(a->window,48,32,480,192)) return 0;
    a->opened=a->ready=1;return 1;
}

WORD BasicClose(struct BasicApp *a)
{
    /* appl_exit retires menus, workstation and windows before model storage
     * can disappear. The shared Process wrapper detaches the endpoint. */
    a->ready=0;
    return appl_exit();
}
