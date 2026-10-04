/* Transactional retained state. One presenter serializes this staging context. */
#include "widgets.h"
static struct WidgetContext staging;
static uint32_t nextEpoch=1;

static void damage(struct WidgetPacket *p,const struct WidgetContext *c,uint16_t index)
{
    const GRECT *b=&c->bounds[index];
    const OBJECT *o=&c->objects[index];
    WORD border=o->ob_type==G_BUTTON ? 1+!!(o->ob_flags&EXIT)+!!(o->ob_flags&DEFAULT) : 0;
    WORD l=b->g_x-border,t=b->g_y-border,r=b->g_x+b->g_w+border,d=b->g_y+b->g_h+border;
    if (!p->changed) { p->left=l;p->top=t;p->right=r;p->bottom=d; }
    else {
        if (l<p->left) p->left=l;
        if (t<p->top) p->top=t;
        if (r>p->right) p->right=r;
        if (d>p->bottom) p->bottom=d;
    }
    p->changed=1;
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
uint16_t WidgetSet(struct WidgetContext *c,const struct WidgetTree *tree,struct WidgetPacket *p)
{
    uint16_t status;
    if (!nextEpoch) return WIDGET_EXHAUSTED;
    status=WidgetValidate(&staging,tree,p->bytes,p->width,p->height);
    if (status) return status;
    staging.epoch=nextEpoch++;staging.revision=1;
    memcpy(c,&staging,sizeof(*c));
    p->epoch=c->epoch;p->revision=c->revision;
    p->left=p->top=0;p->right=c->width;p->bottom=c->height;p->changed=1;
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
    if (!c || !c->epoch || !u || p->bytes!=sizeof(*u) ||
        u->count>WIDGET_PATCHES || u->textBytes>WIDGET_TEXT_BYTES) return WIDGET_BAD_ARGUMENT;
    if (u->epoch!=c->epoch || u->revision!=c->revision) return WIDGET_STALE;
    memcpy(&staging,c,sizeof(staging));
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
    if (c->revision==0xffffffffUL) { p->changed=0;return WIDGET_EXHAUSTED; }
    /* Any committed patch retires a gesture; it cannot overwrite press feedback. */
    WidgetDamage(p,c,c->armed);staging.armed=-1;staging.pressed=0;
    if (staging.focus<0 || !WidgetEligible(&staging,staging.focus))
        staging.focus=WidgetFirst(&staging);
    if (staging.focus!=c->focus) {
        WidgetDamage(p,c,c->focus);WidgetDamage(p,&staging,staging.focus);
    }
    staging.revision++;
    memcpy(c,&staging,sizeof(*c));
    p->epoch=c->epoch;p->revision=c->revision;
    return WIDGET_OK;
}
#ifdef WIDGET_STATE_TESTS
/* Fixture-only boundary injection; production has no epoch reset operation. */
void WidgetTestEpoch(uint32_t value) { nextEpoch=value; }
#endif
