/* SPDX-License-Identifier: MIT */
#include "text.h"
#include <exec816/aes.h>
#include <exec816/program.h>
#include "../../c/calypsi/file-list.h"
#include <string.h>

static const OBJECT menu[]={
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,16},
    {1,3,3,G_IBOX,0,0,0,8,0,424,16},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"File",0,0,48,16},
    {0,5,5,G_IBOX,0,0,0,0,16,640,224},
    {4,6,8,G_BOX,0,0,0x1100,8,0,120,48},
    {7,-1,-1,G_STRING,0,0,(ULONG)"Open        O",0,0,120,16},
    {8,-1,-1,G_STRING,0,DISABLED,(ULONG)"Cancel Load",0,16,120,16},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Quit        Q",0,32,120,16}
};

static WORD minimum(WORD a,WORD b) { return a<b ? a:b; }
static WORD maximum(WORD a,WORD b) { return a>b ? a:b; }

/* Union unfinished damage, clipped to the current work area. */
static void damage(struct TextApp *a,const WORD *r)
{
    WORD x=maximum(r[0],a->work[0]),y=maximum(r[1],a->work[1]);
    WORD endx=minimum(r[0]+r[2],a->work[0]+a->work[2]);
    WORD endy=minimum(r[1]+r[3],a->work[1]+a->work[3]);
    if (x>=endx || y>=endy) return;
    if (a->dirty) {
        endx=maximum(endx,a->damage[0]+a->damage[2]);
        endy=maximum(endy,a->damage[1]+a->damage[3]);
        x=minimum(x,a->damage[0]);y=minimum(y,a->damage[1]);
    }
    a->damage[0]=x;a->damage[1]=y;a->damage[2]=endx-x;a->damage[3]=endy-y;a->dirty=1;
}

static void status(struct TextApp *a,const char *text)
{
    WORD r[4];
    if (!strcmp(a->status,text)) return;
    strcpy(a->status,text);
    r[0]=a->work[0];r[1]=a->work[1]+a->work[3]-12;r[2]=a->work[2];r[3]=12;
    damage(a,r);
}

static char *number(char *out,UWORD n)
{
    UWORD place=10000,digit;WORD started=0;
    do {
        digit=n/place;n-=digit*place;
        if (digit || started || place==1) { *out++='0'+digit;started=1; }
        place/=10;
    } while (place);
    *out=0;return out;
}

static void line_status(struct TextApp *a)
{
    char *p=a->row;
    if (a->load.phase) return;
    if (!a->document.data) { status(a,"O: Open a text file");return; }
    if (!a->document.lines) { status(a,"Empty file");return; }
    p=number(p,a->first+1);*p++='-';
    p=number(p,minimum(a->first+a->rows,a->document.lines));
    strcpy(p," / ");p=number(p+3,a->document.lines);strcpy(p," lines");status(a,a->row);
}

static WORD viewport(struct TextApp *a)
{
    WORD extent,size,position;
    if (!wind_get(a->window,WF_WXYWH,&a->work[0],&a->work[1],&a->work[2],&a->work[3])) return 0;
    a->rows=(a->work[3]-20)/a->cellh;a->columns=(a->work[2]-8)/a->cellw;
    extent=maximum(0,a->document.lines-a->rows);
    a->first=minimum(maximum(a->first,0),extent);
    size=extent ? (LONG)a->rows*1000/a->document.lines:1000;
    position=extent ? (LONG)a->first*1000/extent:0;
    line_status(a);
    if (size!=a->sliderSize) {
        if (!wind_set(a->window,WF_VSLSIZE,size,0,0,0)) return 0;
        a->sliderSize=size;
    }
    if (position!=a->sliderPosition) {
        if (!wind_set(a->window,WF_VSLIDE,position,0,0,0)) return 0;
        a->sliderPosition=position;
    }
    return 1;
}

static WORD bar(struct TextApp *a,WORD x,WORD y,WORD w,WORD h)
{
    WORD p[4];
    if (w<=0 || h<=0) return 1;
    p[0]=x;p[1]=y;p[2]=x+w-1;p[3]=y+h-1;v_bar(a->vdi,p);
    return ExecAESDiagnostic()==AES_OK;
}

static WORD paint(struct TextApp *a)
{
    WORD visible[4],clip[4],y,end,rowY,i,start,okay=1,x,textY,textEnd,statusY;
    y=a->damage[1];textY=a->work[1]+4;
    start=maximum(0,(y-textY)/a->cellh);
    end=minimum(a->damage[1]+a->damage[3],textY+(start+4)*a->cellh);
    if (!wind_update(BEG_UPDATE)) return 0;
    if (!wind_get(a->window,WF_FIRSTXYWH,&visible[0],&visible[1],&visible[2],&visible[3])) okay=0;
    while (okay && visible[2] && visible[3]) {
        clip[0]=maximum(a->damage[0],visible[0]);clip[1]=maximum(y,visible[1]);
        clip[2]=minimum(a->damage[0]+a->damage[2],visible[0]+visible[2])-1;
        clip[3]=minimum(end,visible[1]+visible[3])-1;
        if (clip[0]<=clip[2] && clip[1]<=clip[3]) {
            vs_clip(a->vdi,1,clip);
            x=a->work[0]+4;textEnd=textY+a->rows*a->cellh;statusY=a->work[1]+a->work[3]-12;
            okay=bar(a,a->work[0],y,4,end-y) &&
                bar(a,x+a->columns*a->cellw,y,a->work[2]-4-a->columns*a->cellw,end-y) &&
                bar(a,x,a->work[1],a->columns*a->cellw,4) &&
                bar(a,x,textEnd,a->columns*a->cellw,statusY-textEnd) &&
                bar(a,x,statusY+8,a->columns*a->cellw,4);
            for (i=start;i<a->rows && okay;++i) {
                rowY=textY+i*a->cellh;if (rowY>=end) break;
                TextRow(&a->document,a->first+i,a->row,a->columns);
                v_gtext(a->vdi,x,rowY+6,a->row);okay=ExecAESDiagnostic()==AES_OK;
            }
            if (okay && statusY<end && statusY+8>y) {
                WORD n=0;
                while (n<a->columns && a->status[n]) { a->row[n]=a->status[n];++n; }
                while (n<a->columns) a->row[n++]=' ';
                a->row[n]=0;v_gtext(a->vdi,x,statusY+6,a->row);okay=ExecAESDiagnostic()==AES_OK;
            }
        }
        if (!wind_get(a->window,WF_NEXTXYWH,&visible[0],&visible[1],&visible[2],&visible[3])) okay=0;
    }
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) {
        a->damage[3]-=end-y;a->damage[1]=end;a->dirty=a->damage[3]!=0;++a->paints;
    }
    return okay;
}

static WORD scroll(struct TextApp *a,WORD first)
{
    first=minimum(maximum(first,0),maximum(0,a->document.lines-a->rows));
    if (first==a->first) return 1;
    a->first=first;
    if (!viewport(a)) return 0;
    damage(a,a->work);return 1;
}

static void load_error(struct TextApp *a)
{
    LONG error=a->load.error;
    if (error==TEXT_LINE_LIMIT) status(a,"More than 4096 lines");
    else if (error==ERROR_OBJECT_TOO_LARGE) status(a,"File exceeds 64 KiB");
    else if (error==ERROR_NO_FREE_STORE) status(a,"Not enough memory");
    else {
        char *p=a->row+19;
        strcpy(a->row,"Cannot load: error ");
        if (error<0) { *p++='-';error=-error; }
        number(p,(UWORD)error);status(a,a->row);
    }
}

static void begin(struct TextApp *a)
{
    TextBegin(&a->load,a->target);status(a,"Loading - Escape cancels");
    a->turn=0;
}

static WORD choose(struct TextApp *a)
{
    WORD button;
    if (!fsel_exinput(a->path,a->file,&button,"Open text")) {
        if (ExecAESDiagnostic()==AES_PENDING) { ++a->interruptions;return 1; }
        status(a,"File selector failed");return 1;
    }
    if (button==FSEL_OK) {
        if (!FileSplit(a->path,a->directory,a->mask) ||
            !FileJoin(a->target,sizeof(a->target),a->directory,a->file)) status(a,"Path too long");
        else begin(a);
    }
    return 1;
}

WORD TextRun(struct TextApp *a)
{
    WORD i,events,mx,my,buttons,mods,key,clicks,quit=0,result=20,action,step,kind;
    WORD x,y;
    a->id=appl_init();a->window=-1;a->sliderSize=-1;a->sliderPosition=-1;
    if (a->id<0) return result;
    a->vdi=graf_handle(&a->cellw,&a->cellh,&x,&y);
    for (i=0;i<10;++i) a->input[i]=1;
    a->input[10]=2;v_opnvwk(a->input,&a->vdi,a->output);
    if (!a->vdi) goto finish;
    vsf_color(a->vdi,0);vst_color(a->vdi,1);
    kind=NAME|CLOSER|MOVER|SIZER|UPARROW|DNARROW|VSLIDE;
    if (!wind_calc(WC_BORDER,kind,0,0,208,128,&x,&y,&a->minw,&a->minh)) goto finish;
    a->window=wind_create(kind,0,0,480,192);
    if (a->window<0 || !wind_set_str(a->window,WF_NAME,"Text viewer") ||
        !wind_open(a->window,32,32,480,192)) goto finish;
    a->opened=1;
    memcpy(a->menu,menu,sizeof(menu));
    if (!menu_bar(a->menu,1)) goto finish;
    a->menuInstalled=1;
    strcpy(a->path,"SYS:*.TXT");
    if (!viewport(a)) goto finish;
    damage(a,a->work);
    if (!TextArgument(ExecGetArgStr(),a->target)) status(a,"Expected one path (127 bytes max)");
    else if (*a->target) begin(a);
    a->ready=1;result=0;
    while (!quit && !result) {
        events=evnt_multi(MU_KEYBD|MU_MESAG|((a->dirty || a->load.phase) ? MU_TIMER:0),
            1,1,1,0,0,0,0,0,0,0,0,0,0,a->message,0,0,&mx,&my,&buttons,&mods,&key,&clicks);
        if (!events) {
            if (ExecAESDiagnostic()!=AES_INPUT_LOST) { result=20;break; }
            TextCancel(&a->load);status(a,"Input lost - load cancelled");continue;
        }
        action=0;
        if (events&MU_MESAG) {
            if (a->message[0]==MN_SELECTED) {
                action=a->message[4];if (!menu_tnormal(a->menu,a->message[3],1)) result=20;
            } else if (a->message[3]==a->window) {
                switch (a->message[0]) {
                case WM_CLOSED:quit=1;break;
                case WM_TOPPED:if (!wind_set(a->window,WF_TOP,0,0,0,0)) result=20;break;
                case WM_SIZED:
                    a->message[6]=maximum(a->minw,a->message[6]);a->message[7]=maximum(a->minh,a->message[7]);
                    a->message[4]=minimum(a->message[4],640-a->message[6]);
                    a->message[5]=minimum(a->message[5],240-a->message[7]);
                    /* Fall through: accept and restart damage in new geometry. */
                case WM_MOVED:
                    if (!wind_set(a->window,WF_CXYWH,a->message[4],a->message[5],a->message[6],a->message[7])) result=20;
                    a->dirty=0;if (!viewport(a)) result=20;damage(a,a->work);break;
                case WM_REDRAW:damage(a,&a->message[4]);break;
                case WM_VSLID:
                    if (!scroll(a,(LONG)a->message[4]*maximum(0,a->document.lines-a->rows)/1000)) result=20;break;
                case WM_ARROWED:
                    i=a->message[4];
                    if (!scroll(a,a->first+(i==WA_UPLINE ? -1:i==WA_DNLINE ? 1:i==WA_UPPAGE ? -a->rows:a->rows))) result=20;
                    break;
                }
            }
        }
        if (quit || result) break;
        if (events&MU_KEYBD) {
            switch (key&255) {
            case 'o':case 'O':action=6;break;
            case 27:action=7;break;
            case 'q':case 'Q':action=8;break;
            case ' ':if (!scroll(a,a->first+((mods&3) ? -a->rows:a->rows))) result=20;break;
            default:
                if ((key>>8)==0x48 || (key>>8)==0x50)
                    if (!scroll(a,a->first+((key>>8)==0x48 ? -1:1))) result=20;
            }
        }
        if (action==8) break;
        if (action==7 && a->load.phase) { TextCancel(&a->load);status(a,"Load cancelled"); }
        if (action==6 && !a->load.phase) { if (!choose(a)) result=20;continue; }
        if (a->menuLoading!=(a->load.phase!=0)) {
            a->menuLoading=a->load.phase!=0;
            if (!menu_ienable(a->menu,6,!a->menuLoading) || !menu_ienable(a->menu,7,a->menuLoading)) result=20;
        }
        if (result) break;
        /* First finish the Loading paint; subsequently alternate with disk units. */
        if (a->dirty && (!a->load.phase || !a->turn || a->load.phase==1)) {
            if (!paint(a)) result=20;a->turn=1;
        } else if (a->load.phase) {
            step=TextStep(&a->load,&a->document);a->turn=0;
            if (step==1) {
                const char *leaf=a->document.path,*p=leaf;
                while (*p) { if (*p==':' || *p=='/') leaf=p+1;++p; }
                if (!wind_set_str(a->window,WF_NAME,leaf)) result=20;
                a->first=0;++a->loads;if (!viewport(a)) result=20;damage(a,a->work);
            } else if (step<0) load_error(a);
        }
    }
finish:
    a->ready=0;TextCancel(&a->load);TextDispose(&a->document);
    if (!appl_exit()) result=20;
    return result;
}
