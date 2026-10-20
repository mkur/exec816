#include "aes-private.h"
#include <proto/dos.h>
#include <proto/exec.h>
#include <string.h>

/* Standard RSC words/longs are big endian, independent of host pointer order. */
struct ExecAESResource {
    ULONG bytes;
    UWORD trees,objects,strings;
    OBJECT *object;
    OBJECT **tree;
    char **string;
};
static UWORD word(const UBYTE *p) { return ((UWORD)p[0]<<8)|p[1]; }
static ULONG wide(const UBYTE *p) { return ((ULONG)word(p)<<16)|word(p+2); }
static void native_plane(UBYTE *p,UWORD bytes)
{
    UWORD i;
    for (i=0;i<bytes;i+=2) *(UWORD *)(p+i)=word(p+i);
}
/* Standard RSC colour planes contain hardware colour bits, plane zero first.
 * Transform once into packed device pixels, using load-time upper-RAM scratch. */
static void colour_data(UBYTE *data,UWORD bytes,UBYTE *scratch)
{
    UWORD i,bit,at=0;
    UBYTE pixel,pair=0;
    for (i=0;i<bytes;++i) for (bit=128;bit;bit>>=1) {
        pixel=(data[i]&bit ? 1:0) | (data[bytes+i]&bit ? 2:0) |
            (data[bytes*2+i]&bit ? 4:0) | (data[bytes*3+i]&bit ? 8:0);
        if (bit&0x55) scratch[at++]=pair|pixel;
        else pair=pixel<<4;
    }
    memcpy(data,scratch,bytes*4);
}
/* Atari's version-4 extension: length/table/terminator, index table ending in
 * -1, then CICONBLKs with inline mono data/mask/text and colour forms. Keep the
 * first four-plane form (or mono fallback), and fix only the admitted copy. */
static WORD colour_icons(UBYTE *data,UWORD bytes,UWORD classic,UWORD *table,UWORD *count)
{
    ULONG at,forms,form,end,block,selected,span;
    UWORD i,j,width,height,planeBytes,planes;
    UBYTE *scratch=NULL,*p;
    CICONBLK *icon;
    CICON *colour;
    WORD result=0;
    *count=0;*table=0;
    if ((classic&1) || (ULONG)classic+12>bytes || wide(data+classic)!=bytes ||
        wide(data+classic+8)) return 0;
    at=wide(data+classic+4);
    if (!at || at==0xffffffffUL) return 1;
    if ((at&1) || at<(ULONG)classic+12 || at>bytes) return 0;
    *table=(UWORD)at;
    while (at+4<=bytes && wide(data+at)!=0xffffffffUL && *count<256) {
        ++*count;at+=4;
    }
    if (at+4>bytes || wide(data+at)!=0xffffffffUL) return 0;
    at+=4;
    for (i=0;i<*count;++i) {
        if (at+38>bytes) goto finish;
        block=at;p=data+at;icon=(CICONBLK *)p;
        width=word(p+22);height=word(p+24);forms=wide(p+34);
        if (!width || width>64 || (width&15) || !height || height>64 || forms>256) goto finish;
        planeBytes=(width>>3)*height;
        at+=38;
        if (at+(ULONG)planeBytes*2+12>bytes) goto finish;
        icon->monoblk.ib_pdata=(ULONG)(data+at);native_plane(data+at,planeBytes);at+=planeBytes;
        icon->monoblk.ib_pmask=(ULONG)(data+at);native_plane(data+at,planeBytes);at+=planeBytes;
        icon->monoblk.ib_ptext=(ULONG)(data+at);at+=12;
        for (j=12;j<34;j+=2) *(UWORD *)(p+j)=word(p+j);
        icon->mainlist=0;
        for (form=0;form<forms;++form) {
            if (at+22>bytes) goto finish;
            colour=(CICON *)(data+at);planes=word(data+at);selected=wide(data+at+10);
            if (!planes || planes>16) goto finish;
            span=(ULONG)planeBytes*(planes+1);
            end=at+22+span*(selected ? 2:1);
            if (end>bytes) goto finish;
            at+=22;
            if (planes==4 && !icon->mainlist) {
                if (!scratch) {
                    scratch=AllocMem(2048,MEMF_PUBLIC);
                    if (!scratch) { result=-1;goto finish; }
                }
                colour->num_planes=4;colour->next_res=0;
                colour->col_data=(ULONG)(data+at);
                colour->col_mask=(ULONG)(data+at+planeBytes*4);
                colour_data(data+at,planeBytes,scratch);
                native_plane(data+at+planeBytes*4,planeBytes);
                colour->sel_data=colour->sel_mask=0;
                if (selected) {
                    colour->sel_data=(ULONG)(data+at+span);
                    colour->sel_mask=(ULONG)(data+at+span+planeBytes*4);
                    colour_data(data+at+span,planeBytes,scratch);
                    native_plane(data+at+span+planeBytes*4,planeBytes);
                }
                icon->mainlist=(ULONG)colour;
            }
            at=end;
        }
        *(ULONG *)(data+*table+(ULONG)i*4)=(ULONG)(data+block);
    }
    result=1;
finish:
    if (scratch) FreeMem(scratch,2048);
    return result;
}
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
/* Fix shared planes once. Earlier ICONBLKs already hold native addresses;
 * their descriptor offsets still identify the same original file bytes. */
static void icon_plane(UBYTE *data,UWORD iconAt,UWORD index,ULONG offset,UWORD count)
{
    UWORD j;
    const ICONBLK *previous=(const ICONBLK *)(data+iconAt);
    ULONG address=(ULONG)(data+offset);
    UBYTE *p=data+offset;
    for (j=0;j<index;++j)
        if (previous[j].ib_pmask==address || previous[j].ib_pdata==address) return;
    for (j=0;j<count;++j,p+=2) *(UWORD *)p=word(p);
}
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
    if (type!=R_TREE && type!=R_STRING && type!=R_FRSTR) c->diagnostic=AES_UNSUPPORTED;
    else if (!c->resource || (UWORD)index>=(type==R_TREE ? c->resource->trees:c->resource->strings)) c->diagnostic=AES_MALFORMED;
    else if (type==R_TREE) *address=c->resource->tree[index];
    else if (type==R_STRING) *address=c->resource->string[index];
    else *address=&c->resource->string[index];
    c->busy=0; return *address!=NULL;
}

WORD rsrc_load(const char *name)
{
    struct ExecAESContext *c=ExecAESContext();
    struct ExecAESResource *r=NULL;
    BPTR file;
    UBYTE header[36],*data,*p;
    LONG length,got,at=0;
    UWORD bytes,classic,version,colours=0,colourAt=0,objects,trees,objectAt,treeAt,tedAt,teds,iconAt,icons,stringAt,strings,i,j,type,editable,capacity;
    ULONG spec,offset;
    OBJECT *o;
    TEDINFO *ted;
    WORD okay=0;
    if (!c || !ExecAESEnter(c)) return 0;
    file=Open(name,MODE_OLDFILE);
    if (!file) { c->diagnostic=AES_RESOURCE; c->busy=0; return 0; }
    if (Read(file,header,36)!=36) goto malformed;
    bytes=word(header+34); objectAt=word(header+2); treeAt=word(header+18);
    classic=bytes;version=word(header);
    objects=word(header+20); trees=word(header+22);
    tedAt=word(header+4);teds=word(header+24);
    iconAt=word(header+6);icons=word(header+26);
    stringAt=word(header+10);strings=word(header+30);
    if ((version!=0 && version!=4) || bytes<36 || !objects || objects>256 || !trees || trees>16 ||
        strings>256 || (strings && (stringAt<36 || (stringAt&1) || (ULONG)stringAt+(ULONG)strings*4>bytes)) ||
        teds>256 || icons>256 || word(header+28) ||
        (icons && (iconAt<36 || (iconAt&1) || (ULONG)iconAt+(ULONG)icons*34>bytes)) ||
        (teds && (tedAt<36 || (ULONG)tedAt+(ULONG)teds*28>bytes)) ||
        objectAt<36 || treeAt<36 || (ULONG)objectAt+(ULONG)objects*24>bytes ||
        (ULONG)treeAt+(ULONG)trees*4>bytes) goto malformed;
    if (Seek(file,0,OFFSET_END)<0) goto malformed;
    length=Seek(file,0,OFFSET_BEGINNING);
    if ((!version && length!=bytes) || (version && (length<bytes || length>65535))) goto malformed;
    bytes=(UWORD)length;
    r=AllocMem((ULONG)sizeof(*r)+bytes,MEMF_PUBLIC);
    if (!r) { c->diagnostic=AES_RESOURCE; goto finish; }
    r->bytes=(ULONG)sizeof(*r)+bytes; r->trees=trees; r->objects=objects;r->strings=strings;
    data=(UBYTE *)(r+1);r->object=(OBJECT *)(data+objectAt);r->tree=(OBJECT **)(data+treeAt);
    r->string=(char **)(data+stringAt);
    while (at<bytes) {
        got=Read(file,data+at,(LONG)bytes-at);
        if (got<=0) goto malformed;
        at+=got;
    }
    if (version) {
        WORD status=colour_icons(data,bytes,classic,&colourAt,&colours);
        if (!status) goto malformed;
        if (status<0) { c->diagnostic=AES_RESOURCE;goto finish; }
    }
    /* Validate all file extents before relocation. No repeated draw-time audit. */
    for (i=0;i<strings;++i) {
        offset=wide(data+stringAt+(ULONG)i*4);
        if (offset>=bytes) goto malformed;
        for (j=0;j<=255 && offset+j<bytes && data[offset+j];++j) {}
        if (j>255 || offset+j>=bytes) goto malformed;
    }
    for (i=0;i<objects;++i) {
        p=data+objectAt+(ULONG)i*24;type=word(p+6);spec=wide(p+12);
        if (type!=G_BOX && type!=G_IBOX && type!=G_STRING && type!=G_TITLE && type!=G_BUTTON &&
            type!=G_TEXT && type!=G_BOXTEXT && type!=G_FTEXT && type!=G_FBOXTEXT && type!=G_ICON && type!=G_CICON)
            goto malformed;
        if (word(p+8)&~(SELECTABLE|DEFAULT|EXIT|EDITABLE|RBUTTON|LASTOB|HIDETREE) ||
            word(p+10)&~(SELECTED|CHECKED|DISABLED)) goto malformed;
        if ((word(p+8)&EDITABLE) && type!=G_TEXT && type!=G_BOXTEXT &&
            type!=G_FTEXT && type!=G_FBOXTEXT) goto malformed;
        if (type==G_STRING || type==G_TITLE || type==G_BUTTON) {
            if (!string_size(data,bytes,spec)) goto malformed;
        } else if (type==G_TEXT || type==G_BOXTEXT || type==G_FTEXT || type==G_FBOXTEXT) {
            if (spec<tedAt || spec>=(ULONG)tedAt+(ULONG)teds*28 ||
                (spec-tedAt)%28) goto malformed;
        } else if (type==G_ICON) {
            if (spec<iconAt || spec>=(ULONG)iconAt+(ULONG)icons*34 ||
                (spec-iconAt)%34) goto malformed;
        } else if (type==G_CICON && spec>=colours) {
            goto malformed;
        }
    }
    for (i=0;i<icons;++i) {
        UWORD width,height,planeBytes;
        p=data+iconAt+(ULONG)i*34;width=word(p+22);height=word(p+24);
        if (!width || width>64 || (width&15) || !height || height>64 ||
            !string_size(data,bytes,wide(p+8))) goto malformed;
        planeBytes=(width>>3)*height;
        for (j=0;j<2;++j) {
            offset=wide(p+j*4);
            if (offset<36 || (offset&1) || offset>bytes || planeBytes>bytes-offset)
                goto malformed;
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
    for (i=0;i<icons;++i) {
        ULONG mask,bits;
        UWORD count;
        ICONBLK *ib;
        p=data+iconAt+(ULONG)i*34;ib=(ICONBLK *)p;
        mask=wide(p);bits=wide(p+4);count=(word(p+22)>>4)*word(p+24);
        icon_plane(data,iconAt,i,mask,count);
        if (bits!=mask) icon_plane(data,iconAt,i,bits,count);
        ib->ib_pmask=(ULONG)(data+mask);ib->ib_pdata=(ULONG)(data+bits);
        ib->ib_ptext=(ULONG)(data+wide(p+8));
        for (j=12;j<34;j+=2) *(UWORD *)(p+j)=word(p+j);
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
        o->ob_spec=o->ob_type==G_CICON ? *(ULONG *)(data+colourAt+spec*4):
            (o->ob_type==G_BOX || o->ob_type==G_IBOX) ? spec:(ULONG)(data+spec);
    }
    for (i=0;i<trees;++i) {
        offset=wide(data+treeAt+(ULONG)i*4);r->tree[i]=(OBJECT *)(data+offset);
    }
    for (i=0;i<strings;++i) {
        offset=wide(data+stringAt+(ULONG)i*4);r->string[i]=(char *)(data+offset);
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
