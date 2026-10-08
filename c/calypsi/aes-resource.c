#include "aes-private.h"
#include <proto/dos.h>
#include <proto/exec.h>

/* Standard RSC words/longs are big endian, independent of host pointer order. */
struct ExecAESResource {
    ULONG bytes;
    UWORD trees,objects;
    OBJECT *object;
    OBJECT **tree;
};
static UWORD word(const UBYTE *p) { return ((UWORD)p[0]<<8)|p[1]; }
static ULONG wide(const UBYTE *p) { return ((ULONG)word(p)<<16)|word(p+2); }
/* Resource admission only; drawing trusts the relocated caller-owned strings. */
static UWORD string_size(const UBYTE *data,UWORD bytes,ULONG offset)
{
    UWORD n=0;
    if (offset>=bytes) return 0;
    while (n<=63 && offset+n<bytes && data[offset+n]) ++n;
    return n<=63 && offset+n<bytes ? n+1:0;
}
static UWORD text_capacity(const UBYTE *data,UWORD bytes,const UBYTE *ted)
{
    ULONG offset=wide(ted);
    UWORD capacity=word(ted+24),n=0;
    if (!capacity || capacity>128 || offset>=bytes || capacity>bytes-offset) return 0;
    while (n<capacity && data[offset+n]) ++n;
    return n<capacity ? capacity:0;
}
static WORD coordinate(UWORD n) { return (WORD)((n&255)<<3)+(BYTE)(n>>8); }
WORD rsrc_obfix(OBJECT *tree,WORD obj)
{
    tree[obj].ob_x=coordinate(tree[obj].ob_x);
    tree[obj].ob_y=coordinate(tree[obj].ob_y);
    tree[obj].ob_width=coordinate(tree[obj].ob_width);
    tree[obj].ob_height=coordinate(tree[obj].ob_height);
    return 1;
}
void ExecAESResourceFree(struct ExecAESContext *c)
{
    if (c->resource) { FreeMem(c->resource,c->resource->bytes); c->resource=NULL; }
}
WORD rsrc_free(void)
{
    struct ExecAESContext *c=ExecAESContext();
    if (!c || !ExecAESEnter(c)) return 0;
    ExecAESResourceFree(c); c->busy=0; return 1;
}
WORD rsrc_gaddr(WORD type,WORD index,void **address)
{
    struct ExecAESContext *c=ExecAESContext();
    if (!c || !ExecAESEnter(c)) return 0;
    *address=NULL;
    if (type!=R_TREE) c->diagnostic=AES_UNSUPPORTED;
    else if (!c->resource || (UWORD)index>=c->resource->trees) c->diagnostic=AES_MALFORMED;
    else *address=c->resource->tree[index];
    c->busy=0; return *address!=NULL;
}

WORD rsrc_load(const char *name)
{
    struct ExecAESContext *c=ExecAESContext();
    struct ExecAESResource *r=NULL;
    BPTR file;
    UBYTE header[36],*data,*p;
    LONG length,got,at=0;
    UWORD bytes,objects,trees,objectAt,treeAt,tedAt,teds,i,j,type,editable,capacity;
    ULONG spec,offset;
    OBJECT *o;
    TEDINFO *ted;
    WORD okay=0;
    if (!c || !ExecAESEnter(c)) return 0;
    file=Open(name,MODE_OLDFILE);
    if (!file) { c->diagnostic=AES_RESOURCE; c->busy=0; return 0; }
    if (Read(file,header,36)!=36) goto malformed;
    bytes=word(header+34); objectAt=word(header+2); treeAt=word(header+18);
    objects=word(header+20); trees=word(header+22);
    tedAt=word(header+4);teds=word(header+24);
    if (word(header)!=0 || bytes<36 || !objects || objects>256 || !trees || trees>8 ||
        teds>256 || word(header+26) || word(header+28) ||
        (teds && (tedAt<36 || (ULONG)tedAt+(ULONG)teds*28>bytes)) ||
        objectAt<36 || treeAt<36 || (ULONG)objectAt+(ULONG)objects*24>bytes ||
        (ULONG)treeAt+(ULONG)trees*4>bytes) goto malformed;
    if (Seek(file,0,OFFSET_END)<0) goto malformed;
    length=Seek(file,0,OFFSET_BEGINNING);
    if (length!=bytes) goto malformed;
    r=AllocMem((ULONG)sizeof(*r)+bytes,MEMF_PUBLIC);
    if (!r) { c->diagnostic=AES_RESOURCE; goto finish; }
    r->bytes=(ULONG)sizeof(*r)+bytes; r->trees=trees; r->objects=objects;
    data=(UBYTE *)(r+1);r->object=(OBJECT *)(data+objectAt);r->tree=(OBJECT **)(data+treeAt);
    while (at<bytes) {
        got=Read(file,data+at,(LONG)bytes-at);
        if (got<=0) goto malformed;
        at+=got;
    }
    /* Validate all file extents before relocation. No repeated draw-time audit. */
    for (i=0;i<objects;++i) {
        p=data+objectAt+(ULONG)i*24;type=word(p+6);spec=wide(p+12);
        if (type!=G_BOX && type!=G_IBOX && type!=G_STRING && type!=G_TITLE && type!=G_BUTTON &&
            type!=G_TEXT && type!=G_BOXTEXT && type!=G_FTEXT && type!=G_FBOXTEXT)
            goto malformed;
        if (word(p+8)&~(SELECTABLE|DEFAULT|EXIT|EDITABLE|RBUTTON|LASTOB|HIDETREE) ||
            word(p+10)&~(SELECTED|DISABLED)) goto malformed;
        if ((word(p+8)&EDITABLE) && type!=G_TEXT && type!=G_BOXTEXT &&
            type!=G_FTEXT && type!=G_FBOXTEXT) goto malformed;
        if (type==G_STRING || type==G_TITLE || type==G_BUTTON) {
            if (!string_size(data,bytes,spec)) goto malformed;
        } else if (type==G_TEXT || type==G_BOXTEXT || type==G_FTEXT || type==G_FBOXTEXT) {
            if (spec<tedAt || spec>=(ULONG)tedAt+(ULONG)teds*28 ||
                (spec-tedAt)%28) goto malformed;
        }
    }
    for (i=0;i<teds;++i) {
        p=data+tedAt+(ULONG)i*28;
        editable=0;
        for (j=0;j<objects;++j) {
            const UBYTE *object=data+objectAt+(ULONG)j*24;
            if ((word(object+8)&EDITABLE) && wide(object+12)==(ULONG)(p-data)) { editable=1;break; }
        }
        capacity=editable ? text_capacity(data,bytes,p):string_size(data,bytes,wide(p));
        if (!capacity || !string_size(data,bytes,wide(p+4)) ||
            !string_size(data,bytes,wide(p+8))) goto malformed;
        /* Retain the admitted capacity for relocation, in file byte order. */
        p[24]=capacity>>8;p[25]=capacity;
    }
    for (i=0;i<trees;++i) {
        offset=wide(data+treeAt+(ULONG)i*4);
        if (offset<objectAt || offset>=(ULONG)objectAt+(ULONG)objects*24 ||
            (offset-objectAt)%24) goto malformed;
        for (j=0;j<GEM_OBJECT_LIMIT && offset+(ULONG)(j+1)*24<=(ULONG)objectAt+(ULONG)objects*24;++j)
            if (word(data+offset+(ULONG)j*24+8)&LASTOB) break;
        if (j==GEM_OBJECT_LIMIT || offset+(ULONG)(j+1)*24>(ULONG)objectAt+(ULONG)objects*24) goto malformed;
    }
    /* Fix each TED once, including records shared by several objects. */
    for (i=0;i<teds;++i) {
        p=data+tedAt+(ULONG)i*28;ted=(TEDINFO *)p;
        ted->te_txtlen=word(p+24);
        ted->te_tmplen=string_size(data,bytes,wide(p+4));
        ted->te_ptext=(ULONG)(data+wide(p));
        ted->te_ptmplt=(ULONG)(data+wide(p+4));
        ted->te_pvalid=(ULONG)(data+wide(p+8));
        ted->te_font=word(p+12);ted->te_fontid=word(p+14);
        ted->te_just=word(p+16);ted->te_color=word(p+18);
        ted->te_fontsize=word(p+20);ted->te_thickness=word(p+22);
    }
    for (i=0;i<objects;++i) {
        p=data+objectAt+(ULONG)i*24;o=(OBJECT *)p;spec=wide(p+12);
        o->ob_next=word(p);o->ob_head=word(p+2);o->ob_tail=word(p+4);
        o->ob_type=word(p+6);o->ob_flags=word(p+8);o->ob_state=word(p+10);
        o->ob_x=coordinate(word(p+16));o->ob_y=coordinate(word(p+18));
        o->ob_width=coordinate(word(p+20));o->ob_height=coordinate(word(p+22));
        o->ob_spec=(o->ob_type==G_BOX || o->ob_type==G_IBOX) ? spec:(ULONG)(data+spec);
    }
    for (i=0;i<trees;++i) {
        offset=wide(data+treeAt+(ULONG)i*4);r->tree[i]=(OBJECT *)(data+offset);
    }
    okay=1; goto finish;
malformed:
    c->diagnostic=AES_MALFORMED;
finish:
    if (!Close(file)) { c->diagnostic=AES_RESOURCE; okay=0; }
    if (okay) { ExecAESResourceFree(c); c->resource=r; }
    else if (r) FreeMem(r,r->bytes);
    c->busy=0; return okay;
}

BOOL ExecAESResources(struct ExecAESContext *c,AESPB *pb)
{
    WORD op=pb->control[0],ins=0,ain=0,aout=0;
    void *address;
    switch (op) {
    case 110: ain=1; break;
    case 111: break;
    case 112: ins=2; aout=1; break;
    case 114: ins=1; ain=1; break;
    default:return FALSE;
    }
    pb->int_out[0]=0;
    if (pb->control[1]!=ins || pb->control[2]!=1 || pb->control[3]!=ain || pb->control[4]!=aout) {
        c->diagnostic=AES_MALFORMED; return TRUE;
    }
    switch (op) {
    case 110:pb->int_out[0]=rsrc_load((const char *)(ULONG)pb->addr_in[0]);break;
    case 111:pb->int_out[0]=rsrc_free();break;
    case 112:
        pb->int_out[0]=rsrc_gaddr(pb->int_in[0],pb->int_in[1],&address);
        pb->addr_out[0]=(LONG)(ULONG)address;break;
    case 114:pb->int_out[0]=rsrc_obfix((OBJECT *)(ULONG)pb->addr_in[0],pb->int_in[0]);break;
    }
    return TRUE;
}
