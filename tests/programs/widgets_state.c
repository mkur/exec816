/* Independent transactional expectations, shared by host and native fixtures. */
#include "widgets.h"
extern uint16_t WidgetSet(struct WidgetContext *,const struct WidgetTree *,struct WidgetPacket *);
extern uint16_t WidgetUpdate(struct WidgetContext *,const struct WidgetUpdate *,struct WidgetPacket *);
extern uint16_t WidgetRead(const struct WidgetContext *,struct WidgetSnapshot *,uint16_t);
extern void WidgetTestEpoch(uint32_t);
static struct WidgetContext c,other;
static struct WidgetTree tree;
static struct WidgetUpdate patch;
static struct WidgetSnapshot snapshot;
static struct WidgetPacket packet;
volatile uint16_t WidgetStateChecks,WidgetStateFailures;
static void check(uint16_t yes) { ++WidgetStateChecks;if (!yes) ++WidgetStateFailures; }
static void setup(void)
{
    uint16_t i;
    memset(&tree,0,sizeof(tree));tree.version=1;tree.count=5;tree.textBytes=8;
    memcpy(tree.text,"one\0two",8);
    for (i=0;i<5;i++) {
        struct WidgetObject *o=&tree.objects[i];
        o->head=o->tail=-1;o->next=i==4 ? 0 : i+1;o->kind=G_BUTTON;
        o->flags=SELECTABLE;o->x=8+i*48;o->y=8;o->width=40;o->height=16;
    }
    tree.objects[0].next=-1;tree.objects[0].head=1;tree.objects[0].tail=4;
    tree.objects[0].kind=G_BOX;tree.objects[0].flags=0;tree.objects[0].x=tree.objects[0].y=0;
    tree.objects[0].width=320;tree.objects[0].height=160;tree.objects[0].spec=0x70;
    tree.objects[2].flags|=RBUTTON;tree.objects[3].flags|=RBUTTON;tree.objects[2].state=SELECTED;
    packet.bytes=sizeof(tree);packet.width=320;packet.height=160;
    check(WidgetSet(&c,&tree,&packet)==WIDGET_OK);
}
static void update(void)
{
    memset(&patch,0,sizeof(patch));patch.epoch=c.epoch;patch.revision=c.revision;
    packet.bytes=sizeof(patch);packet.changed=0;
}
uint16_t WidgetStateProbe(void)
{
    uint16_t before=WidgetStateFailures;
    uint32_t epoch,revision;
    WidgetTestEpoch(1);
    setup();epoch=c.epoch;
    check(c.revision==1 && c.focus==1);
    check(WidgetRead(&c,&snapshot,sizeof(snapshot))==WIDGET_OK &&
        snapshot.epoch==epoch && snapshot.count==5 && snapshot.objects[2].state==SELECTED);
    check(WidgetRead(&c,&snapshot,sizeof(snapshot)-1)==WIDGET_BAD_ARGUMENT);
    update();check(WidgetUpdate(&c,&patch,&packet)==WIDGET_OK && !packet.changed && c.revision==1);
    patch.epoch--;check(WidgetUpdate(&c,&patch,&packet)==WIDGET_STALE && c.epoch==epoch);
    update();patch.count=1;patch.changes[0].object=1;patch.changes[0].mask=WIDGET_PATCH_STATE;
    patch.changes[0].state=SELECTED;
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_OK && c.revision==2 &&
        c.objects[1].ob_state==SELECTED && packet.left==55 && packet.right==97 && packet.changed);
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_STALE && c.revision==2);
    patch.revision=2;check(WidgetUpdate(&c,&patch,&packet)==WIDGET_OK && !packet.changed && c.revision==2);
    update();patch.count=2;patch.changes[0].object=2;patch.changes[0].mask=WIDGET_PATCH_STATE;
    patch.changes[0].state=0;patch.changes[1].object=3;patch.changes[1].mask=WIDGET_PATCH_STATE;
    patch.changes[1].state=SELECTED;
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_OK &&
        !c.objects[2].ob_state && c.objects[3].ob_state==SELECTED && c.revision==3);
    update();patch.count=1;patch.changes[0].object=2;patch.changes[0].mask=WIDGET_PATCH_STATE;
    patch.changes[0].state=SELECTED;
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_BAD_ARGUMENT && !c.objects[2].ob_state && c.revision==3);
    update();patch.count=1;patch.changes[0].object=1;patch.changes[0].mask=WIDGET_PATCH_LABEL;
    patch.changes[0].length=1;patch.text[0]='x';patch.textBytes=2;
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_OK && c.revision==4 &&
        !strcmp(c.text+(uint16_t)c.objects[1].ob_spec,"x") &&
        !strcmp(c.text+(uint16_t)c.objects[2].ob_spec,"one"));
    update();patch.count=2;
    patch.changes[0].object=1;patch.changes[0].mask=WIDGET_PATCH_STATE;
    patch.changes[0].state=0;patch.changes[1].object=33;patch.changes[1].mask=WIDGET_PATCH_STATE;
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_BAD_ARGUMENT && c.revision==4 &&
        c.objects[1].ob_state==SELECTED);
    update();patch.count=1;patch.changes[0].object=1;patch.changes[0].mask=WIDGET_PATCH_HIDDEN;
    patch.changes[0].hidden=1;c.armed=1;c.pressed=1;
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_OK && c.focus==2 &&
        c.armed==-1 && !c.pressed && c.revision==5);
    update();patch.count=1;patch.changes[0].object=0;patch.changes[0].mask=WIDGET_PATCH_HIDDEN;
    patch.changes[0].hidden=1;
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_BAD_ARGUMENT && !(c.objects[0].ob_flags&HIDETREE));
    packet.bytes=sizeof(tree);check(WidgetSet(&other,&tree,&packet)==WIDGET_OK && other.epoch!=epoch);
    check(c.focus==2 && other.focus==1 && c.revision==5 && other.revision==1);
    tree.objects[2].next=2;revision=c.revision;
    check(WidgetSet(&c,&tree,&packet)==WIDGET_BAD_ARGUMENT && c.epoch==epoch && c.revision==revision);
    tree.objects[2].next=3;
    check(WidgetSet(&c,&tree,&packet)==WIDGET_OK && c.epoch!=epoch && c.revision==1);
    update();patch.epoch=epoch;check(WidgetUpdate(&c,&patch,&packet)==WIDGET_STALE);
    c.revision=0xffffffffUL;update();
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_OK && !packet.changed && c.revision==0xffffffffUL);
    patch.count=1;patch.changes[0].object=1;patch.changes[0].mask=WIDGET_PATCH_STATE;patch.changes[0].state=SELECTED;
    check(WidgetUpdate(&c,&patch,&packet)==WIDGET_EXHAUSTED && !packet.changed &&
        !c.objects[1].ob_state && c.revision==0xffffffffUL);
    WidgetTestEpoch(0xffffffffUL);packet.bytes=sizeof(tree);
    check(WidgetSet(&c,&tree,&packet)==WIDGET_OK && c.epoch==0xffffffffUL);
    epoch=other.epoch;
    check(WidgetSet(&other,&tree,&packet)==WIDGET_EXHAUSTED && other.epoch==epoch);
    return WidgetStateFailures-before;
}
#ifdef WIDGET_STATE_HOST_TEST
#include <stdio.h>
void WidgetFill(WORD a,WORD b,WORD d,WORD e,const GRECT *r) { (void)a;(void)b;(void)d;(void)e;(void)r; }
void WidgetText(WORD a,WORD b,const WORD *d,WORD e,WORD f,WORD g) { (void)a;(void)b;(void)d;(void)e;(void)f;(void)g; }
int main(void) {
    WidgetStateProbe();
    printf("widget state: %u checks, %u failures\n",WidgetStateChecks,WidgetStateFailures);
    return WidgetStateFailures!=0;
}
#endif
