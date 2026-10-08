#include "aes-private.h"
#include "vdi-private.h"
#include <gem.h>
#include <proto/exec.h>
#include "gem-drawing.h"
#include "vdi-inquiry.inc"

/* Registration pins the presenter. Only this Task can change its context or
 * workstation; warm calls need no endpoint/pointer revalidation. */
static BOOL enter(struct ExecAESContext *c)
{
    if (!c) return FALSE;
    if (c->busy) { c->diagnostic=AES_BUSY; return FALSE; }
    if (!c->identity) { c->diagnostic=AES_IDENTITY; return FALSE; }
    c->busy=1; c->diagnostic=AES_OK;
    return TRUE;
}

WORD graf_handle(WORD *cw,WORD *ch,WORD *bw,WORD *bh)
{
    struct ExecAESContext *c=ExecAESContext();
    if (!enter(c)) return 0;
    *cw=*ch=*bw=*bh=8;
    c->busy=0;
    return EXEC_VDI_PHYSICAL;
}

BOOL ExecVDIClose(struct ExecAESContext *c)
{
    struct ExecVDIWorkstation *w=c->workstation;
    if (!w) return TRUE;
    if (DisplayGrantClose(&w->grant)!=DISPLAY_OK) {
        c->diagnostic=AES_DISPLAY_ERROR; return FALSE;
    }
    FreeSignal(w->signal);
    c->workstation=NULL; c->request.displayGrant=NULL;
    FreeMem(w,sizeof(*w));
    return TRUE;
}

static void open_virtual(struct ExecAESContext *c,VDIPB *pb)
{
    struct ExecVDIWorkstation *w;
    UWORD i;
    WORD physical=pb->contrl[6];
    pb->contrl[6]=0;
    if (c->workstation) { c->diagnostic=AES_RESOURCE; return; }
    if (physical!=EXEC_VDI_PHYSICAL) { c->diagnostic=AES_IDENTITY; return; }
    if (pb->intin[0]!=1 || pb->intin[7]!=FIS_SOLID || pb->intin[10]!=2) {
        c->diagnostic=AES_UNSUPPORTED; return;
    }
    if ((UWORD)pb->intin[6]>15 || (UWORD)pb->intin[9]>15) {
        c->diagnostic=AES_MALFORMED; return;
    }
    w=AllocMem(sizeof(*w),MEMF_PUBLIC|MEMF_CLEAR);
    if (!w) { c->diagnostic=AES_RESOURCE; return; }
    w->signal=AllocSignal(-1);
    if (w->signal<0) { FreeMem(w,sizeof(*w)); c->diagnostic=AES_RESOURCE; return; }
    w->grant.task=c->request.owner;
    w->grant.mask=1UL<<w->signal;
    c->request.displayGrant=(UBYTE *)&w->grant;
    c->busy=0;
    i=ExecAESSubmit(c,AES_OP_DISPLAY);
    c->busy=1;
    if (!i) {
        if (w->grant.state!=DISPLAY_GRANT_FREE) DisplayGrantClose(&w->grant);
        c->request.displayGrant=NULL;
        FreeSignal(w->signal); FreeMem(w,sizeof(*w)); return;
    }
    w->handle=EXEC_VDI_VIRTUAL;
    w->textColor=pb->intin[6]; w->fillColor=pb->intin[9];
    w->unit.glyphs=w->intin;
    c->workstation=w;
    for (i=0;i<45;++i) pb->intout[i]=w->intout[i]=workoutInts[i];
    for (i=0;i<12;++i) pb->ptsout[i]=w->ptsout[i]=workoutPoints[i];
    pb->contrl[2]=6; pb->contrl[4]=45; pb->contrl[6]=w->handle;
}

static BOOL drawing(struct ExecAESContext *c)
{
    if (!c->view || !c->view->shown) { c->diagnostic=AES_IDENTITY; return FALSE; }
    if (!c->view->updates) { c->diagnostic=AES_BUSY; return FALSE; }
    return TRUE;
}

/* The update snapshot supplies screen/work clipping even when user clipping
 * is off. No shared Layers traversal, RPC or event wait occurs here. */
static void paint(struct ExecAESContext *c,LONG left,LONG top,LONG right,LONG bottom)
{
    struct ExecVDIWorkstation *w=c->workstation;
    struct AESWindowView *v=c->view;
    struct ExecVDIUnit *u=&w->unit;
    UWORD i,status;
    LONG l,t,r,b,y;
    if (w->clipped) {
        if (left<w->clip[0]) left=w->clip[0];
        if (top<w->clip[1]) top=w->clip[1];
        if (right>(LONG)w->clip[2]+1) right=(LONG)w->clip[2]+1;
        if (bottom>(LONG)w->clip[3]+1) bottom=(LONG)w->clip[3]+1;
    }
    if (left>=right || top>=bottom) return;
    u->textColor=w->textColor; u->fillColor=w->fillColor;
    for (i=0;i<v->visibleCount;++i) {
        l=left>v->visible[i].left ? left:v->visible[i].left;
        t=top>v->visible[i].top ? top:v->visible[i].top;
        r=right<v->visible[i].right ? right:v->visible[i].right;
        b=bottom<v->visible[i].bottom ? bottom:v->visible[i].bottom;
        if (l>=r || t>=b) continue;
        for (y=t;y<b;y+=EXEC_VDI_STRIP_ROWS) {
            u->left=l; u->right=r; u->top=y;
            u->bottom=y+EXEC_VDI_STRIP_ROWS<b ? y+EXEC_VDI_STRIP_ROWS:b;
            status=GemDrawingBorrow(&w->grant,u->left,u->top,u->right,u->bottom,GemVdiPaint,u);
            if (status!=DISPLAY_OK) { c->diagnostic=AES_DISPLAY_ERROR; return; }
        }
    }
}

static void bar(struct ExecAESContext *c,const WORD *points)
{
    LONG l=points[0],t=points[1],r=points[2],b=points[3],swap;
    if (!drawing(c)) return;
    if (l>r) { swap=l; l=r; r=swap; }
    if (t>b) { swap=t; t=b; b=swap; }
    c->workstation->unit.operation=11;
    paint(c,l,t,r+1,b+1);
}

/* Named strings and parameter-block words share the streaming renderer. The
 * private 32-word chunk survives a preemption; no stack buffer escapes a call. */
static void text(struct ExecAESContext *c,WORD x,WORD y,const void *source,UWORD words,BOOL string)
{
    struct ExecVDIWorkstation *w=c->workstation;
    const UBYTE *chars=source;
    const WORD *glyphs=source;
    LONG at=x,top=(LONG)y-EXEC_VDI_FONT_TOP;
    UWORD count;
    if (!drawing(c)) return;
    w->unit.operation=8; w->unit.y=y;
    while (at<EXEC_VDI_WIDTH) {
        count=0;
        while (count<EXEC_VDI_TEXT_CHUNK) {
            if (string) {
                if (!*chars) break;
                w->intin[count++]=*chars++;
            } else {
                if (!words) break;
                w->intin[count++]=*glyphs++; --words;
            }
        }
        if (!count) break;
        w->unit.count=count; w->unit.x=(WORD)at;
        paint(c,at,top,at+((LONG)count<<3),top+EXEC_VDI_FONT_HEIGHT);
        if (c->diagnostic!=AES_OK) break;
        at+=(LONG)count<<3;
    }
}

/* Parameter counts are checked once at the public call boundary. Caller
 * pointers, buffer sizes and lifetimes follow the shared-address-space ABI. */
static void dispatch(struct ExecAESContext *c,VDIPB *pb)
{
    UWORD op=pb->contrl[0],pairs=0,words=0,i;
    WORD value,swap;
    struct ExecVDIWorkstation *w=c->workstation;
    pb->contrl[2]=pb->contrl[4]=0;
    switch (op) {
    case 100: words=11; break;
    case 101: break;
    case 8: pairs=1; words=pb->contrl[3]; break;
    case 11:
        if (pb->contrl[5]!=1) { c->diagnostic=AES_UNSUPPORTED; return; }
        pairs=2; break;
    case 22: case 23: case 25: case 32: words=1; break;
    case 129: pairs=2; words=1; break;
    default:c->diagnostic=AES_UNSUPPORTED; return;
    }
    if (pb->contrl[1]!=pairs || pb->contrl[3]!=words || pb->contrl[3]<0) {
        c->diagnostic=AES_MALFORMED; return;
    }
    if (op==100) { open_virtual(c,pb); return; }
    if (!w || pb->contrl[6]!=w->handle) { c->diagnostic=AES_IDENTITY; return; }
    for (i=0;i<12;++i) w->control[i]=pb->contrl[i];
    for (i=0;i<pairs*2;++i) w->ptsin[i]=pb->ptsin[i];
    switch (op) {
    case 101: ExecVDIClose(c); break;
    case 11: bar(c,w->ptsin); break;
    case 8: text(c,w->ptsin[0],w->ptsin[1],pb->intin,words,FALSE); break;
    case 129:
        value=pb->intin[0];
        if (value!=0 && value!=1) { c->diagnostic=AES_UNSUPPORTED; break; }
        for (i=0;i<4;++i) w->clip[i]=w->ptsin[i];
        if (w->clip[0]>w->clip[2]) { swap=w->clip[0]; w->clip[0]=w->clip[2]; w->clip[2]=swap; }
        if (w->clip[1]>w->clip[3]) { swap=w->clip[1]; w->clip[1]=w->clip[3]; w->clip[3]=swap; }
        w->clipped=value; break;
    default:
        value=pb->intin[0];
        if ((op==23 || op==32) ? value!=1 : (UWORD)value>15) {
            c->diagnostic=AES_UNSUPPORTED; break;
        }
        if (op==22) w->textColor=value;
        if (op==25) w->fillColor=value;
        pb->intout[0]=w->intout[0]=value; pb->contrl[4]=1;
    }
}

void EXEC_CALL vdi_call(VDIPB *pb)
{
    struct ExecAESContext *c=ExecAESContext();
    if (!enter(c)) {
        if (pb->contrl[0]==100) pb->contrl[6]=0;
        return;
    }
    dispatch(c,pb);
    c->busy=0;
}

static WORD call(WORD op,WORD sub,WORD pairs,WORD words,WORD handle,const WORD *points,const WORD *ints)
{
    WORD control[12]={0,0,0,0,0,0,0,0,0,0,0,0},reply=0;
    VDIPB pb={control,(WORD *)ints,(WORD *)points,&reply,NULL};
    control[0]=op; control[1]=pairs; control[3]=words; control[5]=sub; control[6]=handle;
    vdi_call(&pb);
    return reply;
}

void v_opnvwk(WORD *input,WORD *handle,WORD *output)
{
    WORD control[12]={0,0,0,0,0,0,0,0,0,0,0,0};
    VDIPB pb={control,input,NULL,output,output+45};
    control[0]=100; control[3]=11; control[6]=*handle;
    vdi_call(&pb); *handle=control[6];
}
void v_clsvwk(WORD h) { call(101,0,0,0,h,NULL,NULL); }
void v_bar(WORD h,const WORD *p) { call(11,1,2,0,h,p,NULL); }
void vs_clip(WORD h,WORD clip,const WORD *p) { call(129,0,2,1,h,p,&clip); }
WORD vswr_mode(WORD h,WORD mode) { return call(32,0,0,1,h,NULL,&mode); }
WORD vsf_interior(WORD h,WORD style) { return call(23,0,0,1,h,NULL,&style); }
WORD vsf_color(WORD h,WORD color) { return call(25,0,0,1,h,NULL,&color); }
WORD vst_color(WORD h,WORD color) { return call(22,0,0,1,h,NULL,&color); }
void v_gtext(WORD h,WORD x,WORD y,const char *s)
{
    struct ExecAESContext *c=ExecAESContext();
    if (!enter(c)) return;
    if (!c->workstation || c->workstation->handle!=h) c->diagnostic=AES_IDENTITY;
    else text(c,x,y,s,0,TRUE);
    c->busy=0;
}
