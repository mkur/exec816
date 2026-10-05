/* Ordinary C bridge; the desktop presenter is the sole caller. */
#include "widgets.h"
struct WidgetPacket WidgetPacket __attribute__((aligned(2)));
extern uint16_t WidgetSet(struct WidgetContext *,const struct WidgetTree *,struct WidgetPacket *);
extern uint16_t WidgetUpdate(struct WidgetContext *,const struct WidgetUpdate *,struct WidgetPacket *);
extern uint16_t WidgetRead(const struct WidgetContext *,struct WidgetSnapshot *,uint16_t);
void WidgetEntry(void)
{
    struct WidgetPacket *p=&WidgetPacket;
    struct WidgetContext *c=(struct WidgetContext *)p->context;
    p->status=WIDGET_BAD_ARGUMENT;p->changed=p->damageCount=0;
    if (!c) return;
    switch (p->operation) {
    case WIDGET_OP_SET:
        p->status=WidgetSet(c,(const struct WidgetTree *)p->payload,p);break;
    case WIDGET_OP_UPDATE:
        p->status=WidgetUpdate(c,(const struct WidgetUpdate *)p->payload,p);break;
    case WIDGET_OP_READ:
        p->status=WidgetRead(c,(struct WidgetSnapshot *)p->payload,p->bytes);break;
    case WIDGET_OP_POINTER:
    case WIDGET_OP_KEY:
    case WIDGET_OP_CANCEL:
        p->status=WidgetInput(c,p);break;
    case WIDGET_OP_DRAW:
        p->status=WidgetPaint(p);break;
    }
    WidgetCurrent=0;
}
