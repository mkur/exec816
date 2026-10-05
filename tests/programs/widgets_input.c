/* Independent input transition assertions; native and host use the same probe. */
#include "widgets.h"
static struct WidgetContext c;
static struct WidgetTree tree;
static struct WidgetPacket p;
volatile uint16_t WidgetInputChecks,WidgetInputFailures;
static void check(int yes) { WidgetInputChecks++;if (!yes) WidgetInputFailures++; }
static void step(uint16_t op,uint16_t kind,int16_t x,int16_t y,uint16_t buttons,uint16_t code,uint16_t modifiers)
{
    memset(&p,0,sizeof(p));p.operation=op;p.kind=kind;p.x=x;p.y=y;
    p.buttons=buttons;p.code=code;p.qualifiers=modifiers;
    p.status=WidgetInput(&c,&p);
}
uint16_t WidgetInputProbe(void)
{
    uint16_t i,before=WidgetInputFailures;
    uint32_t revision;
    memset(&tree,0,sizeof(tree));tree.version=WIDGET_VERSION;tree.count=6;tree.textBytes=2;
    tree.text[0]='X';tree.objects[0].next=-1;tree.objects[0].head=1;tree.objects[0].tail=5;
    tree.objects[0].kind=G_IBOX;tree.objects[0].width=300;tree.objects[0].height=100;
    for (i=1;i<6;i++) {
        struct WidgetObject *o=&tree.objects[i];
        o->next=i==5 ? 0 : i+1;o->head=o->tail=-1;o->kind=G_BUTTON;
        o->flags=SELECTABLE;o->x=10+i*40;o->y=20;o->width=32;o->height=16;
    }
    tree.objects[2].flags|=RBUTTON;tree.objects[2].state=SELECTED;
    tree.objects[3].flags|=RBUTTON;tree.objects[4].flags|=DEFAULT|EXIT;
    tree.objects[5].flags|=LASTOB;tree.objects[5].state=DISABLED;
    check(WidgetValidate(&c,&tree,sizeof(tree),300,100)==WIDGET_OK);
    c.epoch=42;c.revision=1;
    step(WIDGET_OP_POINTER,3,55,24,1,1,0);
    check(c.armed==1 && c.pressed && !c.objects[1].ob_state && !p.kind && p.changed);
    check(p.damageCount==1 && p.damage[0].left==49 && p.damage[0].top==19 &&
        p.damage[0].right==83 && p.damage[0].bottom==37);
    step(WIDGET_OP_POINTER,2,10,70,1,0,0);
    check(c.armed==1 && !c.pressed && p.changed);
    step(WIDGET_OP_POINTER,2,55,24,1,0,0);
    check(c.pressed && p.changed);
    step(WIDGET_OP_POINTER,3,55,24,0,0,0);
    check(c.armed==-1 && !c.pressed && p.kind==8 && p.object==1 && p.state==SELECTED && c.revision==2);
    step(WIDGET_OP_POINTER,3,55,24,0,0,0);
    check(!p.kind && !p.changed && c.revision==2);
    step(WIDGET_OP_POINTER,3,55,24,1,1,0);
    step(WIDGET_OP_POINTER,3,10,70,0,0,0);
    check(!p.kind && c.armed==-1 && c.objects[1].ob_state==SELECTED);
    step(WIDGET_OP_POINTER,3,55,24,1,0,0);
    check(c.armed==-1); /* Held/ambiguous input cannot arm. */
    step(WIDGET_OP_POINTER,3,215,24,1,1,0);
    check(c.armed==-1); /* Disabled. */
    step(WIDGET_OP_KEY,1,0,0,0,44,0);
    check(c.focus==2 && p.index && !p.kind);
    check(p.damageCount==2 && p.damage[0].left==93 && p.damage[0].right==119 &&
        p.damage[1].left==53 && p.damage[1].right==79 &&
        p.damage[0].top==33 && p.damage[0].bottom==34 &&
        p.damage[1].top==33 && p.damage[1].bottom==34);
    step(WIDGET_OP_KEY,1,0,0,0,44,1);
    check(c.focus==1);
    step(WIDGET_OP_KEY,1,0,0,0,44,1);
    check(c.focus==4); /* Reverse wrap skips disabled. */
    step(WIDGET_OP_KEY,1,0,0,0,33,0);
    check(p.kind==8 && p.object==4 && !p.state && c.revision==2);
    step(WIDGET_OP_KEY,1,0,0,0,12,0);
    check(p.kind==8 && p.object==4 && c.revision==2);
    step(WIDGET_OP_POINTER,3,135,24,1,1,0);
    check(p.damageCount==2 && p.damage[0].left==129 && p.damage[0].right==163 &&
        p.damage[1].left==173 && p.damage[1].right==199);
    step(WIDGET_OP_POINTER,3,135,24,0,0,0);
    check(p.kind==8 && p.object==3 && !c.objects[2].ob_state && c.objects[3].ob_state==SELECTED && c.revision==3);
    check(p.damageCount==2 && p.damage[0].left==129 && p.damage[0].right==163 &&
        p.damage[1].left==89 && p.damage[1].right==123);
    step(WIDGET_OP_KEY,1,0,0,0,33,0);
    check(p.kind==8 && c.revision==3); /* Selecting the same radio is an action, not a revision. */
    step(WIDGET_OP_POINTER,3,55,24,1,1,0);
    step(WIDGET_OP_KEY,1,0,0,0,28,0);
    check(p.kind==9 && c.armed==-1 && c.objects[1].ob_state==SELECTED && p.changed);
    step(WIDGET_OP_KEY,7,0,0,0,1,0);
    check(p.kind==9 && p.epoch==42 && p.revision==3);
    step(WIDGET_OP_KEY,1,0,0,0,63,0);
    check(!p.index && !p.kind);
    step(WIDGET_OP_KEY,1,0,0,0,33,2);
    check(!p.index && !p.kind);
    c.objects[1].ob_flags|=HIDETREE;
    step(WIDGET_OP_KEY,1,0,0,0,44,0);
    check(c.focus==2);
    step(WIDGET_OP_POINTER,3,55,24,1,1,0);
    check(c.armed==-1);
    c.revision=0xffffffffUL;c.focus=2;
    step(WIDGET_OP_KEY,1,0,0,0,33,0);
    check(p.status==WIDGET_EXHAUSTED && !p.kind && !c.objects[2].ob_state && c.objects[3].ob_state==SELECTED);
    revision=c.revision;
    step(WIDGET_OP_KEY,1,0,0,0,12,0);
    check(p.status==WIDGET_OK && p.kind==8 && p.object==4 && c.revision==revision);
    step(WIDGET_OP_POINTER,3,135,24,1,1,0);
    step(WIDGET_OP_CANCEL,0,0,0,0,0,0);
    check(c.armed==-1 && !c.pressed && !p.kind && p.changed);
    /* More independently damaged controls than the bridge can retain must
       preserve all pixels through its conservative full-client fallback. */
    memset(&tree,0,sizeof(tree));tree.version=WIDGET_VERSION;tree.count=10;tree.textBytes=2;
    tree.text[0]='X';tree.objects[0].next=-1;tree.objects[0].head=1;tree.objects[0].tail=9;
    tree.objects[0].kind=G_BOX;tree.objects[0].width=300;tree.objects[0].height=100;
    for (i=1;i<10;i++) {
        struct WidgetObject *o=&tree.objects[i];
        o->next=i==9 ? 0 : i+1;o->head=o->tail=-1;o->kind=G_BUTTON;
        o->flags=SELECTABLE|(i==9 ? LASTOB : 0);o->x=10+i*24;o->y=20;o->width=16;o->height=16;
    }
    check(WidgetValidate(&c,&tree,sizeof(tree),300,100)==WIDGET_OK);
    memset(&p,0,sizeof(p));
    for (i=1;i<9;i++) WidgetDamage(&p,&c,i);
    check(p.damageCount==8);
    WidgetFocusDamage(&p,&c,1);WidgetDamage(&p,&c,1);
    check(p.damageCount==8); /* Contained duplicates do not overflow. */
    WidgetDamage(&p,&c,9);
    check(p.changed && p.damageCount==1 && !p.damage[0].left && !p.damage[0].top &&
        p.damage[0].right==300 && p.damage[0].bottom==100);
    WidgetDamage(&p,&c,2);check(p.damageCount==1);
    return WidgetInputFailures-before;
}
#ifdef WIDGET_INPUT_HOST_TEST
#include <stdio.h>
void WidgetFill(WORD a,WORD b,WORD d,WORD e,const GRECT *r) { (void)a;(void)b;(void)d;(void)e;(void)r; }
void WidgetText(WORD a,WORD b,const WORD *d,WORD e,WORD f,WORD g) { (void)a;(void)b;(void)d;(void)e;(void)f;(void)g; }
int main(void) {
    WidgetInputProbe();printf("widget input: %u checks, %u failures\n",WidgetInputChecks,WidgetInputFailures);
    return WidgetInputFailures!=0;
}
#endif
