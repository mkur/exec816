/* SPDX-License-Identifier: GPL-3.0-only */
#include <gem.h>
#include <proto/dos.h>
static WORD globals[15],trials;
int main(void)
{
    WORD x,y,buttons,keys;
    WORD control[5]={79,0,5,0,0},out[5]={0,0,0,0,0};
    AESPB pb={control,globals,NULL,out,NULL,NULL};
    ++trials;
    if(!graf_mkstate(&x,&y,&buttons,&keys))return 101;
    aes_call(&pb);
    if(out[0]!=1 || out[1]!=x || out[2]!=y || out[3]!=buttons || out[4]!=keys)return 102;
    if(!graf_mkstate(&x,&y,&buttons,&keys) || x!=out[1] || y!=out[2])return 103;
    SetIoErr(0);return -321;
}
