/* SPDX-License-Identifier: MIT */
#include <gem.h>

static char document[]="A\tB\r\nSecond\n\rThird\rFourth\n";
static char invalid[]={'x'};
static WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57];
static OBJECT tree={-1,-1,-1,G_EDIT,LASTOB,0,0,0,0,0,0};
GRECT work,coverBounds,coverWork;
volatile WORD phase,proceed;

static WORD draw(WORD window)
{
    WORD okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(window,WF_WORKXYWH,&work.g_x,&work.g_y,&work.g_w,&work.g_h);
    tree.ob_x=work.g_x;
    tree.ob_y=work.g_y;
    tree.ob_width=work.g_w;
    tree.ob_height=work.g_h;
    if (okay) okay=objc_draw(&tree,0,0,work.g_x,work.g_y,work.g_w,work.g_h);
    return wind_update(END_UPDATE) && okay;
}

static void show(WORD stage)
{
    phase=stage;
    while (proceed!=stage) evnt_timer(20,0);
}

int main(void)
{
    WORD window,cover,handle,unused;
    WORD points[4];
    XEDITINFO *edit;
    phase=proceed=0;
    if (appl_init()<0) return 1;
    handle=graf_handle(&unused,&unused,&unused,&unused);
    v_opnvwk(input,&handle,output);
    if (!handle) return 2;
    window=wind_create(NAME|CLOSER,32,40,240,112);
    if (window<=0 || !wind_open(window,32,40,240,112)) return 3;
    if (!wind_get(window,WF_WORKXYWH,&work.g_x,&work.g_y,&work.g_w,&work.g_h)) return 4;
    tree.ob_width=work.g_w;
    tree.ob_height=work.g_h;
    edit=edit_create();
    if (!edit) return 5;
    tree.ob_spec=(ULONG)edit;
    edit_set_buf(&tree,0,invalid,sizeof(invalid));
    if (edit_open(&tree,0)) return 6;
    edit_set_buf(&tree,0,document,sizeof(document));
    if (!edit_open(&tree,0) || !draw(window)) return 7;
    show(1);

    cover=wind_create(NAME|CLOSER,62,45,104,70);
    if (cover<=0 || !wind_open(cover,62,45,104,70)) return 8;
    if (!wind_get(cover,WF_CURRXYWH,&coverBounds.g_x,&coverBounds.g_y,
            &coverBounds.g_w,&coverBounds.g_h) ||
        !wind_get(cover,WF_WORKXYWH,&coverWork.g_x,&coverWork.g_y,
            &coverWork.g_w,&coverWork.g_h)) return 9;
    if (!wind_update(BEG_UPDATE)) return 10;
    points[0]=coverWork.g_x;
    points[1]=coverWork.g_y;
    points[2]=points[0]+coverWork.g_w-1;
    points[3]=points[1]+coverWork.g_h-1;
    vsf_color(handle,2);
    vr_recfl(handle,points);
    if (!wind_update(END_UPDATE) || !draw(window)) return 11;
    show(2);

    if (!wind_close(cover) || !wind_delete(cover)) return 12;
    edit_close(&tree,0);
    if (!edit_open(&tree,0) || !draw(window)) return 13;
    show(3);
    edit_close(&tree,0);
    edit_delete(edit);
    /* Leave another open editor for automatic AES retirement. */
    edit=edit_create();
    if (!edit) return 14;
    tree.ob_spec=(ULONG)edit;
    edit_set_buf(&tree,0,document,sizeof(document));
    if (!edit_open(&tree,0)) return 15;
    return 0;
}
