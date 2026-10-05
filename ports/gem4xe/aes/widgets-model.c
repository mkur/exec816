/* Bounded admission around the extracted AES walks. GPL-3.0-only. */
#include "widgets.h"

struct WidgetContext *WidgetCurrent;
static uint16_t orderCount;

const char *WidgetSpec(uint32_t offset)
{
    return WidgetCurrent->text+(uint16_t)offset;
}

static void remember(OBJECT *tree,WORD index,WORD x,WORD y)
{
    struct WidgetContext *c=WidgetCurrent;
    c->order[orderCount++]=(uint16_t)index;
    r_set(&c->bounds[index],x,y,tree[index].ob_width,tree[index].ob_height);
}

/* Only validated contexts enter donor walks. The parent chain is at most eight. */
uint16_t WidgetVisible(const struct WidgetContext *c,uint16_t index)
{
    int16_t parent=(int16_t)index;
    do {
        if (c->objects[parent].ob_flags&HIDETREE) return 0;
        parent=c->parent[parent];
    } while (parent>=0);
    return 1;
}

uint16_t WidgetValidate(struct WidgetContext *c,const struct WidgetTree *p,
                        uint16_t bytes,uint16_t width,uint16_t height)
{
    uint16_t i,j,k,depth,defaults=0;
    int16_t child,parent;
    int32_t x,y,right,bottom;
    WORD border;
    OBJECT *o;
    if (!p || bytes!=sizeof(*p) || p->version!=WIDGET_VERSION ||
        !p->count || p->count>WIDGET_OBJECTS || p->textBytes>WIDGET_TEXT_BYTES ||
        p->background>15 || !width || width>624 || !height || height>216)
        return WIDGET_BAD_ARGUMENT;
    memset(c,0,sizeof(*c));
    c->count=p->count;c->textBytes=p->textBytes;c->background=p->background;
    c->width=width;c->height=height;c->focus=c->armed=-1;
    memcpy(c->objects,p->objects,sizeof(c->objects));
    memcpy(c->text,p->text,p->textBytes);
    for (i=0;i<c->count;i++) c->parent[i]=-2;
    c->parent[0]=-1;
    if (c->objects[0].ob_next!=-1 || c->objects[0].ob_x || c->objects[0].ob_y ||
        c->objects[0].ob_width!=width || c->objects[0].ob_height!=height ||
        (c->objects[0].ob_type!=G_BOX && c->objects[0].ob_type!=G_IBOX))
        return WIDGET_BAD_ARGUMENT;
    for (i=0;i<c->count;i++) {
        o=&c->objects[i];
        if (o->ob_type!=G_BOX && o->ob_type!=G_IBOX &&
            o->ob_type!=G_STRING && o->ob_type!=G_BUTTON) return WIDGET_BAD_ARGUMENT;
        if (o->ob_flags&~(SELECTABLE|DEFAULT|EXIT|RBUTTON|LASTOB|HIDETREE) ||
            o->ob_state&~(SELECTED|DISABLED)) return WIDGET_BAD_ARGUMENT;
        if ((o->ob_flags&LASTOB) && i!=c->count-1) return WIDGET_BAD_ARGUMENT;
        if (o->ob_type!=G_BUTTON &&
            ((o->ob_flags&(SELECTABLE|DEFAULT|EXIT|RBUTTON)) || o->ob_state))
            return WIDGET_BAD_ARGUMENT;
        if (o->ob_type==G_BUTTON && (!(o->ob_flags&SELECTABLE) ||
            ((o->ob_flags&RBUTTON) && (o->ob_flags&(EXIT|DEFAULT)))))
            return WIDGET_BAD_ARGUMENT;
        if (o->ob_flags&DEFAULT) {
            if (!(o->ob_flags&EXIT) || ++defaults>1) return WIDGET_BAD_ARGUMENT;
        }
        if (o->ob_type==G_BUTTON && (o->ob_flags&EXIT) && (o->ob_state&SELECTED))
            return WIDGET_BAD_ARGUMENT;
        if (o->ob_x<0 || o->ob_y<0 || o->ob_width<=0 || o->ob_height<=0)
            return WIDGET_BAD_ARGUMENT;
        if (o->ob_type==G_BOX || o->ob_type==G_IBOX) {
            /* Inward border 0..3, no BOXCHAR; hollow or solid interiors. */
            if (o->ob_spec>>24 || ((o->ob_spec>>16)&255)>3 ||
                (((o->ob_spec>>4)&7)!=0 && ((o->ob_spec>>4)&7)!=7))
                return WIDGET_BAD_ARGUMENT;
            if (o->ob_width<2*(WORD)(o->ob_spec>>16) ||
                o->ob_height<2*(WORD)(o->ob_spec>>16)) return WIDGET_BAD_ARGUMENT;
        } else {
            if (o->ob_spec>=c->textBytes) return WIDGET_BAD_ARGUMENT;
            j=(uint16_t)o->ob_spec;k=0;
            while (j<c->textBytes && c->text[j] && k<=WIDGET_LABEL_MAX) { j++;k++; }
            if (j==c->textBytes || k>WIDGET_LABEL_MAX || k*8>o->ob_width ||
                o->ob_height<8) return WIDGET_BAD_ARGUMENT;
        }
        if (o->ob_head==-1) {
            if (o->ob_tail!=-1) return WIDGET_BAD_ARGUMENT;
        } else {
            if (o->ob_type!=G_BOX && o->ob_type!=G_IBOX) return WIDGET_BAD_ARGUMENT;
            child=o->ob_head;j=0;
            for (;;) {
                if (child<=0 || child>=c->count || c->parent[child]!=-2 ||
                    ++j>c->count) return WIDGET_BAD_ARGUMENT;
                c->parent[child]=(int16_t)i;
                if (child==o->ob_tail) {
                    if (c->objects[child].ob_next!=i) return WIDGET_BAD_ARGUMENT;
                    break;
                }
                child=c->objects[child].ob_next;
            }
        }
    }
    for (i=0;i<c->count;i++) {
        o=&c->objects[i];parent=(int16_t)i;x=y=0;depth=0;
        do {
            if (parent<0 || parent>=c->count || ++depth>WIDGET_DEPTH)
                return WIDGET_BAD_ARGUMENT;
            x+=(int32_t)c->objects[parent].ob_x;
            y+=(int32_t)c->objects[parent].ob_y;
            parent=c->parent[parent];
        } while (parent!=-1);
        border=o->ob_type==G_BUTTON ? 1+!!(o->ob_flags&EXIT)+!!(o->ob_flags&DEFAULT) : 0;
        parent=c->parent[i];
        if (parent>=0 && (o->ob_x<border || o->ob_y<border ||
            (int32_t)o->ob_x+o->ob_width+border>c->objects[parent].ob_width ||
            (int32_t)o->ob_y+o->ob_height+border>c->objects[parent].ob_height))
            return WIDGET_BAD_ARGUMENT;
        right=x+(int32_t)o->ob_width+border;
        bottom=y+(int32_t)o->ob_height+border;
        if (x<border || y<border || right>width || bottom>height)
            return WIDGET_BAD_ARGUMENT;
        if ((o->ob_flags&RBUTTON) && (o->ob_state&SELECTED)) {
            for (j=1;j<i;j++)
                if (c->parent[j]==c->parent[i] && (c->objects[j].ob_flags&RBUTTON) &&
                    (c->objects[j].ob_state&SELECTED)) return WIDGET_BAD_ARGUMENT;
        }
        /* Cache all admitted nodes, including initially hidden subtrees. */
        o->ob_flags &= ~HIDETREE;
    }
    WidgetCurrent=c;orderCount=0;
    everyobj(c->objects,ROOT,NIL,remember,0,0,WIDGET_DEPTH-1);
    if (orderCount!=c->count) return WIDGET_BAD_ARGUMENT;
    for (i=0;i<c->count;i++) c->objects[i].ob_flags=p->objects[i].flags;
    for (i=0;i<c->count;i++) {
        j=c->order[i];
        if (c->objects[j].ob_type==G_BUTTON && !(c->objects[j].ob_state&DISABLED) &&
            WidgetVisible(c,j)) { c->focus=(int16_t)j;break; }
    }
    return WIDGET_OK;
}

int16_t WidgetHit(struct WidgetContext *c,int16_t x,int16_t y)
{
    WidgetCurrent=c;
    return ob_find(c->objects,ROOT,WIDGET_DEPTH-1,x,y);
}

void WidgetDrawObject(struct WidgetContext *c,uint16_t index,int16_t x,int16_t y)
{
    WORD state;
    WidgetCurrent=c;
    if (index>=c->count || !WidgetVisible(c,index)) return;
    state=c->objects[index].ob_state;
    if (c->armed==index && c->pressed) c->objects[index].ob_state^=SELECTED;
    just_draw(c->objects,(WORD)index,x+c->bounds[index].g_x,y+c->bounds[index].g_y);
    c->objects[index].ob_state=(UWORD)state;
}
