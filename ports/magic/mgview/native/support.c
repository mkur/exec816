/* SPDX-License-Identifier: GPL-3.0-only
 * Native workstation/error glue. The viewer/parser remain the MagiC modules. */
#include "mgview-native.h"

WORD vdi_handle;
WORD work_in[12],work_out[57];

void open_work(void)
{
    int i;
    for(i=0;i<10;++i)work_in[i]=1;
    work_in[9]=WHITE;work_in[10]=2;
    v_opnvwk(work_in,&vdi_handle,work_out);
}

WORD top_whdl(void)
{
    WORD handle=0,b=0,c=0,d=0;
    wind_get(0,WF_TOP,&handle,&b,&c,&d);
    return handle;
}

void form_xerr(LONG error,const char *path)
{
    /* Bounded fixed text also prevents paths from becoming alert markup. */
    const char *message="[3][Cannot open or read this file.][OK]";
    (void)path;
    if(error==GEMDOS_ENSMEM)message="[3][Not enough memory.][OK]";
    else if(error==GEMDOS_ERANGE)message="[3][File, index or path is too large.][OK]";
    form_alert(1,message);
}

void *memchr2(const void *text,size_t length)
{
    const unsigned char *p=text;
    while(length--){if(*p=='\r' || *p=='\n')return (void *)p;++p;}
    return NULL;
}
