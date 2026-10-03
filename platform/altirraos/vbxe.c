/* Exec-owned FX 1.26 adapter. No donor startup, IRQ hooks or unbounded waits. */
#include "vbxe-internal.h"
#include <hardware/vbxe-upload.h>
#include <proto/exec.h>

#define REG(address) (*(volatile UBYTE *)(ULONG)(address))
#define BUSY 0xd653UL
#define VCOUNT 0xd40bUL
void EXEC_CALL _VbxeMap(struct VbxeMapState *map);

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
    if (d->mutated) {
        REG(0xd640)=d->video=0;
        map(d,0,0);
        REG(0xd654)=d->irq=0;
        REG(0xd641)=d->xdl[0]=0;
        REG(0xd642)=d->xdl[1]=0;
        REG(0xd643)=d->xdl[2]=0;
        REG(0xd650)=d->blit[0]=0;
        REG(0xd651)=d->blit[1]=0;
        REG(0xd652)=d->blit[2]=0;
        REG(0xd644)=d->color=0;
        REG(0xd645)=d->palette=0;
        REG(0x230)=(UBYTE)d->savedList;
        REG(0x231)=(UBYTE)(d->savedList>>8);
        REG(0xd402)=(UBYTE)d->savedList;
        REG(0xd403)=(UBYTE)(d->savedList>>8);
        REG(0x22f)=d->savedDma;
        REG(0xd400)=d->savedDma;
        d->mutated=0;
    }
    d->lastError=result;
    if (DisplayRelease(&d->lease)!=DISPLAY_OK)
        DisplayResetRequired();
    return result;
}

static UWORD recover(struct VbxeDisplay *d)
{
    REG(BUSY)=0;                 /* FX stop, never assume the write completed DMA. */
    if (idle()!=DISPLAY_OK) {
        d->lastError=DISPLAY_DEVICE_FAULT;
        DisplayFault(&d->lease);
        DisplayResetRequired(); /* Does not return, acknowledge or free storage. */
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
    /* Authorization is a launch precondition, separate from identity reads. */
    if (!DisplayBaseline() || REG(0xd640)!=0x10 || REG(0xd641)!=0x26)
        return retire(d,DISPLAY_UNSUPPORTED);
    /* Readable checks catch contradictions; they do not infer write-only state. */
    if ((REG(BUSY)&3) || REG(0xd65e) || REG(0xd65f) || REG(0xd654))
        return retire(d,DISPLAY_UNSUPPORTED);
    d->savedDma=REG(0x22f);
    d->savedList=(UWORD)REG(0x230)|((UWORD)REG(0x231)<<8);
    d->mutated=1;
    REG(0x22f)=0;
    REG(0xd400)=0;
    REG(0xd640)=d->video=0;
    REG(0xd654)=d->irq=0;
    map(d,0,0);
    d->lastError=DISPLAY_OK;
    return DisplayActivate(&d->lease);
}

UWORD VbxeOwnerFence(struct VbxeDisplay *d)
{
    return idle()==DISPLAY_OK ? DISPLAY_OK : recover(d);
}

UWORD VbxeOwnerClose(struct VbxeDisplay *d)
{
    UWORD status=VbxeOwnerFence(d);
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

/* Only fully validated records reach this synchronous driver-owned launch.
 * CopyRect validates its entire geometry once, then constructs bounded records
 * on its retained owner's stack. Public lists validate every supplied record. */
static UWORD submit(struct VbxeDisplay *d,const UBYTE *records,UWORD count)
{
    struct VbxeUpload upload;
    upload.records=(ULONG)records; upload.count=count;
    if (idle()!=DISPLAY_OK) return recover(d);
    map(d,(UBYTE)(0x80|(VBXE_BCB>>12)),0x88);
    _VbxeUpload(&upload);
    map(d,0,0);
    REG(0xd650)=d->blit[0]=(UBYTE)VBXE_BCB;
    REG(0xd651)=d->blit[1]=(UBYTE)(VBXE_BCB>>8);
    REG(0xd652)=d->blit[2]=(UBYTE)(VBXE_BCB>>16);
    REG(BUSY)=1;
    return idle()==DISPLAY_OK ? DISPLAY_OK : recover(d);
}

/* Validate every record before mapping or starting DMA. Upload directly into
 * the private arena so no second 4 KiB CPU buffer or mutable client chain is
 * needed. Only the owner may enter; the caller retains the CPU records. */
UWORD VbxeOwnerSubmit(struct VbxeDisplay *d,const UBYTE *records,UWORD count)
{
    const UBYTE *p;
    ULONG work=0;
    UWORD i,n,bytes,rows;
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

UWORD VbxeOwnerCopyRect(struct VbxeDisplay *d,const struct VbxeCopy *c)
{
    ULONG src,dst,srcEnd,dstEnd;
    UWORD bytes,rows,n,limit,backwards,i,status;
    WORD ss,ds;
    UBYTE bcb[21];
    if (!extent(0,c,sizeof(*c)) || !surface(&c->source) || !surface(&c->destination))
        return DISPLAY_BAD_ARGUMENT;
    if ((c->sourceX|c->destinationX|c->width)&1 || c->width>1024 ||
        c->sourceX>c->source.width || c->sourceY>c->source.height ||
        c->destinationX>c->destination.width || c->destinationY>c->destination.height ||
        c->width>c->source.width-c->sourceX || c->height>c->source.height-c->sourceY ||
        c->width>c->destination.width-c->destinationX || c->height>c->destination.height-c->destinationY)
        return DISPLAY_BAD_ARGUMENT;
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
    limit=(UWORD)VBXE_LIST_WORK/(bytes*2);
    if (limit>VBXE_CHUNK_ROWS) limit=VBXE_CHUNK_ROWS;
    for (i=0;i<21;i++) bcb[i]=0;
    word(bcb+3,(UWORD)ss); word(bcb+9,(UWORD)ds);
    bcb[5]=bcb[11]=backwards ? 255 : 1;
    word(bcb+12,bytes-1); bcb[15]=255;
    while (rows) {
        n=rows<limit ? rows : limit;
        word(bcb,(UWORD)src); bcb[2]=(UBYTE)(src>>16);
        word(bcb+6,(UWORD)dst); bcb[8]=(UBYTE)(dst>>16);
        bcb[14]=(UBYTE)(n-1);
        status=submit(d,bcb,1);
        if (status!=DISPLAY_OK) return status;
        rows-=n;
        if (rows) { src+=(LONG)n*ss; dst+=(LONG)n*ds; }
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
    REG(0xd641)=d->xdl[0]=(UBYTE)VBXE_XDL;
    REG(0xd642)=d->xdl[1]=(UBYTE)(VBXE_XDL>>8);
    REG(0xd643)=d->xdl[2]=(UBYTE)(VBXE_XDL>>16);
    REG(0xd640)=d->video=VBXE_VIDEO_XDL|VBXE_VIDEO_OPAQUE_ZERO;
    return DISPLAY_OK;
}

UWORD VbxeOwnerPalette(struct VbxeDisplay *d, const UBYTE *rgb)
{
    UWORD i,status;
    if (!extent(0,rgb,48)) return DISPLAY_BAD_ARGUMENT;
    status=VbxeOwnerFence(d);
    if (status!=DISPLAY_OK) return status;
    REG(0xd645)=d->palette=1;
    REG(0xd644)=d->color=0;
    for (i=0;i<16;i++) {
        REG(0xd646)=*rgb++;
        REG(0xd647)=*rgb++;
        REG(0xd648)=*rgb++;
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

UWORD VbxeSubmit(struct VbxeDisplay *display, const UBYTE *records, UWORD count)
{
    UWORD status=check(display);
    if (status!=DISPLAY_OK) return status;
    return VbxeOwnerSubmit(display,records,count);
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
