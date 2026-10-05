/* Shared host/65816 corpus for bounded admission and actual donor routines. */
#include "widgets.h"
volatile uint16_t widgetChecks,widgetFailures,widgetFailureAt;
static struct WidgetTree tree;
static struct WidgetContext context;
static uint16_t fills,texts;
static GRECT firstFill;
static void check(uint16_t good)
{
    ++widgetChecks;
    if (!good) { ++widgetFailures;widgetFailureAt=widgetChecks; }
}
void WidgetFill(WORD mode,WORD style,WORD pattern,WORD colour,const GRECT *r)
{
    (void)mode;(void)style;(void)pattern;(void)colour;
    if (!fills) firstFill=*r;
    ++fills;
}
void WidgetText(WORD x,WORD y,const WORD *glyphs,WORD count,WORD mode,WORD colour)
{
    (void)x;(void)y;(void)mode;(void)colour;
    check(count==1 && glyphs[0]=='A');
    ++texts;
}
static void init(void)
{
    uint16_t i;
    memset(&tree,0,sizeof(tree));
    tree.version=WIDGET_VERSION;tree.count=5;tree.textBytes=2;
    tree.text[0]='A';
    for (i=0;i<5;i++) {
        struct WidgetObject *o=&tree.objects[i];
        o->head=o->tail=-1;o->next=i==4 ? 0 : i+1;
        o->kind=G_BUTTON;o->flags=SELECTABLE;
        o->x=16+(i-1)*64;o->y=24;o->width=48;o->height=16;
    }
    tree.objects[0].next=-1;tree.objects[0].head=1;tree.objects[0].tail=4;
    tree.objects[0].kind=G_BOX;tree.objects[0].flags=0;
    tree.objects[0].x=tree.objects[0].y=0;
    tree.objects[0].width=320;tree.objects[0].height=160;
    tree.objects[0].spec=0x70;
    tree.objects[4].flags|=LASTOB;
}
static uint16_t admit(void)
{
    return WidgetValidate(&context,&tree,sizeof(tree),320,160);
}
uint16_t WidgetModelProbe(void)
{
    uint16_t i,before=widgetFailures;
    WORD selected,x,y;
    init();
    check(sizeof(OBJECT)==24);
    check(sizeof(struct WidgetContext)<=WIDGET_CONTEXT_BYTES);
    check(sizeof(tree)<=WIDGET_PACKET_LIMIT);
    check(admit()==WIDGET_OK);
    check(context.count==5 && context.focus==1 && context.parent[4]==0);
    for (i=0;i<5;i++) check(context.order[i]==i);
    check(WidgetHit(&context,16,24)==1);
    check(WidgetHit(&context,63,39)==1);
    check(WidgetHit(&context,64,39)==0);
    check(WidgetHit(&context,-1,20)==-1);
    ob_offset(context.objects,4,&x,&y);check(x==208 && y==24);
    fills=texts=0;r_set(&gl_clip,0,0,640,240);
    WidgetDrawObject(&context,0,0,0);
    check(fills==1 && firstFill.g_x==0 && firstFill.g_y==0 &&
          firstFill.g_w==320 && firstFill.g_h==160);
    WidgetDrawObject(&context,1,0,0);
    check(fills==10 && texts==1);
    fm_button(context.objects,1,1,&selected);
    check(context.objects[1].ob_state==SELECTED);
    fm_button(context.objects,1,1,&selected);
    check(context.objects[1].ob_state==0);
    context.objects[1].ob_flags|=RBUTTON;context.objects[2].ob_flags|=RBUTTON;
    fm_button(context.objects,1,1,&selected);
    fm_button(context.objects,2,1,&selected);
    check(context.objects[1].ob_state==0 && context.objects[2].ob_state==SELECTED);
    context.objects[2].ob_flags|=HIDETREE;
    check(WidgetHit(&context,80,24)==0 && !WidgetVisible(&context,2));
    init();tree.count=0;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.count=33;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[0].head=0;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[4].next=1;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[2].next=2;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[2].next=31;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[0].tail=3;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].spec=0x10000UL;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.text[1]='X';check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].kind=G_USERDEF;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].flags|=INDIRECT;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].state=SHADOWED;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].x=32760;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].x=0;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[0].spec=0xff0070UL;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[0].spec=0x0040;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].flags|=DEFAULT|EXIT;tree.objects[2].flags|=DEFAULT|EXIT;
    check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].flags|=RBUTTON;tree.objects[2].flags|=RBUTTON;
    tree.objects[1].state=tree.objects[2].state=SELECTED;
    check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].flags|=HIDETREE;
    check(admit()==WIDGET_OK && context.focus==2 && context.order[1]==1);
    check(WidgetValidate(&context,&tree,sizeof(tree)-1,320,160)==WIDGET_BAD_ARGUMENT);
    init();tree.objects[1].kind=G_IBOX;tree.objects[1].flags=0;
    tree.objects[1].width=64;tree.objects[1].height=64;
    tree.objects[1].head=tree.objects[1].tail=2;tree.objects[1].next=3;
    tree.objects[2].next=1;tree.objects[2].x=8;tree.objects[2].y=8;
    check(admit()==WIDGET_OK && context.parent[2]==1 && context.bounds[2].g_x==24);
    tree.objects[2].x=24;check(admit()==WIDGET_BAD_ARGUMENT);
    init();tree.count=32;tree.objects[0].tail=31;
    for (i=1;i<32;i++) {
        tree.objects[i]=tree.objects[1];tree.objects[i].next=i==31 ? 0 : i+1;
    }
    check(admit()==WIDGET_OK && context.order[31]==31);
    init();tree.count=9;tree.objects[0].tail=1;
    for (i=1;i<9;i++) {
        tree.objects[i]=tree.objects[0];tree.objects[i].next=i-1;
        tree.objects[i].head=tree.objects[i].tail=i==8 ? -1 : i+1;
    }
    check(admit()==WIDGET_BAD_ARGUMENT);
    tree.count=8;tree.objects[7].head=tree.objects[7].tail=-1;
    check(admit()==WIDGET_OK);
    return widgetFailures-before;
}
#ifdef WIDGET_HOST_TEST
#include <stdio.h>
int main(void)
{
    WidgetModelProbe();
    printf("widget model: %u checks, %u failures at %u\n",widgetChecks,widgetFailures,widgetFailureAt);
    return widgetFailures!=0;
}
#endif
