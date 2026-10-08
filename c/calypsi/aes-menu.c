#include "aes-private.h"
#include <proto/exec.h>

/* Full C addresses are transported high word first in the fixed request. */
WORD ExecAESMenu(OBJECT *tree,WORD operation,WORD item,ULONG value)
{
    struct ExecAESContext *c=ExecAESContext();
    WORD result;
    if (!c) return 0;
    if (c->busy) { c->diagnostic=AES_BUSY; return 0; }
    if (!c->identity) { c->diagnostic=AES_IDENTITY; return 0; }
    c->request.intin[0]=operation;
    c->request.intin[1]=(WORD)((ULONG)tree>>16);
    c->request.intin[2]=(WORD)(ULONG)tree;
    c->request.intin[3]=item;
    c->request.intin[4]=(WORD)(value>>16);
    c->request.intin[5]=(WORD)value;
    result=ExecAESSubmit(c,AES_OP_MENU);
    if (result && operation==30) c->menuTree=item ? (ULONG)tree:0;
    return result;
}

WORD menu_bar(OBJECT *tree,WORD show)
{
    return ExecAESMenu(tree,30,show,0);
}
WORD menu_ienable(OBJECT *tree,WORD item,WORD enable)
{
    struct ExecAESContext *c=ExecAESContext();
    if (c && c->menuTree==(ULONG)tree) return ExecAESMenu(tree,32,item,enable);
    if (enable) tree[item].ob_state&=~DISABLED;
    else tree[item].ob_state|=DISABLED;
    return 1;
}
WORD menu_tnormal(OBJECT *tree,WORD item,WORD normal)
{
    struct ExecAESContext *c=ExecAESContext();
    if (c && c->menuTree==(ULONG)tree) return ExecAESMenu(tree,33,item,normal);
    if (normal) tree[item].ob_state&=~SELECTED;
    else tree[item].ob_state|=SELECTED;
    return 1;
}
WORD menu_text(OBJECT *tree,WORD item,const char *text)
{
    struct ExecAESContext *c=ExecAESContext();
    if (c && c->menuTree==(ULONG)tree) return ExecAESMenu(tree,34,item,(ULONG)text);
    tree[item].ob_spec=(ULONG)text; return 1;
}
struct Popup {
    WORD message[8],saved[GEM_OBJECT_LIMIT];
    WORD x,y,w,h,mx,my,mb,ks,kr,br;
};
static WORD paint(OBJECT *tree,WORD menu,struct Popup *p)
{
    WORD okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=objc_draw(tree,menu,MAX_DEPTH,p->x,p->y,p->w,p->h);
    if (!wind_update(END_UPDATE)) okay=0;
    return okay;
}
WORD menu_popup(const MENU *menu,WORD x,WORD y,MENU *result)
{
    struct ExecAESContext *c=ExecAESContext();
    OBJECT *tree=(OBJECT *)(ULONG)menu->mn_tree;
    struct Popup *p;
    WORD count=1,i,selected,first,last,oldX,oldY,ox,oy,events,hit,down=0,armed=NIL,done=0,okay=0;
    if (!c || !c->view || !c->view->shown || !c->workstation || menu->mn_scroll) return 0;
    p=AllocMem(sizeof(*p),MEMF_PUBLIC|MEMF_CLEAR);
    if (!p) { c->diagnostic=AES_RESOURCE; return 0; }
    while (!(tree[count-1].ob_flags&LASTOB)) ++count;
    for (i=0;i<count;++i) p->saved[i]=tree[i].ob_state;
    first=tree[menu->mn_menu].ob_head;last=tree[menu->mn_menu].ob_tail;
    selected=menu->mn_item>=0 ? menu->mn_item:first;
    oldX=tree[0].ob_x;oldY=tree[0].ob_y;
    objc_offset(tree,selected,&ox,&oy);
    tree[0].ob_x+=x-ox;tree[0].ob_y+=y-oy;
    objc_offset(tree,menu->mn_menu,&p->x,&p->y);
    p->w=tree[menu->mn_menu].ob_width;p->h=tree[menu->mn_menu].ob_height;
    /* The bounded menu must fit its owning work area; clamp its position. */
    if (p->w>c->view->work.right-c->view->work.left || p->h>c->view->work.bottom-c->view->work.top) goto finish;
    ox=p->x;oy=p->y;
    if (p->x<c->view->work.left) p->x=c->view->work.left;
    if (p->y<c->view->work.top) p->y=c->view->work.top;
    if (p->x+p->w>c->view->work.right) p->x=c->view->work.right-p->w;
    if (p->y+p->h>c->view->work.bottom) p->y=c->view->work.bottom-p->h;
    tree[0].ob_x+=p->x-ox;tree[0].ob_y+=p->y-oy;
    for (i=first;;i=tree[i].ob_next) {
        tree[i].ob_state&=~SELECTED;
        if (i==last) break;
    }
    if (!(tree[selected].ob_state&DISABLED)) tree[selected].ob_state|=SELECTED;
    if (!paint(tree,menu->mn_menu,p)) goto finish;
    while (!done) {
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG,1,1,down ? 0:1,
            0,0,0,0,0,0,0,0,0,0,p->message,0,0,&p->mx,&p->my,&p->mb,&p->ks,&p->kr,&p->br);
        if (!events) {
            if (ExecAESDiagnostic()==AES_INPUT_LOST) { down=1;armed=NIL;continue; }
            break;
        }
        if (events&MU_MESAG) {
            if (p->message[0]==WM_REDRAW && p->message[3]==c->view->handle) {
                if (!paint(tree,menu->mn_menu,p)) break;
            } else {
                /* Preserve manager requests for the application's event loop. */
                for (i=0;i<8;++i) c->deferredMessage[i]=p->message[i];
                c->deferredEpoch=c->messageEpoch;
                c->deferredMenuEpoch=c->messageMenuEpoch;
                c->messagePending=1;break;
            }
        }
        if (events&MU_BUTTON) {
            hit=objc_find(tree,menu->mn_menu,MAX_DEPTH,p->mx,p->my);
            if (p->mb&1) {
                down=1;armed=hit;
                if (hit>menu->mn_menu && !(tree[hit].ob_state&DISABLED)) {
                    tree[selected].ob_state&=~SELECTED;selected=hit;
                    tree[selected].ob_state|=SELECTED;
                    if (!paint(tree,menu->mn_menu,p)) break;
                }
            } else {
                down=0;done=1;
                okay=hit==armed && hit>menu->mn_menu && !(tree[hit].ob_state&DISABLED);
            }
        }
        if (events&MU_KEYBD) {
            if ((p->kr&255)==27) done=1;
            else if ((p->kr&255)==13) { okay=!(tree[selected].ob_state&DISABLED);done=1; }
            else if ((p->kr>>8)==0x48 || (p->kr>>8)==0x50 || (p->kr&255)==9) {
                i=selected;
                do {
                    if ((p->kr>>8)==0x48) {
                        hit=first;
                        if (i==first) i=last;
                        else { while (tree[hit].ob_next!=i) hit=tree[hit].ob_next;i=hit; }
                    } else i=i==last ? first:tree[i].ob_next;
                    if (!(tree[i].ob_state&DISABLED) && !(tree[i].ob_flags&HIDETREE)) break;
                } while (i!=selected);
                tree[selected].ob_state&=~SELECTED;selected=i;tree[selected].ob_state|=SELECTED;
                if (!paint(tree,menu->mn_menu,p)) break;
            }
        }
    }
    if (okay) { *result=*menu;result->mn_item=selected;result->mn_keystate=p->ks; }
finish:
    for (i=0;i<count;++i) tree[i].ob_state=p->saved[i];
    tree[0].ob_x=oldX;tree[0].ob_y=oldY;
    FreeMem(p,sizeof(*p));return okay;
}
BOOL ExecAESMenus(struct ExecAESContext *c,AESPB *pb)
{
    WORD op=pb->control[0],ins=2,addresses=1;
    if (op!=30 && op!=32 && op!=33 && op!=34 && op!=36) return FALSE;
    if (op==30) ins=1;
    if (op==34) { ins=1;addresses=2; }
    if (op==36) addresses=2;
    pb->int_out[0]=0;
    if (pb->control[1]!=ins || pb->control[2]!=1 || pb->control[3]!=addresses || pb->control[4]) {
        c->diagnostic=AES_MALFORMED;return TRUE;
    }
    c->diagnostic=AES_OK;
    switch (op) {
    case 30:pb->int_out[0]=menu_bar((OBJECT *)(ULONG)pb->addr_in[0],pb->int_in[0]);break;
    case 32:pb->int_out[0]=menu_ienable((OBJECT *)(ULONG)pb->addr_in[0],pb->int_in[0],pb->int_in[1]);break;
    case 33:pb->int_out[0]=menu_tnormal((OBJECT *)(ULONG)pb->addr_in[0],pb->int_in[0],pb->int_in[1]);break;
    case 34:pb->int_out[0]=menu_text((OBJECT *)(ULONG)pb->addr_in[0],pb->int_in[0],(const char *)(ULONG)pb->addr_in[1]);break;
    case 36:pb->int_out[0]=menu_popup((MENU *)(ULONG)pb->addr_in[0],pb->int_in[0],pb->int_in[1],(MENU *)(ULONG)pb->addr_in[1]);break;
    }
    return TRUE;
}
