/* Exec-owned FX adapter with detected I/O page and bounded completion. */
#include "vbxe-internal.h"
#include <hardware/vbxe-upload.h>
#include <hardware/vbxe-notify.h>
#include <hardware/boot-diagnostics.h>
#include <proto/exec.h>

#define REG(address) (*(volatile UBYTE *)(ULONG)(address))
#define BUSY (registerBase+0x53UL)
#define VCOUNT 0xd40bUL
void EXEC_CALL _VbxeMap(struct VbxeMapState *map);
/* One hardware owner; IDs are never reused, including across close/reopen. */
static ULONG operationSequence;
static ULONG registerBase;

static UWORD check(struct VbxeDisplay *d)
{
    if ((ULONG)d < 0x10000UL || (ULONG)d > 0x1000000UL-sizeof(*d))
        return DISPLAY_INVALID_OWNER;
    return DisplayCheck(&d->lease);
}

static void map(struct VbxeDisplay *d, UBYTE bank, UBYTE control)
{
    d->map.pendingBank=bank;
    d->map.pendingControl=control;
    _VbxeMap(&d->map);
}

/* Unsigned subtraction handles a tick rollover while a wait is outstanding. */
static UWORD idle(void)
{
    UWORD start;
    if (!(REG(BUSY)&3)) return DISPLAY_OK;
    start=DisplayTicks();
    while (REG(BUSY)&3) {
        if ((UWORD)(DisplayTicks()-start)>=VBXE_WAIT_TICKS)
            return DISPLAY_DEVICE_FAULT;
    }
    return DISPLAY_OK;
}

static UWORD retire(struct VbxeDisplay *d, UWORD result)
{
    if (DisplayBeginRelease(&d->lease)!=DISPLAY_OK)
        DisplayResetRequired();
    if (VbxeNotifyClose(&d->lease)!=DISPLAY_OK)
        DisplayResetRequired();
    if (d->mutated) {
        REG(registerBase+0x40UL)=d->video=0;
        map(d,0,0);
        REG(registerBase+0x41UL)=d->xdl[0]=0;
        REG(registerBase+0x42UL)=d->xdl[1]=0;
        REG(registerBase+0x43UL)=d->xdl[2]=0;
        REG(registerBase+0x50UL)=d->blit[0]=0;
        REG(registerBase+0x51UL)=d->blit[1]=0;
        REG(registerBase+0x52UL)=d->blit[2]=0;
        REG(registerBase+0x44UL)=d->color=0;
        REG(registerBase+0x45UL)=d->palette=0;
        REG(0x230)=(UBYTE)d->savedList;
        REG(0x231)=(UBYTE)(d->savedList>>8);
        REG(0xd402)=(UBYTE)d->savedList;
        REG(0xd403)=(UBYTE)(d->savedList>>8);
        REG(0x22f)=d->savedDma;
        REG(0xd400)=d->savedDma;
        d->mutated=0;
    }
    d->lastError=result;
    d->operationPending=0;
    if (DisplayRelease(&d->lease)!=DISPLAY_OK)
        DisplayResetRequired();
    return result;
}

static UWORD recover(struct VbxeDisplay *d)
{
    REG(BUSY)=0;                 /* FX stop, never assume the write completed DMA. */
    if (idle()!=DISPLAY_OK) {
        d->lastError=DISPLAY_DEVICE_FAULT;
        DisplayAccessFault(1);
        DisplayResetRequired(); /* Does not return, acknowledge or free storage. */
    }
    if (DisplayDelegated()) {
        d->lastError=DISPLAY_DEVICE_FAULT;
        if (d->operationPending) VbxeNotifyReset();
        d->operationPending=0;
        DisplayAccessFault(0);
        return DISPLAY_DEVICE_FAULT;
    }
    return retire(d,DISPLAY_DEVICE_FAULT);
}

UWORD VbxeOpen(struct VbxeDisplay *d)
{
    UWORD status;
    if ((ULONG)d < 0x10000UL || (ULONG)d > 0x1000000UL-sizeof(*d))
        return DISPLAY_INVALID_OWNER;
    status=DisplayAcquire(&d->lease,DISPLAY_VBXE);
    if (status!=DISPLAY_OK)
        return status;
    d->mutated=0;
    d->operationPending=0;
    d->operationId=0;
    registerBase=VbxeHardwareBase();
    if (!registerBase) {
        VbxeBootReport(BOOT_DIAG_NO_VBXE,((UWORD)REG(0xd640UL)<<8)|REG(0xd740UL));
        return retire(d,DISPLAY_UNSUPPORTED);
    }
    d->map.pageOffset=(UWORD)(registerBase-0xd600UL);
    if (REG(registerBase+0x40UL)!=0x10) {
        VbxeBootReport(BOOT_DIAG_BAD_CORE,REG(registerBase+0x40UL));
        return retire(d,DISPLAY_UNSUPPORTED);
    }
    /* Authorization is a launch precondition, separate from identity reads. */
    if (!DisplayBaseline()) {
        VbxeBootReport(BOOT_DIAG_BAD_BASELINE,0);
        return retire(d,DISPLAY_UNSUPPORTED);
    }
    /* Readable checks catch contradictions; they do not infer write-only state. */
    if ((REG(BUSY)&3) || REG(registerBase+0x5eUL) || REG(registerBase+0x5fUL) || REG(registerBase+0x54UL)) {
        VbxeBootReport(BOOT_DIAG_BUSY,REG(BUSY));
        return retire(d,DISPLAY_UNSUPPORTED);
    }
    status=VbxeNotifyOpen(&d->lease);
    if (status!=DISPLAY_OK) return retire(d,status);
    d->savedDma=REG(0x22f);
    d->savedList=(UWORD)REG(0x230)|((UWORD)REG(0x231)<<8);
    d->mutated=1;
    REG(0x22f)=0;
    REG(0xd400)=0;
    REG(registerBase+0x40UL)=d->video=0;
    map(d,0,0);
    d->lastError=DISPLAY_OK;
    return DisplayActivate(&d->lease);
}

UWORD VbxeOwnerFence(struct VbxeDisplay *d)
{
    UWORD status;
    if (d->operationPending) {
        do { status=VbxeOwnerPoll(d,d->operationId); }
        while (status==DISPLAY_BUSY);
        return status;
    }
    return idle()==DISPLAY_OK ? DISPLAY_OK : recover(d);
}

UWORD VbxeOwnerClose(struct VbxeDisplay *d)
{
    UWORD status;
    if (DisplayDelegated()) return DISPLAY_BUSY;
    status=VbxeOwnerFence(d);
    if (status!=DISPLAY_OK)
        return status;
    return retire(d,DISPLAY_OK);
}

/* CPU buffers may be upper data or caller stack, never the mapped aperture.
 * Actual allocation/lifetime remains the ordinary shared-address-space contract. */
static UWORD extent(ULONG address, const void *buffer, UWORD bytes)
{
    ULONG p=(ULONG)buffer;
    return address<=VBXE_VRAM_BYTES && (ULONG)bytes<=VBXE_VRAM_BYTES-address
        && p!=0 && p<=0xffffffUL && (ULONG)bytes<=0x1000000UL-p
        && !(p<0x9000UL && p+(ULONG)bytes>0x8000UL);
}

static UWORD transfer(struct VbxeDisplay *d, ULONG address, UBYTE *buffer,
                       UWORD bytes, UWORD reading)
{
    UWORD i,n,offset,status;
    volatile UBYTE *window=(volatile UBYTE *)0x8000UL;
    if (!extent(address,buffer,bytes))
        return DISPLAY_BAD_ARGUMENT;
    status=VbxeOwnerFence(d);
    if (status!=DISPLAY_OK)
        return status;
    while (bytes) {
        offset=(UWORD)(address&0xfff);
        n=0x1000-offset;
        if (n>bytes) n=bytes;
        map(d,(UBYTE)(0x80|(address>>12)),0x88);
        for (i=0;i<n;i++) {
            if (reading) buffer[i]=window[offset+i];
            else window[offset+i]=buffer[i];
        }
        buffer+=n;
        address+=n;
        bytes-=n;
    }
    map(d,0,0);
    return DISPLAY_OK;
}

UWORD VbxeOwnerWrite(struct VbxeDisplay *d, ULONG address, const void *source, UWORD bytes)
{ return transfer(d,address,(UBYTE *)source,bytes,0); }
UWORD VbxeOwnerRead(struct VbxeDisplay *d, ULONG address, void *destination, UWORD bytes)
{ return transfer(d,address,destination,bytes,1); }

static void word(UBYTE *p,UWORD value)
{ p[0]=(UBYTE)value; p[1]=(UBYTE)(value>>8); }

/* Half-open full-operation extents; command storage is never raster data. */
UWORD VbxeBlitExtent(ULONG address,UWORD stride,UWORD bytes,UWORD rows)
{
    ULONG end;
    if (!bytes || bytes>512 || !rows || rows>256 || stride>4095 ||
        address>=VBXE_VRAM_BYTES) return 0;
    /* Sixteen-row chunks fit a 16-bit row displacement even at stride 4095.
     * Keep the widened fallback for public callers with taller rectangles. */
    end=rows<=16 ? address+(UWORD)((rows-1)*stride)+bytes
                 : address+(ULONG)(rows-1)*stride+bytes;
    return end<=VBXE_VRAM_BYTES &&
        !(address<VBXE_BCB+VBXE_BCB_BYTES && end>VBXE_BCB);
}

static UWORD getword(const UBYTE *p)
{ return (UWORD)p[0]|((UWORD)p[1]<<8); }
static ULONG address(const UBYTE *p)
{ return (ULONG)getword(p)|((ULONG)p[2]<<16); }

/* Hardware Y increments are signed 13-bit, relative to each row's start.
 * Accept only canonical sign extension so no caller bits silently disappear.
 * Keep the frequent positive path narrow; descending endpoints use LONG. */
static UWORD stepped(ULONG at,WORD pitch,BYTE x,UWORD bytes,UWORD rows)
{
    LONG low=(LONG)at,high=(LONG)at,dy,dx;
    if (x==1 && pitch>=0) return VbxeBlitExtent(at,(UWORD)pitch,bytes,rows);
    if ((x!=1 && x!=-1) || pitch< -4096 || pitch>4095 || at>=VBXE_VRAM_BYTES)
        return 0;
    dy=(LONG)(rows-1)*pitch; dx=(LONG)(bytes-1)*x;
    if (dy<0) low+=dy; else high+=dy;
    if (dx<0) low+=dx; else high+=dx;
    return low>=0 && high<(LONG)VBXE_VRAM_BYTES &&
        !(low<(LONG)(VBXE_BCB+VBXE_BCB_BYTES) && high>=(LONG)VBXE_BCB);
}

/* Records reach this synchronous driver-owned launch after raw-list validation
 * or construction by an admitted internal producer with established geometry
 * and list/work bounds. Both paths keep the same fences and recovery. */
static void start(struct VbxeDisplay *d)
{
    REG(registerBase+0x50UL)=d->blit[0]=(UBYTE)VBXE_BCB;
    REG(registerBase+0x51UL)=d->blit[1]=(UBYTE)(VBXE_BCB>>8);
    REG(registerBase+0x52UL)=d->blit[2]=(UBYTE)(VBXE_BCB>>16);
    REG(BUSY)=1;
}

static void upload(struct VbxeDisplay *d,const UBYTE *records,UWORD count)
{
    struct VbxeUpload upload;
    upload.records=(ULONG)records; upload.count=count;
    map(d,(UBYTE)(0x80|(VBXE_BCB>>12)),0x88);
    _VbxeUpload(&upload);
    map(d,0,0);
}

static void launch(struct VbxeDisplay *d,const UBYTE *records,UWORD count)
{
    upload(d,records,count);
    start(d);
}

static UWORD submit(struct VbxeDisplay *d,const UBYTE *records,UWORD count)
{
    UWORD status=VbxeOwnerFence(d);
    if (status!=DISPLAY_OK) return status;
    launch(d,records,count);
    return VbxeOwnerFence(d);
}

/* The descriptor proves every possible byte glyph stays in the atlas and
 * every destination stays on screen. Unlike Submit, no caller-supplied raw
 * records are trusted. Each generated list has a fill and at most 32 glyphs:
 * 33 records / 693 bytes, at most 5120 bus accesses, within existing limits.
 * The optional final fill adds one record and at most 3072 bus accesses.
 * All glyphs (including blank masks) follow the same checked geometry. */
static UWORD text_run(struct VbxeDisplay *d,ULONG font,UWORD x,UWORD y,
    const UBYTE *text,UWORD count,UBYTE ink,UBYTE paper,
    const struct VbxeTextFill *fill)
{
    struct VbxeTextUpload upload;
    UWORD status,n;
    if ((x&1) || x>640 || y>232 || count>(640-x)/8 ||
        font<VBXE_SCREEN_BYTES || font>VBXE_VRAM_BYTES-8192 ||
        (font<VBXE_BCB+VBXE_BCB_BYTES && font+8192>VBXE_BCB) ||
        (ink&15)!=(ink>>4) || (paper&15)!=(paper>>4) ||
        (count && !extent(0,text,count))) return DISPLAY_BAD_ARGUMENT;
    if (fill && (!count || (fill->x&1) || (fill->width&1) ||
        !fill->width || !fill->height || fill->x>=640 || fill->y>=240 ||
        fill->width>640-fill->x || fill->height>240-fill->y ||
        (ULONG)fill->width*fill->height>VBXE_TEXT_FILL_WORK ||
        (fill->value&15)!=(fill->value>>4))) return DISPLAY_BAD_ARGUMENT;
    if (!count) return DISPLAY_OK;
    status=VbxeOwnerFence(d);
    if (status!=DISPLAY_OK) return status;
    upload.text=(ULONG)text;
    upload.font=font;
    upload.destination=(ULONG)y*320+x/2;
    upload.ink=ink;
    upload.paper=paper;
    if (fill) {
        upload.fillDestination=(ULONG)fill->y*320+fill->x/2;
        upload.fillBytes=fill->width/2;
        upload.fillValue=fill->value;
    }
    while (count) {
        n=count>32 ? 32 : count;
        upload.count=n;
        upload.fillRows=fill && count==n ? fill->height : 0;
        map(d,(UBYTE)(0x80|(VBXE_BCB>>12)),0x88);
        _VbxeTextUpload(&upload);
        map(d,0,0);
        start(d);
        status=VbxeOwnerFence(d);
        if (status!=DISPLAY_OK) return status;
        upload.text+=n;
        upload.destination+=n*4;
        count-=n;
    }
    return DISPLAY_OK;
}

UWORD VbxeOwnerText(struct VbxeDisplay *d,ULONG font,UWORD x,UWORD y,
    const UBYTE *text,UWORD count,UBYTE ink,UBYTE paper)
{
    return text_run(d,font,x,y,text,count,ink,paper,0);
}

UWORD VbxeOwnerTextFill(struct VbxeDisplay *d,ULONG font,UWORD x,UWORD y,
    const UBYTE *text,UWORD count,UBYTE ink,UBYTE paper,const struct VbxeTextFill *fill)
{
    if (!fill) return DISPLAY_BAD_ARGUMENT;
    return text_run(d,font,x,y,text,count,ink,paper,fill);
}

/* A completion record outlives each poll. No borrowed descriptor survives
 * launch, and no other list may overwrite the arena while pending is set. */
static UWORD complete_operation(struct VbxeDisplay *d)
{
    VbxeNotifyReset();
    d->operationPending=0;
    d->lastError=DISPLAY_OK;
    return DISPLAY_OK;
}

UWORD VbxeOwnerPoll(struct VbxeDisplay *d,ULONG id)
{
    UWORD event;
    if (!id || id!=d->operationId) return DISPLAY_BAD_ARGUMENT;
    if (!d->operationPending) return d->lastError;
    event=VbxeNotifyState(id);
    if (!(REG(BUSY)&3)) return complete_operation(d);
    /* A terminal notice followed by BUSY contradicts the completed list.
     * Recover now: that notice has already retired its watchdog demand. */
    if (event==VBXE_NOTIFY_DONE || event==VBXE_NOTIFY_EXPIRED ||
        (UWORD)(DisplayTicks()-d->operationStarted)>=VBXE_WAIT_TICKS)
        return recover(d);
    return DISPLAY_BUSY;
}

/* The only asynchronous publication path. Typed callers have already copied
 * and validated their complete list before entering; no descriptor is borrowed. */
static UWORD launch_async(struct VbxeDisplay *d,const UBYTE *records,UWORD count,ULONG *id)
{
    UWORD status;
    if (d->operationPending) return DISPLAY_BUSY;
    if (operationSequence==0xffffffffUL) return DISPLAY_UNSUPPORTED;
    if (REG(BUSY)&3) return recover(d);
    d->operationId=++operationSequence;
    d->operationStarted=DisplayTicks();
    d->lastError=DISPLAY_BUSY;
    d->operationPending=1;
    *id=d->operationId;
    upload(d,records,count);
    status=VbxeNotifyArm(d->operationId);
    if (status!=DISPLAY_OK) return recover(d);
    return DISPLAY_OK;
}

UWORD VbxeOwnerScrollStart(struct VbxeDisplay *d,const struct VbxeCopy *c,
                           UBYTE value,ULONG *id)
{
    ULONG source,destination,bottom;
    UWORD bytes,i,count,rows;
    UBYTE records[42],*fill;
    if (d->operationPending) return DISPLAY_BUSY;
    if (!extent(0,c,sizeof(*c)) || !extent(0,id,sizeof(*id)))
        return DISPLAY_BAD_ARGUMENT;
    if (operationSequence==0xffffffffUL) return DISPLAY_UNSUPPORTED;
    if (c->source.offset || c->destination.offset ||
        c->source.pitch!=320 || c->destination.pitch!=320 ||
        c->source.width!=640 || c->destination.width!=640 ||
        c->source.height!=240 || c->destination.height!=240 ||
        c->sourceX!=c->destinationX || c->sourceX>640 ||
        (c->sourceX|c->width)&1 || !c->width || c->width>640-c->sourceX ||
        c->sourceY>240 || c->sourceY<=c->destinationY ||
        c->height>240-c->sourceY)
        return DISPLAY_BAD_ARGUMENT;
    rows=c->sourceY-c->destinationY;
    if (rows&7) return DISPLAY_BAD_ARGUMENT;
    bytes=c->width/2;
    source=(ULONG)c->sourceY*320+c->sourceX/2;
    destination=(ULONG)c->destinationY*320+c->destinationX/2;
    bottom=destination+(ULONG)c->height*320;
    if ((c->height && (!VbxeBlitExtent(source,320,bytes,c->height) ||
        !VbxeBlitExtent(destination,320,bytes,c->height))) ||
        !VbxeBlitExtent(bottom,320,bytes,rows)) return DISPLAY_BAD_ARGUMENT;
    for (i=0;i<42;i++) records[i]=0;
    word(records,(UWORD)source); records[2]=(UBYTE)(source>>16);
    word(records+3,320); records[5]=1;
    word(records+6,(UWORD)destination); records[8]=(UBYTE)(destination>>16);
    word(records+9,320); records[11]=1;
    word(records+12,bytes-1); records[14]=(UBYTE)(c->height-1);
    records[15]=255;
    fill=records+21;
    fill[5]=1;
    word(fill+6,(UWORD)bottom); fill[8]=(UBYTE)(bottom>>16);
    word(fill+9,320); fill[11]=1;
    word(fill+12,bytes-1); fill[14]=(UBYTE)(rows-1); fill[16]=value;
    count=c->height ? 2 : 1;
    return launch_async(d,count==2 ? records : fill,count,id);
}

/* Validate every record before mapping or starting DMA. Upload directly into
 * the private arena so no second 4 KiB CPU buffer or mutable client chain is
 * needed. Only the owner may enter; the caller retains the CPU records. */
UWORD VbxeSubmit(struct VbxeDisplay *d,const UBYTE *records,UWORD count)
{
    const UBYTE *p;
    ULONG work=0;
    UWORD i,n,bytes,rows,status=check(d);
    if (status!=DISPLAY_OK) return status;
    if (!count) return DISPLAY_OK;
    if (count>VBXE_LIST_RECORDS || !extent(0,records,count*21))
        return DISPLAY_BAD_ARGUMENT;
    p=records;
    for (i=0;i<count;i++,p+=21) {
        n=getword(p+12);
        if (n>=512 || p[17] || p[18] || p[19] || p[20]>6)
            return DISPLAY_BAD_ARGUMENT;
        bytes=n+1; rows=(UWORD)p[14]+1;
        if (!stepped(address(p),(WORD)getword(p+3),(BYTE)p[5],bytes,rows) ||
            !stepped(address(p+6),(WORD)getword(p+9),(BYTE)p[11],bytes,rows))
            return DISPLAY_BAD_ARGUMENT;
        /* At most 512*16*3 = 24576 here; narrowing does not discard carry. */
        work+=rows<=16 ? (UWORD)(bytes*rows*(p[20] ? 3 : 2))
                       : (ULONG)bytes*rows*(p[20] ? 3 : 2);
        if (work>VBXE_LIST_WORK) return DISPLAY_BAD_ARGUMENT;
    }
    return submit(d,records,count);
}

UWORD VbxeOwnerFill(struct VbxeDisplay *d, ULONG address, UWORD stride,
               UWORD bytes, UWORD rows, UBYTE value)
{
    if (!bytes || !rows || stride<bytes || !VbxeBlitExtent(address,stride,bytes,rows) ||
        address+(ULONG)(rows-1)*stride+bytes>VBXE_SCREEN_BYTES)
        return DISPLAY_BAD_ARGUMENT;
    return VbxeOwnerBlit(d,0,0,address,stride,bytes,rows,0,value,0);
}

static UWORD surface(const struct VbxeSurface *s)
{
    ULONG end;
    if (!s->width || !s->height || !s->pitch || s->pitch>4095 ||
        s->width>(UWORD)(s->pitch*2) || s->offset>=VBXE_VRAM_BYTES) return 0;
    end=s->offset+(ULONG)(s->height-1)*s->pitch+(s->width+1)/2;
    return end<=VBXE_VRAM_BYTES &&
        !(s->offset<VBXE_BCB+VBXE_BCB_BYTES && end>VBXE_BCB);
}

struct CopySetup {
    ULONG source,destination;
    WORD sourcePitch,destinationPitch;
    UWORD bytes,rows;
    UBYTE backwards;
};

static UWORD prepare_copy(const struct VbxeCopy *c,struct CopySetup *copy)
{
    ULONG src,dst,srcEnd,dstEnd;
    UWORD bytes,rows,backwards;
    WORD ss,ds;
    if (!extent(0,c,sizeof(*c)) || !surface(&c->source) || !surface(&c->destination))
        return DISPLAY_BAD_ARGUMENT;
    if ((c->sourceX|c->destinationX|c->width)&1 || c->width>1024 ||
        c->sourceX>c->source.width || c->sourceY>c->source.height ||
        c->destinationX>c->destination.width || c->destinationY>c->destination.height ||
        c->width>c->source.width-c->sourceX || c->height>c->source.height-c->sourceY ||
        c->width>c->destination.width-c->destinationX || c->height>c->destination.height-c->destinationY)
        return DISPLAY_BAD_ARGUMENT;
    copy->rows=0;
    if (!c->width || !c->height) return DISPLAY_OK;
    bytes=c->width/2; rows=c->height;
    ss=(WORD)c->source.pitch; ds=(WORD)c->destination.pitch;
    src=c->source.offset+(ULONG)c->sourceY*ss+c->sourceX/2;
    dst=c->destination.offset+(ULONG)c->destinationY*ds+c->destinationX/2;
    srcEnd=src+(ULONG)(rows-1)*ss+bytes;
    dstEnd=dst+(ULONG)(rows-1)*ds+bytes;
    backwards=src<dstEnd && dst<srcEnd;
    if (backwards && ss!=ds) return DISPLAY_BAD_ARGUMENT;
    if (src==dst && ss==ds) return DISPLAY_OK;
    backwards=backwards && dst>src;
    if (backwards) {
        src=srcEnd-1; dst=dstEnd-1;
        ss=-ss; ds=-ds;
    }
    copy->source=src; copy->destination=dst;
    copy->sourcePitch=ss; copy->destinationPitch=ds;
    copy->bytes=bytes; copy->rows=rows; copy->backwards=(UBYTE)backwards;
    return DISPLAY_OK;
}

static void copy_record(UBYTE *bcb,const struct CopySetup *c,UWORD rows)
{
    UWORD i;
    for (i=0;i<21;i++) bcb[i]=0;
    word(bcb,(UWORD)c->source); bcb[2]=(UBYTE)(c->source>>16);
    word(bcb+6,(UWORD)c->destination); bcb[8]=(UBYTE)(c->destination>>16);
    word(bcb+3,(UWORD)c->sourcePitch); word(bcb+9,(UWORD)c->destinationPitch);
    bcb[5]=bcb[11]=c->backwards ? 255 : 1;
    word(bcb+12,c->bytes-1); bcb[14]=(UBYTE)(rows-1); bcb[15]=255;
}

UWORD VbxeOwnerCopyStart(struct VbxeDisplay *d,const struct VbxeCopy *c,ULONG *id)
{
    struct CopySetup copy;
    UBYTE bcb[21];
    UWORD status;
    if (d->operationPending) return DISPLAY_BUSY;
    if (!extent(0,id,sizeof(*id))) return DISPLAY_BAD_ARGUMENT;
    status=prepare_copy(c,&copy);
    if (status!=DISPLAY_OK) return status;
    if (c->width>640 || c->height>240) return DISPLAY_BAD_ARGUMENT;
    /* Empty/identical copies neither consume an identity nor start hardware. */
    if (!copy.rows) { *id=0; return DISPLAY_OK; }
    copy_record(bcb,&copy,copy.rows);
    return launch_async(d,bcb,1,id);
}

UWORD VbxeOwnerCopyRect(struct VbxeDisplay *d,const struct VbxeCopy *c)
{
    struct CopySetup copy;
    UWORD rows,n,limit,status;
    UBYTE bcb[21];
    status=prepare_copy(c,&copy);
    if (status!=DISPLAY_OK || !copy.rows) return status;
    rows=copy.rows;
    limit=(UWORD)VBXE_LIST_WORK/(copy.bytes*2);
    if (limit>VBXE_CHUNK_ROWS) limit=VBXE_CHUNK_ROWS;
    while (rows) {
        n=rows<limit ? rows : limit;
        copy_record(bcb,&copy,n);
        status=submit(d,bcb,1);
        if (status!=DISPLAY_OK) return status;
        rows-=n;
        if (rows) {
            copy.source+=(LONG)n*copy.sourcePitch;
            copy.destination+=(LONG)n*copy.destinationPitch;
        }
    }
    return DISPLAY_OK;
}

UWORD VbxeOwnerWaitFrame(struct VbxeDisplay *d)
{
    UBYTE previous,current;
    UWORD start,status=VbxeOwnerFence(d);
    if (status!=DISPLAY_OK) return status;
    start=DisplayTicks();
    previous=REG(VCOUNT);
    for (;;) {
        current=REG(VCOUNT);
        if (current<previous) return DISPLAY_OK;
        previous=current;
        if ((UWORD)(DisplayTicks()-start)>=VBXE_WAIT_TICKS)
            return recover(d);
    }
    return DISPLAY_OK;
}

UWORD VbxeOwnerShow(struct VbxeDisplay *d)
{
    /* HR, 240 rows, 320 bytes/row, palette 1, normal width, priority over ANTIC. */
    static const UBYTE xdl[12]={0x62,0x18,239,0,0,0,0x40,1,0x11,0xff,4,0x80};
    UWORD status=VbxeOwnerWrite(d,VBXE_XDL,xdl,sizeof(xdl));
    if (status!=DISPLAY_OK) return status;
    status=VbxeOwnerWaitFrame(d);
    if (status!=DISPLAY_OK) return status;
    REG(registerBase+0x41UL)=d->xdl[0]=(UBYTE)VBXE_XDL;
    REG(registerBase+0x42UL)=d->xdl[1]=(UBYTE)(VBXE_XDL>>8);
    REG(registerBase+0x43UL)=d->xdl[2]=(UBYTE)(VBXE_XDL>>16);
    REG(registerBase+0x40UL)=d->video=VBXE_VIDEO_XDL|VBXE_VIDEO_OPAQUE_ZERO;
    return DISPLAY_OK;
}

UWORD VbxeOwnerPalette(struct VbxeDisplay *d, const UBYTE *rgb)
{
    UWORD i,status;
    if (!extent(0,rgb,48)) return DISPLAY_BAD_ARGUMENT;
    status=VbxeOwnerFence(d);
    if (status!=DISPLAY_OK) return status;
    REG(registerBase+0x45UL)=d->palette=1;
    REG(registerBase+0x44UL)=d->color=0;
    for (i=0;i<16;i++) {
        REG(registerBase+0x46UL)=*rgb++;
        REG(registerBase+0x47UL)=*rgb++;
        REG(registerBase+0x48UL)=*rgb++;
        d->color++;
    }
    return DISPLAY_OK;
}

UWORD VbxeOwnerPresent(struct VbxeDisplay *d)
{
    UBYTE rgb[48];
    UWORD i,status;
    for (i=0;i<48;i++) rgb[i]=(UBYTE)((i/3)*17);
    status=VbxeOwnerPalette(d,rgb);
    return status==DISPLAY_OK ? VbxeOwnerShow(d) : status;
}

UWORD VbxeOwnerBlit(struct VbxeDisplay *d, ULONG source, UWORD sourceStride,
               ULONG destination, UWORD destinationStride, UWORD bytes, UWORD rows,
               UBYTE andMask, UBYTE xorMask, UBYTE mode)
{
    UBYTE bcb[21];
    UWORD i,n,limit,status;
    if (mode>6 || !VbxeBlitExtent(source,sourceStride,bytes,rows) ||
        !VbxeBlitExtent(destination,destinationStride,bytes,rows))
        return DISPLAY_BAD_ARGUMENT;
    limit=(UWORD)VBXE_LIST_WORK/(bytes*(mode ? 3 : 2));
    if (limit>VBXE_CHUNK_ROWS) limit=VBXE_CHUNK_ROWS;
    for (i=0;i<21;i++) bcb[i]=0;
    word(bcb+3,sourceStride); bcb[5]=1;
    word(bcb+9,destinationStride); bcb[11]=1;
    word(bcb+12,bytes-1);
    bcb[15]=andMask; bcb[16]=xorMask; bcb[20]=mode;
    while (rows) {
        n=rows<limit ? rows : limit;
        word(bcb,(UWORD)source); bcb[2]=(UBYTE)(source>>16);
        word(bcb+6,(UWORD)destination); bcb[8]=(UBYTE)(destination>>16);
        bcb[14]=(UBYTE)(n-1);
        status=submit(d,bcb,1);
        if (status!=DISPLAY_OK) return status;
        source+=(ULONG)n*sourceStride;
        destination+=(ULONG)n*destinationStride;
        rows-=n;
    }
    return DISPLAY_OK;
}

UWORD VbxeFence(struct VbxeDisplay *display)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerFence(display);
}

UWORD VbxeScrollStart(struct VbxeDisplay *display,const struct VbxeCopy *copy,
                      UBYTE value,ULONG *id)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerScrollStart(display,copy,value,id);
}

UWORD VbxeCopyStart(struct VbxeDisplay *display,const struct VbxeCopy *copy,ULONG *id)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerCopyStart(display,copy,id);
}

UWORD VbxePoll(struct VbxeDisplay *display,ULONG id)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerPoll(display,id);
}

UWORD VbxeClose(struct VbxeDisplay *display)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerClose(display);
}

UWORD VbxeWrite(struct VbxeDisplay *display, ULONG address, const void *source, UWORD bytes)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerWrite(display,address,source,bytes);
}

UWORD VbxeRead(struct VbxeDisplay *display, ULONG address, void *destination, UWORD bytes)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerRead(display,address,destination,bytes);
}

/* Internal producers own record validity and enforce capacity/work bounds
 * while constructing the list. Do not decode and validate it a second time. */
UWORD VbxeOwnerSubmit(struct VbxeDisplay *display, const UBYTE *records, UWORD count)
{
    if (!count) return DISPLAY_OK;
    return submit(display,records,count);
}

UWORD VbxeFill(struct VbxeDisplay *display, ULONG address, UWORD stride, UWORD bytes, UWORD rows, UBYTE value)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerFill(display,address,stride,bytes,rows,value);
}

UWORD VbxeCopyRect(struct VbxeDisplay *display, const struct VbxeCopy *copy)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerCopyRect(display,copy);
}

UWORD VbxeWaitFrame(struct VbxeDisplay *display)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerWaitFrame(display);
}

UWORD VbxeShow(struct VbxeDisplay *display)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerShow(display);
}

UWORD VbxePalette(struct VbxeDisplay *display, const UBYTE *rgb)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerPalette(display,rgb);
}

UWORD VbxePresent(struct VbxeDisplay *display)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerPresent(display);
}

UWORD VbxeBlit(struct VbxeDisplay *display, ULONG source, UWORD sourceStride,
               ULONG destination, UWORD destinationStride, UWORD bytes, UWORD rows,
               UBYTE andMask, UBYTE xorMask, UBYTE mode)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerBlit(display,source,sourceStride,destination,destinationStride,bytes,rows,andMask,xorMask,mode);
}

ULONG VbxeCompletionMask(struct VbxeDisplay *display)
{
    return check(display)==DISPLAY_OK ? VbxeNotifyMask(&display->lease) : 0;
}
