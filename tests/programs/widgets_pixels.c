#include "widgets.h"
#include "gem-drawing.h"
#include <exec816/runtime.h>
volatile uint16_t WidgetPixelStage,WidgetPixelGate,WidgetPixelFailures;
static struct WidgetTree tree;
static struct WidgetContext context;
static struct WidgetPacket packet;
volatile uint16_t WidgetPixelIndex;
static void check(uint16_t good) { if (!good) ++WidgetPixelFailures; }
extern void ClippedGlyphsProbe(void);
extern uint16_t GlyphClipTop;
extern void BuilderProbe(void);
extern void BuilderRunTests(void);
extern void BuilderFaultProbe(void);
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
    BuilderProbe();
    for (stage=1;stage<=22;stage++) {
        if (stage!=3 && stage!=6 && stage!=12 && stage!=14 && stage!=15 &&
            stage!=18 && stage!=19 && stage!=20)
            check(GemDrawingFill(0,0,640,240,3)==DISPLAY_OK);
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
        if (stage>=8 && stage<=11) {
            tree.objects[0].kind=stage==8 ? G_IBOX : G_BOX;
            tree.objects[0].spec=stage==11 ? 0x11178UL : 0x11108UL;
            tree.objects[0].flags=stage==10 ? HIDETREE : 0;
            check(WidgetValidate(&context,&tree,sizeof(tree),608,160)==WIDGET_OK);
        }
        /* Prepared outline lists reach both maximum work and minimum geometry.
         * Moving/hiding must restore the old XOR border without touching the
         * interior or accepting an invalid replacement. */
        if (stage==17) {
            /* Maximum-depth rejected tail: eight examined objects per step,
             * including steps with no draw. No scratch prefix is published. */
            memset(&tree,0,sizeof(tree));
            tree.version=WIDGET_VERSION;tree.count=WIDGET_OBJECTS;tree.background=8;
            for (i=0;i<WIDGET_OBJECTS;i++) {
                o=&tree.objects[i];o->kind=G_IBOX;
                o->width=608;o->height=160;
                o->next=i ? (i<7 ? i-1 : i==31 ? 6 : i+1) : -1;
                o->head=i<7 ? i+1 : -1;
                o->tail=i<6 ? i+1 : i==6 ? 31 : -1;
            }
            tree.objects[0].flags=HIDETREE;tree.objects[31].flags=LASTOB;
            check(WidgetValidate(&context,&tree,sizeof(tree),608,160)==WIDGET_OK);
            packet.left=17;packet.top=42;packet.right=625;packet.bottom=58;
            packet.index=0;packet.qualifiers=0;
        }
        if (stage==22) {
            memset(&tree,0,sizeof(tree));
            tree.version=WIDGET_VERSION;tree.count=2;tree.background=8;tree.textBytes=64;
            memset(tree.text,'A',63);
            o=&tree.objects[0];o->next=-1;o->head=o->tail=1;o->kind=G_BOX;
            o->width=608;o->height=160;o->spec=0x78;
            o=&tree.objects[1];o->next=0;o->head=o->tail=-1;o->kind=G_BUTTON;
            o->flags=SELECTABLE|LASTOB;o->state=SELECTED|DISABLED;
            o->x=9;o->y=23;o->width=504;o->height=24;
            check(WidgetValidate(&context,&tree,sizeof(tree),608,160)==WIDGET_OK);
            context.focus=1;
            paint(17,19,625,179,1);
        }
        else if (stage>=17 && stage<=20) {
            check(WidgetPaint(&packet)==DISPLAY_OK);
            check(packet.index==8*(stage-16));
            check(!!packet.changed==(stage!=20));
        }
        else if (stage==21) {
            packet.index=0;
            check(WidgetPaint(&packet)==DISPLAY_OK && packet.changed);
            BuilderFaultProbe();
            check(GemDrawingFill(0,0,640,240,3)==DISPLAY_OK);
            /* Reopen discarded the unfinished strip; only a new first step
             * may resume drawing. It must repaint the complete background. */
            check(WidgetPaint(&packet)==DISPLAY_BAD_ARGUMENT);
            packet.index=0;
            do { check(WidgetPaint(&packet)==DISPLAY_OK); } while (packet.changed);
        }
        else if (stage==16) BuilderRunTests();
        else if (stage==13) check(GemDrawingOutline(0,0,640,240,1)==DISPLAY_OK);
        else if (stage==14) {
            check(GemDrawingOutline(1,0,640,240,1)==DISPLAY_BAD_ARGUMENT);
            check(GemDrawingOutline(608,208,640,240,1)==DISPLAY_OK);
        }
        else if (stage==15) check(GemDrawingOutline(0,0,0,0,0)==DISPLAY_OK);
        else if (stage==7) {
            for (i=0;i<240;i+=16) {
                GlyphClipTop=i;
                check(GemDrawingBatch(0,i,640,i+16,ClippedGlyphsProbe)==DISPLAY_OK);
            }
        }
        else if (stage==11) {
            packet.context=(uint32_t)&context;
            packet.originX=17;packet.originY=19;packet.qualifiers=0;
            packet.left=17;packet.top=42;packet.right=625;packet.bottom=58;packet.index=0;
            check(WidgetPaint(&packet)==DISPLAY_OK && packet.changed);
            /* A mismatched continuation must leave the pending strip intact. */
            packet.right=624;
            check(WidgetPaint(&packet)==DISPLAY_BAD_ARGUMENT);
            packet.right=625;
        }
        else if (stage==12) {
            do {
                /* A native pointer operation between C chunks shares the
                 * command arena but must not redirect into widget scratch. */
                check(GemDrawingPointer(276,50,1)==DISPLAY_OK);
                check(GemDrawingPointer(276,50,0)==DISPLAY_OK);
                check(WidgetPaint(&packet)==DISPLAY_OK);
            } while (packet.changed);
        }
        else if (stage==2) paint(32,45,295,57,0);
        else paint(17,19,stage>=5 ? 625 : 337,179,stage==4);
        WidgetPixelIndex=packet.index;
        WidgetPixelStage=stage;
        while (WidgetPixelGate<stage) ExecYield();
    }
    BuilderFaultProbe();
    packet.bottom=packet.top;packet.index=0;
    check(WidgetPaint(&packet)==DISPLAY_BAD_ARGUMENT && packet.index==0);
    check(GemDrawingFill(0,0,640,240,0)==DISPLAY_OK);
}
