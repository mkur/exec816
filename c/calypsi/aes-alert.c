/* Bounded standard alerts share the ordinary caller-local form session. */
#include "aes-alert-private.h"
#include "vdi-private.h"
#include "gem-drawing.h"
#include "alert-icons.h"
#include <proto/exec.h>
#include <string.h>
extern void GemWidgetFill(UWORD,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);

static UWORD part(const char *text,WORD *position,char *strings,WORD stride,
                  WORD limit,WORD *count,WORD buttons)
{
    WORD n=0,length=0;
    char ch;
    if (text[(*position)++]!='[') return AES_MALFORMED;
    for (;;) {
        ch=text[(*position)++];
        if (!ch) return AES_MALFORMED;
        if (ch==']' || ch=='|') {
            if (text[*position]==ch) ++*position;
            else {
                if (buttons && !length) return AES_MALFORMED;
                strings[n*stride+length]=0; ++n;
                if (ch==']') { *count=n; return AES_OK; }
                if (n==limit) return AES_UNSUPPORTED;
                length=0; continue;
            }
        }
        if (length==stride-1) return AES_UNSUPPORTED;
        strings[n*stride+length++]=ch;
    }
}

/* Only this admission boundary parses the trusted, NUL-terminated input.
 * Tree traversal and painting use the already established fixed bounds. */
UWORD ExecAESAlertParse(struct ExecAESAlert *a,WORD def,const char *text)
{
    WORD length=0,position=3,i,maxLine=0,maxButton=0,width,height,content,buttons,x;
    UWORD status;
    while (length<512 && text[length]) ++length;
    if (length==512) return AES_UNSUPPORTED;
    if (length<3 || text[0]!='[' || text[2]!=']' || text[1]<'0' || text[1]>'9')
        return AES_MALFORMED;
    a->icon=text[1]-'0';
    if (a->icon>3) return AES_UNSUPPORTED;
    status=part(text,&position,&a->lines[0][0],41,5,&a->lineCount,0);
    if (status!=AES_OK) return status;
    status=part(text,&position,&a->labels[0][0],21,3,&a->buttonCount,1);
    if (status!=AES_OK) return status;
    if (text[position] || def<0 || def>a->buttonCount) return AES_MALFORMED;
    for (i=0;i<a->lineCount;++i) {
        length=strlen(a->lines[i]); if (length>maxLine) maxLine=length;
    }
    for (i=0;i<a->buttonCount;++i) {
        length=strlen(a->labels[i]); if (length>maxButton) maxButton=length;
    }
    content=maxLine*8+(a->icon ? 48:0);
    buttons=(maxButton*8+16)*a->buttonCount+8*(a->buttonCount-1);
    width=(content>buttons ? content:buttons)+32;
    content=a->lineCount*12;
    if (a->icon && content<32) content=32;
    height=content+64;
    for (i=0;i<10;++i) {
        OBJECT *o=&a->tree[i];
        memset(o,0,sizeof(*o));
        o->ob_next=i+1; o->ob_head=o->ob_tail=NIL;
        o->ob_type=G_IBOX; o->ob_flags=HIDETREE;
    }
    a->tree[0].ob_next=NIL; a->tree[0].ob_head=1; a->tree[0].ob_tail=9;
    a->tree[0].ob_type=G_BOX; a->tree[0].ob_flags=0; a->tree[0].ob_spec=0x00011170;
    a->tree[0].ob_width=width; a->tree[0].ob_height=height;
    for (i=0;i<a->lineCount;++i) {
        OBJECT *o=&a->tree[i+2];
        o->ob_type=G_STRING; o->ob_flags=0; o->ob_spec=(ULONG)a->lines[i];
        o->ob_x=16+(a->icon ? 48:0)+(width-32-(a->icon ? 48:0)-strlen(a->lines[i])*8)/2;
        o->ob_y=16+i*12; o->ob_width=strlen(a->lines[i])*8; o->ob_height=8;
    }
    x=(width-buttons)/2;
    for (i=0;i<a->buttonCount;++i) {
        OBJECT *o=&a->tree[i+7];
        o->ob_type=G_BUTTON; o->ob_flags=SELECTABLE|EXIT;
        if (i+1==def) o->ob_flags|=DEFAULT;
        o->ob_spec=(ULONG)a->labels[i]; o->ob_x=x; o->ob_y=height-32;
        o->ob_width=maxButton*8+16; o->ob_height=16; x+=o->ob_width+8;
    }
    a->tree[9].ob_flags|=LASTOB; a->tree[9].ob_next=0;
    return AES_OK;
}

struct IconPaint { WORD icon,x,y,left,top,right,bottom; };
static void icon_strip(void *data)
{
    struct IconPaint *p=data;
    const UBYTE *run=AlertIconRuns+AlertIconOffsets[p->icon-1];
    const UBYTE *end=AlertIconRuns+AlertIconOffsets[p->icon];
    WORD x,y,right;
    for (;run<end;run+=3) {
        y=p->y+run[0];
        if (y<p->top || y>=p->bottom) continue;
        x=p->x+run[1]; right=x+run[2];
        if (x<p->left) x=p->left;
        if (right>p->right) right=p->right;
        if (x<right) GemWidgetFill(1,1,1,x,y,right,y+1);
    }
}

WORD ExecAESAlertPaint(struct ExecAESContext *c)
{
    struct ExecAESAlert *a=c->form->alert;
    struct AESWindowView *v=c->view;
    struct IconPaint p;
    WORD i,row,bottom;
    if (!a->icon) return 1;
    p.icon=a->icon; p.x=a->tree[0].ob_x+16; p.y=a->tree[0].ob_y+16;
    for (i=0;i<v->visibleCount;++i) {
        p.left=p.x>v->visible[i].left ? p.x:v->visible[i].left;
        p.right=p.x+32<v->visible[i].right ? p.x+32:v->visible[i].right;
        row=p.y>v->visible[i].top ? p.y:v->visible[i].top;
        bottom=p.y+32<v->visible[i].bottom ? p.y+32:v->visible[i].bottom;
        if (p.left>=p.right) continue;
        for (;row<bottom;row+=16) {
            p.top=row; p.bottom=row+16<bottom ? row+16:bottom;
            if (GemDrawingBorrow(&c->workstation->grant,p.left,p.top,p.right,p.bottom,
                                 icon_strip,&p)!=DISPLAY_OK) {
                c->diagnostic=AES_DISPLAY_ERROR; return 0;
            }
        }
    }
    return 1;
}

WORD form_alert(WORD def,const char *text)
{
    struct ExecAESContext *c=ExecAESContext();
    struct ExecAESAlert *a;
    GRECT r;
    WORD result;
    UWORD status;
    if (!c) return 0;
    if (c->busy || c->form || c->editTree || c->updateDepth || c->mouseDepth) {
        c->diagnostic=AES_BUSY; return 0;
    }
    a=AllocMem(sizeof(*a),MEMF_PUBLIC|MEMF_CLEAR);
    if (!a) { c->diagnostic=AES_RESOURCE; return 0; }
    status=ExecAESAlertParse(a,def,text);
    if (status!=AES_OK) { c->diagnostic=status; goto failure; }
    if (!form_center(a->tree,&r.g_x,&r.g_y,&r.g_w,&r.g_h) ||
        !ExecAESFormBegin(c,&r,"Alert")) goto failure;
    c->form->alert=a; c->form->tree=a->tree;
    c->form->originalX=a->tree[0].ob_x; c->form->originalY=a->tree[0].ob_y;
    result=ExecAESFormRun(c,0);
    if (!ExecAESFormFinish(c)) return 0;
    return result<7 ? 0:result-6;
failure:
    FreeMem(a,sizeof(*a)); return 0;
}
