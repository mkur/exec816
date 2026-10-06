/* Transactional retained state. One presenter serializes this staging context. */
#include "widgets.h"
#include <stddef.h>
static struct WidgetContext staging;
static uint32_t nextEpoch=1;

/* Copy bounded damage to the bridge; no pointer into a context survives.
 * Containment removes duplicate work without joining separated controls.
 * Overflow falls back to the whole client, including every earlier change. */
static void rectangle(struct WidgetPacket *p,const struct WidgetContext *c,
                       WORD left,WORD top,WORD right,WORD bottom)
{
    uint16_t i=0,j;
    struct WidgetDamageRect *r;
    if (left>=right || top>=bottom) return;
    while (i<p->damageCount) {
        r=&p->damage[i];
        if (r->left<=left && r->top<=top && r->right>=right && r->bottom>=bottom) return;
        if (left<=r->left && top<=r->top && right>=r->right && bottom>=r->bottom) {
            --p->damageCount;
            for (j=i;j<p->damageCount;j++) p->damage[j]=p->damage[j+1];
        } else ++i;
    }
    if (p->damageCount==WIDGET_DAMAGE_RECTS) {
        p->damageCount=0;left=top=0;right=c->width;bottom=c->height;
    }
    r=&p->damage[p->damageCount++];
    r->left=left;r->top=top;r->right=right;r->bottom=bottom;
    p->changed=1;
}
static void damage(struct WidgetPacket *p,const struct WidgetContext *c,uint16_t index)
{
    const GRECT *b=&c->bounds[index];
    const OBJECT *o=&c->objects[index];
    WORD border=o->ob_type==G_BUTTON ? 1+!!(o->ob_flags&EXIT)+!!(o->ob_flags&DEFAULT) : 0;
    rectangle(p,c,b->g_x-border,b->g_y-border,
              b->g_x+b->g_w+border,b->g_y+b->g_h+border);
}
uint16_t WidgetEligible(const struct WidgetContext *c,uint16_t index)
{
    return index<c->count && c->objects[index].ob_type==G_BUTTON &&
        !(c->objects[index].ob_state&DISABLED) && WidgetVisible(c,index);
}
int16_t WidgetFirst(const struct WidgetContext *c)
{
    uint16_t i;
    for (i=0;i<c->count;i++) if (WidgetEligible(c,c->order[i])) return c->order[i];
    return -1;
}
void WidgetDamage(struct WidgetPacket *p,const struct WidgetContext *c,int16_t index)
{
    if (index>=0 && index<c->count) damage(p,c,(uint16_t)index);
}
void WidgetFocusDamage(struct WidgetPacket *p,const struct WidgetContext *c,int16_t index)
{
    const GRECT *b;
    if (index<0 || index>=c->count || !WidgetVisible(c,index)) return;
    b=&c->bounds[index];
    rectangle(p,c,b->g_x+3,b->g_y+b->g_h-3,b->g_x+b->g_w-3,b->g_y+b->g_h-2);
}
uint16_t WidgetSet(struct WidgetContext *c,const struct WidgetTree *tree,struct WidgetPacket *p)
{
    uint16_t status;
    p->changed=p->damageCount=0;
    if (!nextEpoch) return WIDGET_EXHAUSTED;
    status=WidgetValidate(&staging,tree,p->bytes,p->width,p->height);
    if (status) return status;
    staging.epoch=nextEpoch++;staging.revision=1;
    memcpy(c,&staging,sizeof(*c));
    p->epoch=c->epoch;p->revision=c->revision;
    rectangle(p,c,0,0,c->width,c->height);
    return WIDGET_OK;
}
uint16_t WidgetRead(const struct WidgetContext *c,struct WidgetSnapshot *out,uint16_t bytes)
{
    uint16_t i;
    if (!c || !c->epoch || !out || bytes!=sizeof(*out)) return WIDGET_BAD_ARGUMENT;
    memset(out,0,sizeof(*out));
    out->epoch=c->epoch;out->revision=c->revision;out->count=c->count;out->focus=c->focus;
    for (i=0;i<c->count;i++) {
        out->objects[i].state=c->objects[i].ob_state;out->objects[i].flags=c->objects[i].ob_flags;
    }
    return WIDGET_OK;
}
uint16_t WidgetUpdate(struct WidgetContext *c,const struct WidgetUpdate *u,struct WidgetPacket *p)
{
    uint16_t i,j,k,n,used=0,length,labels=0,changed=0,matched;
    const struct WidgetChange *v;
    const char *label;
    OBJECT *o;
    p->changed=p->damageCount=0;
    if (!c || !c->epoch || !u || p->bytes!=sizeof(*u) ||
        u->count>WIDGET_PATCHES || u->textBytes>WIDGET_TEXT_BYTES) return WIDGET_BAD_ARGUMENT;
    if (u->epoch!=c->epoch || u->revision!=c->revision) return WIDGET_STALE;
    /* Only admitted objects/text are live. Copy their immutable geometry for
       validation and damage, without moving the unused capacity on each click.
       Staging remains private until every check below has succeeded. */
    memcpy(&staging,c,offsetof(struct WidgetContext,objects)+c->count*sizeof(OBJECT));
    memcpy(staging.text,c->text,c->textBytes);
    memcpy(staging.parent,c->parent,c->count*sizeof(c->parent[0]));
    memcpy(staging.order,c->order,c->count*sizeof(c->order[0]));
    memcpy(staging.bounds,c->bounds,c->count*sizeof(c->bounds[0]));
    for (i=0;i<u->count;i++) {
        v=&u->changes[i];
        if (v->object>=c->count || !v->mask || (v->mask&~7)) return WIDGET_BAD_ARGUMENT;
        for (j=0;j<i;j++) if (u->changes[j].object==v->object) return WIDGET_BAD_ARGUMENT;
        o=&staging.objects[v->object];
        if (v->mask&WIDGET_PATCH_STATE) {
            if (o->ob_type!=G_BUTTON || (v->state&~(SELECTED|DISABLED)) ||
                ((o->ob_flags&EXIT) && (v->state&SELECTED))) return WIDGET_BAD_ARGUMENT;
            o->ob_state=v->state;
        }
        if (v->mask&WIDGET_PATCH_HIDDEN) {
            if (v->hidden>1 || !v->object) return WIDGET_BAD_ARGUMENT;
            o->ob_flags=(o->ob_flags&~HIDETREE)|(v->hidden ? HIDETREE : 0);
        }
        if (v->mask&WIDGET_PATCH_LABEL) {
            if ((o->ob_type!=G_BUTTON && o->ob_type!=G_STRING) ||
                v->length>WIDGET_LABEL_MAX || v->length*8>o->ob_width ||
                v->offset>=u->textBytes || v->length>=u->textBytes-v->offset ||
                u->text[v->offset+v->length]) return WIDGET_BAD_ARGUMENT;
            for (j=0;j<v->length;j++) if (!u->text[v->offset+j]) return WIDGET_BAD_ARGUMENT;
            labels=1;
        }
    }
    for (i=1;i<c->count;i++)
        if ((staging.objects[i].ob_flags&RBUTTON) && (staging.objects[i].ob_state&SELECTED))
            for (j=1;j<i;j++)
                if (c->parent[j]==c->parent[i] && (staging.objects[j].ob_flags&RBUTTON) &&
                    (staging.objects[j].ob_state&SELECTED)) return WIDGET_BAD_ARGUMENT;
    if (labels) {
        for (i=0;i<c->count;i++) {
            o=&staging.objects[i];
            if (o->ob_type!=G_STRING && o->ob_type!=G_BUTTON) continue;
            label=c->text+(uint16_t)c->objects[i].ob_spec;
            for (j=0;j<u->count;j++)
                if (u->changes[j].object==i && (u->changes[j].mask&WIDGET_PATCH_LABEL))
                    label=(const char *)u->text+u->changes[j].offset;
            length=(uint16_t)strlen(label)+1;matched=0;
            /* Deduplicate so shared labels do not expand the admitted capacity. */
            for (k=0;k<i;k++) {
                if (staging.objects[k].ob_type!=G_STRING && staging.objects[k].ob_type!=G_BUTTON) continue;
                n=(uint16_t)staging.objects[k].ob_spec;
                if (!strcmp(staging.text+n,label)) { o->ob_spec=n;matched=1;break; }
            }
            if (!matched) {
                if (length>WIDGET_TEXT_BYTES-used) return WIDGET_BAD_ARGUMENT;
                o->ob_spec=used;memcpy(staging.text+used,label,length);used+=length;
            }
        }
        staging.textBytes=used;
    }
    p->changed=0;
    for (i=0;i<c->count;i++) {
        o=&staging.objects[i];
        if (o->ob_state!=c->objects[i].ob_state || o->ob_flags!=c->objects[i].ob_flags ||
            ((o->ob_type==G_BUTTON || o->ob_type==G_STRING) &&
             strcmp(staging.text+(uint16_t)o->ob_spec,c->text+(uint16_t)c->objects[i].ob_spec))) {
            damage(p,c,i);changed=1;
        }
    }
    if (!changed) { p->epoch=c->epoch;p->revision=c->revision;return WIDGET_OK; }
    if (c->revision==0xffffffffUL) { p->changed=p->damageCount=0;return WIDGET_EXHAUSTED; }
    /* Any committed patch retires a gesture; it cannot overwrite press feedback. */
    WidgetDamage(p,c,c->armed);staging.armed=-1;staging.pressed=0;
    if (staging.focus<0 || !WidgetEligible(&staging,staging.focus))
        staging.focus=WidgetFirst(&staging);
    if (staging.focus!=c->focus) {
        WidgetFocusDamage(p,&staging,staging.focus);WidgetFocusDamage(p,c,c->focus);
    }
    staging.revision++;
    /* A patch cannot change geometry, ordering or object count. Publish only
       the header, live objects and admitted text; inactive bytes stay unused. */
    memcpy(c,&staging,offsetof(struct WidgetContext,objects)+c->count*sizeof(OBJECT));
    memcpy(c->text,staging.text,staging.textBytes);
    p->epoch=c->epoch;p->revision=c->revision;
    return WIDGET_OK;
}
#ifdef WIDGET_STATE_TESTS
/* Fixture-only boundary injection; production has no epoch reset operation. */
void WidgetTestEpoch(uint32_t value) { nextEpoch=value; }
#endif
