/* SPDX-License-Identifier: MIT */
#include <gem.h>
#include <exec816/aes.h>
#include <string.h>

#define DOCUMENT "A\tB\r\nSecond\n\rThird\rFourth\n"
static char document[sizeof(DOCUMENT)+3]=DOCUMENT;
#define ROW(n) n " abcdefghijklmnopqrstuvwxyz-0123456789\r\n"
static char scrollDocument[]=
    ROW("00") ROW("01") ROW("02") ROW("03") ROW("04") ROW("05") ROW("06") ROW("07")
    ROW("08") ROW("09") ROW("10") ROW("11") ROW("12") ROW("13") ROW("14") ROW("15");
static char invalid[]={'x'};
static WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57];
static OBJECT tree={-1,-1,-1,G_EDIT,LASTOB,0,0,0,0,0,0};
GRECT work,coverBounds,coverWork;
volatile WORD phase,proceed;
LONG scrollTop;
WORD scrollLeft;
volatile WORD dragActive,dragDone,dragMode;
UWORD dragStatus;

static WORD geometry(WORD window)
{
    if (!wind_get(window,WF_WORKXYWH,&work.g_x,&work.g_y,&work.g_w,&work.g_h)) return 0;
    tree.ob_x=work.g_x;
    tree.ob_y=work.g_y;
    tree.ob_width=work.g_w;
    tree.ob_height=work.g_h;
    return 1;
}

static WORD draw(WORD window)
{
    WORD okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=geometry(window) && objc_draw(&tree,0,0,work.g_x,work.g_y,work.g_w,work.g_h);
    return wind_update(END_UPDATE) && okay;
}

static void show(WORD stage)
{
    phase=stage;
    while (proceed!=stage) evnt_timer(20,0);
}

static WORD key(WORD window,WORD code,LONG expectedError)
{
    EVNT event;
    LONG error;
    WORD result;
    if (!wind_update(BEG_UPDATE)) return 0;
    event.mwhich=MU_KEYBD|MU_MESAG;
    event.key=code;
    event.kstate=0;
    result=edit_evnt(&tree,0,window,&event,&error);
    return wind_update(END_UPDATE) && result==(expectedError==0) &&
        error==expectedError && event.mwhich==MU_MESAG;
}

static WORD scroll_info(LONG top,WORD left)
{
    LONG lines;
    WORD rows,shown,width,visibleWidth;
    return edit_get_scrollinfo(&tree,0,&lines,&scrollTop,&rows,&shown,&width,
        &scrollLeft,&visibleWidth) && lines==17 && scrollTop==top && scrollLeft==left &&
        rows==work.g_h/8 && shown==rows && width==320 && visibleWidth==work.g_w;
}

static WORD scroll(WORD window,LONG top,WORD left)
{
    WORD result;
    if (!wind_update(BEG_UPDATE)) return 0;
    result=edit_scroll(&tree,0,window,top,left);
    return wind_update(END_UPDATE) && result;
}

static WORD drag(WORD window,WORD stage,WORD loss)
{
    EVNT event;
    LONG error;
    WORD okay;
    phase=stage;
    do {
        event.mwhich=evnt_multi_moblk(MU_BUTTON,1,1,1,NULL,NULL,NULL,0,0,
            &event.mx,&event.my,&event.mbutton,&event.kstate,&event.key,&event.mclicks);
        dragStatus=ExecAESDiagnostic();
        if (!event.mwhich && dragStatus!=AES_INPUT_LOST) return 0;
    } while (!(event.mwhich&MU_BUTTON) || ExecAESInputWindow(MU_BUTTON)!=window);
    if (!wind_update(BEG_UPDATE)) return 0;
    dragActive=stage;
    okay=edit_evnt(&tree,0,window,&event,&error);
    dragStatus=ExecAESDiagnostic();
    dragActive=0;
    dragDone=stage;
    if (!loss && stage==11) show(13);
    return wind_update(END_UPDATE) && !event.mwhich &&
        (loss ? !okay && error==-1 && dragStatus==AES_INPUT_LOST:okay && !error);
}

int main(void)
{
    WORD window,cover,handle,unused;
    WORD points[4],oldHeight,newHeight;
    LONG capacity,length;
    char *buffer,*cursor,*start,*end;
    XEDITINFO *edit;
    phase=proceed=dragActive=dragDone=0;
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

    if (edit_get_dirty(&tree,0) || !key(window,0x4d00,0) ||
        !key(window,0x2d78,0) || !key(window,0x1c0d,0) ||
        !key(window,0x1c0d,EDITERR_BUFFER_FULL)) return 16;
    if (!edit_get_buf(&tree,0,&buffer,&capacity,&length) ||
        buffer!=document || capacity!=sizeof(document) || length!=capacity-1 ||
        strcmp(buffer,"Ax\r\n\tB\r\nSecond\n\rThird\rFourth\n") ||
        !edit_get_cursor(&tree,0,&cursor) || cursor!=document+4 ||
        !edit_get_dirty(&tree,0)) return 17;
    show(2);
    if (!key(window,0x0e08,0) || strcmp(document,"Ax\tB\r\nSecond\n\rThird\rFourth\n") ||
        !key(window,0x4b00,0) || !key(window,0x537f,0) || strcmp(document,DOCUMENT)) return 18;
    edit_set_dirty(&tree,0,0);
    if (!wind_update(BEG_UPDATE)) return 19;
    if (edit_cursor(&tree,0,window,0)!=1 || edit_cursor(&tree,0,window,0)!=2 ||
        edit_cursor(&tree,0,window,1)!=1 || edit_cursor(&tree,0,window,1)!=0 ||
        !wind_update(END_UPDATE)) return 20;
    if (!key(window,0x1e01,0)) return 21;
    edit_get_sel(&tree,0,&start,&end);
    if (start!=document || end!=document+sizeof(DOCUMENT)-1 || edit_get_dirty(&tree,0)) return 22;

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
    show(3);

    if (!wind_close(cover) || !wind_delete(cover) || !draw(window)) return 12;
    show(4);
    edit_close(&tree,0);
    if (!wind_set(window,WF_CURRXYWH,33,40,240,112) ||
        !edit_open(&tree,0) || !draw(window)) return 13;
    show(5);
    edit_close(&tree,0);
    edit_set_buf(&tree,0,scrollDocument,sizeof(scrollDocument));
    if (!wind_set(window,WF_CURRXYWH,33,40,156,67) || !geometry(window) ||
        !edit_open(&tree,0) || !wind_update(BEG_UPDATE)) return 23;
    if (edit_cursor(&tree,0,window,0)!=1 || !wind_update(END_UPDATE) ||
        !draw(window) || !scroll_info(0,0)) return 24;
    show(6);
    if (!scroll(window,1,-1) || !scroll_info(1,0)) return 25;
    show(7);
    if (!scroll(window,-1,3) || !scroll(window,-1,6) || !scroll(window,-1,1) ||
        !scroll(window,-1,9) || !scroll_info(1,9)) return 26;
    show(8);
    if (!key(window,0x5100,0) || !scroll_info(1+work.g_h/8,9)) return 27;
    show(9);
    if (!wind_update(BEG_UPDATE)) return 28;
    if (!wind_set(window,WF_CURRXYWH,33,40,164,83) || !geometry(window) ||
        !edit_resized(&tree,0,&oldHeight,&newHeight) || oldHeight!=48 ||
        newHeight!=64 || !wind_update(END_UPDATE) || !draw(window) ||
        !scroll_info(7,0)) return 29;
    show(10);
    if (dragMode && (ExecAESMouseProfile(0)!=0 ||
        !wind_set(window,WF_CURRXYWH,280,70,164,83) || !draw(window) ||
        !key(window,0x1e01,0))) return 34;
    edit_get_sel(&tree,0,&start,&end);
    if (dragMode==2) {
        char *savedStart=start,*savedEnd=end;
        if (!drag(window,11,1)) return 32;
        edit_get_sel(&tree,0,&start,&end);
        if (start!=savedStart || end!=savedEnd || !scroll_info(7,0)) return 33;
    } else if (dragMode==1) {
        if (!drag(window,11,0)) return 30;
        edit_get_sel(&tree,0,&start,&end);
        if (!start || end<=start || start==scrollDocument || !scroll_info(9,0)) return 31;
        if (!drag(window,14,0)) return 35;
    }
    show(12);
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
