/* Exec-owned FX 1.26 adapter. No donor startup, IRQ hooks or unbounded waits. */
#include <hardware/vbxe.h>
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
    UWORD start=DisplayTicks();
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

UWORD VbxeFence(struct VbxeDisplay *d)
{
    UWORD status=check(d);
    if (status!=DISPLAY_OK)
        return status;
    return idle()==DISPLAY_OK ? DISPLAY_OK : recover(d);
}

UWORD VbxeClose(struct VbxeDisplay *d)
{
    UWORD status=VbxeFence(d);
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
    UWORD i,n,offset,status=check(d);
    volatile UBYTE *window=(volatile UBYTE *)0x8000UL;
    if (status!=DISPLAY_OK)
        return status;
    if (!extent(address,buffer,bytes))
        return DISPLAY_BAD_ARGUMENT;
    status=VbxeFence(d);
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

UWORD VbxeWrite(struct VbxeDisplay *d, ULONG address, const void *source, UWORD bytes)
{ return transfer(d,address,(UBYTE *)source,bytes,0); }
UWORD VbxeRead(struct VbxeDisplay *d, ULONG address, void *destination, UWORD bytes)
{ return transfer(d,address,destination,bytes,1); }

static void word(UBYTE *p,UWORD value)
{ p[0]=(UBYTE)value; p[1]=(UBYTE)(value>>8); }

/* A bounded constant-source fill BCB, suitable for adapter tests and clearing.
 * General raster primitives are integrated with the selected VDI in G4. */
UWORD VbxeFill(struct VbxeDisplay *d, ULONG address, UWORD stride,
               UWORD bytes, UWORD rows, UBYTE value)
{
    UBYTE bcb[21];
    UWORD i,status=check(d);
    ULONG end;
    if (status!=DISPLAY_OK) return status;
    if (!bytes || bytes>512 || !rows || rows>256 || stride<bytes || stride>4095)
        return DISPLAY_BAD_ARGUMENT;
    end=address+(ULONG)(rows-1)*stride+bytes;
    if (address>=VBXE_SCREEN_BYTES || end>VBXE_SCREEN_BYTES)
        return DISPLAY_BAD_ARGUMENT;
    status=VbxeFence(d);
    if (status!=DISPLAY_OK) return status;
    for (i=0;i<21;i++) bcb[i]=0;
    bcb[5]=bcb[11]=1;
    word(bcb+6,(UWORD)address);
    bcb[8]=(UBYTE)(address>>16);
    word(bcb+9,stride);
    word(bcb+12,bytes-1);
    bcb[14]=(UBYTE)(rows-1);
    bcb[16]=value;
    status=VbxeWrite(d,VBXE_BCB,bcb,21);
    if (status!=DISPLAY_OK) return status;
    REG(0xd650)=d->blit[0]=(UBYTE)VBXE_BCB;
    REG(0xd651)=d->blit[1]=(UBYTE)(VBXE_BCB>>8);
    REG(0xd652)=d->blit[2]=(UBYTE)(VBXE_BCB>>16);
    REG(BUSY)=1;
    return VbxeFence(d);
}

UWORD VbxeWaitFrame(struct VbxeDisplay *d)
{
    UBYTE previous,current;
    UWORD start,status=VbxeFence(d);
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

UWORD VbxeShow(struct VbxeDisplay *d)
{
    /* HR, 240 rows, 320 bytes/row, palette 1, normal width, priority over ANTIC. */
    static const UBYTE xdl[12]={0x62,0x18,239,0,0,0,0x40,1,0x11,0xff,4,0x80};
    UWORD status=VbxeWrite(d,VBXE_XDL,xdl,sizeof(xdl));
    if (status!=DISPLAY_OK) return status;
    status=VbxeWaitFrame(d);
    if (status!=DISPLAY_OK) return status;
    REG(0xd641)=d->xdl[0]=(UBYTE)VBXE_XDL;
    REG(0xd642)=d->xdl[1]=(UBYTE)(VBXE_XDL>>8);
    REG(0xd643)=d->xdl[2]=(UBYTE)(VBXE_XDL>>16);
    REG(0xd640)=d->video=5;
    return DISPLAY_OK;
}

UWORD VbxePalette(struct VbxeDisplay *d, const UBYTE *rgb)
{
    UWORD i,status=check(d);
    if (status!=DISPLAY_OK) return status;
    if (!extent(0,rgb,48)) return DISPLAY_BAD_ARGUMENT;
    status=VbxeFence(d);
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

UWORD VbxePresent(struct VbxeDisplay *d)
{
    UBYTE rgb[48];
    UWORD i,status;
    for (i=0;i<48;i++) rgb[i]=(UBYTE)((i/3)*17);
    status=VbxePalette(d,rgb);
    return status==DISPLAY_OK ? VbxeShow(d) : status;
}

UWORD VbxeBlit(struct VbxeDisplay *d, ULONG source, UWORD sourceStride,
               ULONG destination, UWORD destinationStride, UWORD bytes, UWORD rows,
               UBYTE andMask, UBYTE xorMask, UBYTE mode)
{
    UBYTE bcb[21];
    UWORD i,status=check(d);
    if (status!=DISPLAY_OK) return status;
    if (!bytes || bytes>512 || !rows || rows>256 || mode>6 ||
        sourceStride>4095 || destinationStride>4095 ||
        source>=VBXE_VRAM_BYTES || destination>=VBXE_VRAM_BYTES ||
        (ULONG)(rows-1)*sourceStride+bytes>VBXE_VRAM_BYTES-source ||
        (ULONG)(rows-1)*destinationStride+bytes>VBXE_VRAM_BYTES-destination)
        return DISPLAY_BAD_ARGUMENT;
    for (i=0;i<21;i++) bcb[i]=0;
    word(bcb,(UWORD)source); bcb[2]=(UBYTE)(source>>16);
    word(bcb+3,sourceStride); bcb[5]=1;
    word(bcb+6,(UWORD)destination); bcb[8]=(UBYTE)(destination>>16);
    word(bcb+9,destinationStride); bcb[11]=1;
    word(bcb+12,bytes-1); bcb[14]=(UBYTE)(rows-1);
    bcb[15]=andMask; bcb[16]=xorMask; bcb[20]=mode;
    status=VbxeWrite(d,VBXE_BCB,bcb,21);
    if (status!=DISPLAY_OK) return status;
    REG(0xd650)=d->blit[0]=(UBYTE)VBXE_BCB;
    REG(0xd651)=d->blit[1]=(UBYTE)(VBXE_BCB>>8);
    REG(0xd652)=d->blit[2]=(UBYTE)(VBXE_BCB>>16);
    REG(BUSY)=1;
    return VbxeFence(d);
}
