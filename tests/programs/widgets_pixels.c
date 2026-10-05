#include "widgets.h"
#include "gem-drawing.h"
#include <exec816/runtime.h>
volatile uint16_t WidgetPixelStage,WidgetPixelGate,WidgetPixelFailures;
static struct WidgetTree tree;
static struct WidgetContext context;
static struct WidgetPacket packet;
static void check(uint16_t good) { if (!good) ++WidgetPixelFailures; }
extern void ClippedGlyphsProbe(void);
extern uint16_t GlyphClipTop;
static void paint(uint16_t left,uint16_t top,uint16_t right,uint16_t bottom,uint16_t focus)
{
    uint16_t y;
    packet.context=(uint32_t)&context;
    packet.originX=17;packet.originY=19;packet.qualifiers=focus;
    packet.left=left;packet.right=right;
    for (y=top;y<bottom;y+=16) {
        packet.top=y;packet.bottom=y+16<bottom ? y+16 : bottom;packet.index=0;
        do { check(WidgetPaint(&packet)==DISPLAY_OK); } while (packet.index<context.count);
    }
}
void WidgetPixelProbe(void)
{
    uint16_t i,stage;
    struct WidgetObject *o;
    memset(&tree,0,sizeof(tree));
    tree.version=WIDGET_VERSION;tree.count=7;tree.textBytes=8;tree.background=8;
    memcpy(tree.text,"Abc\0XYZ",8);
    for (i=0;i<7;i++) {
        o=&tree.objects[i];o->head=o->tail=-1;o->next=i==6 ? 0 : i+1;
        o->kind=G_BUTTON;o->flags=SELECTABLE;o->x=9+(i-1)*50;
        o->y=23;o->width=40;o->height=24;
    }
    o=&tree.objects[0];o->next=-1;o->head=1;o->tail=6;o->kind=G_BOX;o->flags=0;
    o->x=o->y=0;o->width=320;o->height=160;o->spec=0x11178UL;
    tree.objects[1].flags|=EXIT|DEFAULT;
    tree.objects[2].state=SELECTED;
    tree.objects[3].state=DISABLED;
    tree.objects[4].state=SELECTED|DISABLED;
    tree.objects[5].kind=G_STRING;tree.objects[5].flags=0;tree.objects[5].spec=4;
    tree.objects[6].kind=G_IBOX;tree.objects[6].flags=LASTOB;tree.objects[6].spec=0x21170UL;
    check(WidgetValidate(&context,&tree,sizeof(tree),320,160)==WIDGET_OK);
    for (stage=1;stage<=7;stage++) {
        if (stage!=3 && stage!=6) check(GemDrawingFill(0,0,640,240,3)==DISPLAY_OK);
        if (stage==3) check(GemDrawingPointer(276,50,1)==DISPLAY_OK);
        if (stage==5) {
            tree.count=9;tree.objects[0].width=608;tree.objects[0].tail=8;
            tree.objects[6].flags=0;tree.objects[6].next=7;
            tree.objects[7]=tree.objects[5];tree.objects[7].next=8;
            tree.objects[7].x=24;tree.objects[7].y=70;tree.objects[7].width=504;
            tree.objects[7].spec=8;tree.textBytes=72;
            memset(tree.text+8,'A',63);tree.text[71]=0;
            tree.objects[8]=tree.objects[5];tree.objects[8].next=0;
            tree.objects[8].flags=LASTOB;tree.objects[8].x=65;tree.objects[8].y=26;
            check(WidgetValidate(&context,&tree,sizeof(tree),608,160)==WIDGET_OK);
        }
        if (stage==7) {
            for (i=0;i<240;i+=16) {
                GlyphClipTop=i;
                check(GemDrawingBatch(0,i,640,i+16,ClippedGlyphsProbe)==DISPLAY_OK);
            }
        }
        else if (stage==2) paint(32,45,295,57,0);
        else paint(17,19,stage>=5 ? 625 : 337,179,stage==4);
        WidgetPixelStage=stage;
        while (WidgetPixelGate<stage) ExecYield();
    }
    packet.bottom=packet.top;packet.index=0;
    check(WidgetPaint(&packet)==DISPLAY_BAD_ARGUMENT && packet.index==0);
    check(GemDrawingFill(0,0,640,240,0)==DISPLAY_OK);
}
