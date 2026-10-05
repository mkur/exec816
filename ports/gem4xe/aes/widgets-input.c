/* Event-driven adapter around donor fm_button. No device reads or waits. */
#include "widgets.h"

static void focus(struct WidgetContext *c,struct WidgetPacket *p,int16_t object)
{
    if (object==c->focus) return;
    WidgetDamage(p,c,c->focus);c->focus=object;WidgetDamage(p,c,c->focus);
}
static void cancel(struct WidgetContext *c,struct WidgetPacket *p)
{
    if (c->pressed) WidgetDamage(p,c,c->armed);
    c->armed=-1;c->pressed=0;
}
static uint16_t activate(struct WidgetContext *c,struct WidgetPacket *p,int16_t object)
{
    uint16_t before[WIDGET_OBJECTS],i,changed=0;
    WORD result;
    OBJECT *o;
    if (object<0 || !WidgetEligible(c,object)) return WIDGET_OK;
    o=&c->objects[object];
    /* A selected radio or momentary button can still report an action at MAX. */
    if (c->revision==0xffffffffUL && !(o->ob_flags&EXIT) &&
        !((o->ob_flags&RBUTTON) && (o->ob_state&SELECTED))) return WIDGET_EXHAUSTED;
    for (i=0;i<c->count;i++) before[i]=c->objects[i].ob_state;
    WidgetCurrent=c;fm_button(c->objects,object,1,&result);
    for (i=0;i<c->count;i++) if (before[i]!=c->objects[i].ob_state) {
        WidgetDamage(p,c,i);changed=1;
    }
    if (changed) c->revision++;
    p->kind=8;p->object=object;p->state=c->objects[object].ob_state;
    return WIDGET_OK;
}
uint16_t WidgetInput(struct WidgetContext *c,struct WidgetPacket *p)
{
    uint16_t kind=p->kind,scan=p->code&63,i,start=0,status=WIDGET_OK;
    int16_t object;
    p->kind=0;p->index=1;p->object=-1;p->changed=0;
    if (!c || !c->epoch) return WIDGET_BAD_ARGUMENT;
    if (p->operation==WIDGET_OP_CANCEL) cancel(c,p);
    else if (p->operation==WIDGET_OP_POINTER) {
        if (c->armed>=0) {
            object=WidgetHit(c,p->x,p->y);
            if (!(p->buttons&1)) {
                object=object==c->armed ? c->armed : -1;
                cancel(c,p);
                if (object>=0) status=activate(c,p,object);
            } else if (c->pressed!=(object==c->armed)) {
                c->pressed=object==c->armed;WidgetDamage(p,c,c->armed);
            }
        } else if (kind==3 && (p->buttons&1) && p->code) {
            object=WidgetHit(c,p->x,p->y);
            if (object>=0 && WidgetEligible(c,object)) {
                focus(c,p,object);c->armed=object;c->pressed=1;WidgetDamage(p,c,object);
            }
        }
    } else if (p->operation==WIDGET_OP_KEY) {
        if (kind==7 || scan==28) {
            cancel(c,p);p->kind=9;
        } else if (!(p->qualifiers&2) && scan==44) {
            cancel(c,p);
            for (i=0;i<c->count;i++) if (c->order[i]==c->focus) start=i;
            for (i=1;i<=c->count;i++) {
                object=c->order[(start+((p->qualifiers&1) ? c->count-i : i))%c->count];
                if (WidgetEligible(c,object)) { focus(c,p,object);break; }
            }
        } else if (!(p->qualifiers&2) && (scan==33 || scan==12)) {
            cancel(c,p);object=c->focus;
            if (scan==12) {
                object=-1;
                for (i=0;i<c->count;i++) if ((c->objects[i].ob_flags&DEFAULT) && WidgetEligible(c,i)) {
                    object=(int16_t)i;break;
                }
            }
            status=activate(c,p,object);
        } else p->index=0;
    } else return WIDGET_BAD_ARGUMENT;
    p->epoch=c->epoch;p->revision=c->revision;
    return status;
}
