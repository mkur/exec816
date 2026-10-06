/* Exec adapter for the selected GEM renderer. No donor hardware routines link.
 * The donor's window pointers address a private upper-RAM staging page. Flushing
 * it uses the checked G3 transfer and always closes the CPU aperture. A fault
 * latches for the whole call: subsequent void donor callbacks cannot touch HW.
 * Lists are bounded by count and work; every dependency drains queued DMA.
 */
#include "gem-drawing.h"
#ifndef GEM_DRAWING_ONLY
#include "gem-vbxe.h"
#endif
#include "vbxe-internal.h"
#include <stdint.h>
#include <string.h>

extern uint16_t GemVdiOpen(int16_t *workout);
extern uint16_t GemVdiCommand(uint16_t op, uint16_t sub, uint16_t pairs,
    uint16_t words, const int16_t *points, const int16_t *ints, int16_t *reply);
extern void GemVdiReset(void);
extern UWORD GemBitmapFill(UWORD,UWORD,UWORD,UWORD,UWORD);
extern UWORD GemBitmapText(UWORD,UWORD,const UBYTE *,UWORD,UWORD,UWORD);
extern UWORD GemBitmapTextFill(UWORD,UWORD,const UBYTE *,UWORD,UWORD,UWORD,
                              UWORD,UWORD,UWORD,UWORD,UWORD);
extern const UBYTE map_col[16];

static struct VbxeDisplay display;
static UBYTE page[4096];
static ULONG pageAddress;
static UWORD dirty, fault;
static UBYTE commands[VBXE_BCB_BYTES];
static UWORD commandCount;
static ULONG commandWork;
/* The 5120 bytes immediately after the screen hold one 640 x 16 strip.
 * Only widget callbacks redirect drawing, never other owner operations. */
#define WIDGET_STRIP_BASE 76800UL
static UWORD stripActive,stripRedirect,stripLeft,stripTop,stripRight,stripBottom;
static ULONG stripOffset;
static void pointer_reset(void);
static void pointer_erase(UWORD left,UWORD top,UWORD right,UWORD bottom);
static void outline_hide(void);
static UWORD outlineLeft,outlineTop,outlineRight,outlineBottom,outlineVisible,outlineDrawn;



static void latch(UWORD status) { if (status && !fault) fault=status; }
/* Construction establishes record validity and enforces count/work bounds.
 * The admitted owner submits this private list without decoding it again. */
static void drain(void)
{
    if (commandCount && !fault) latch(VbxeOwnerSubmit(&display,commands,commandCount));
    commandCount=0;
    commandWork=0;
}
static void flush(void)
{
    drain();
    if (dirty && !fault) latch(VbxeOwnerWrite(&display,pageAddress,page,sizeof(page)));
    dirty=0;
}
volatile uint8_t *vram_win(uint32_t address)
{
    ULONG base;
    if (stripRedirect && address<VBXE_SCREEN_BYTES) address+=stripOffset;
    base=address&~0xfffUL;
    drain();
    if (!dirty || base!=pageAddress) {
        flush();
        if (!fault) latch(VbxeOwnerRead(&display,base,page,sizeof(page)));
        pageAddress=base;
    }
    dirty=1;
    return page+(UWORD)(address&0xfff);
}
void blit_start(void) { flush(); }
void blit_run(void) { flush(); }
uint8_t blit_pending(void) { return (uint8_t)(commandCount!=0 || dirty); }
void blit_mask(uint32_t source, uint16_t ss, uint32_t dest, uint16_t ds,
               uint16_t bytes, uint16_t rows, uint8_t am, uint8_t xm, uint8_t mode)
{
    UWORD n,limit;
    ULONG work;
    UBYTE *record;
    if (fault) return;
    if (stripRedirect && dest<VBXE_SCREEN_BYTES) dest+=stripOffset;
    /* Private renderer geometry is already clipped to screen/strip/atlas.
     * The producer supplies nonempty dimensions and a known hardware mode. */
    if (dirty) flush();
    limit=(UWORD)VBXE_LIST_WORK/(bytes*(mode ? 3 : 2));
    if (limit>VBXE_CHUNK_ROWS) limit=VBXE_CHUNK_ROWS;
    while (rows && !fault) {
        n=rows<limit ? rows : limit;
        work=(ULONG)bytes*n*(mode ? 3 : 2);
        if (commandCount==VBXE_LIST_RECORDS || commandWork+work>VBXE_LIST_WORK) drain();
        if (fault) return;
        record=commands+commandCount*21;

        record[0]=(UBYTE)source; record[1]=(UBYTE)(source>>8); record[2]=(UBYTE)(source>>16);
        record[3]=(UBYTE)ss; record[4]=(UBYTE)(ss>>8); record[5]=1;
        record[6]=(UBYTE)dest; record[7]=(UBYTE)(dest>>8); record[8]=(UBYTE)(dest>>16);
        record[9]=(UBYTE)ds; record[10]=(UBYTE)(ds>>8); record[11]=1;
        record[12]=(UBYTE)(bytes-1); record[13]=(UBYTE)((bytes-1)>>8);
        record[14]=(UBYTE)(n-1); record[15]=am; record[16]=xm; record[20]=mode;
        commandCount++;
        commandWork+=work;
        source+=(ULONG)n*ss; dest+=(ULONG)n*ds; rows-=n;
    }
}

/* Called only after the device's complete-cell visibility check. The atlas
 * supplies four/five bytes by eight rows. Immutable atlas/screen geometry and
 * the strip redirection establish extents; this producer bounds each list. */
void blit_glyph(uint32_t source,uint16_t stride,uint32_t dest,uint16_t bytes,uint8_t ink)
{
    UBYTE *r;
    UWORD work=bytes*24;
    if (fault) return;
    if (stripRedirect && dest<VBXE_SCREEN_BYTES) dest+=stripOffset;
    if (dirty) flush();
    if (commandCount==VBXE_LIST_RECORDS || commandWork+work>VBXE_LIST_WORK) drain();
    if (fault) return;
    r=commands+commandCount*21;
    r[0]=(UBYTE)source; r[1]=(UBYTE)(source>>8); r[2]=(UBYTE)(source>>16);
    r[3]=0; r[4]=(UBYTE)(stride>>8);
    r[6]=(UBYTE)dest; r[7]=(UBYTE)(dest>>8); r[8]=(UBYTE)(dest>>16);
    r[9]=64; r[10]=1; r[12]=(UBYTE)(bytes-1); r[13]=0;
    r[14]=7; r[15]=ink; r[16]=0; r[20]=6;
    commandCount++; commandWork+=work;
}
void blit_fill(uint32_t d,uint16_t s,uint16_t b,uint16_t r,uint8_t v)
{ blit_mask(0,0,d,s,b,r,0,v,0); }
void blit_and(uint32_t d,uint16_t s,uint16_t b,uint16_t r,uint8_t v)
{ blit_mask(0,0,d,s,b,r,0,v,4); }
void blit_or(uint32_t d,uint16_t s,uint16_t b,uint16_t r,uint8_t v)
{ blit_mask(0,0,d,s,b,r,0,v,3); }
void blit_xor(uint32_t d,uint16_t s,uint16_t b,uint16_t r,uint8_t v)
{ blit_mask(0,0,d,s,b,r,0,v,5); }
void vbxe_palette(uint8_t pal,uint8_t first,const uint8_t *rgb,uint16_t count)
{
    if (pal!=1 || first || count!=16) { latch(DISPLAY_BAD_ARGUMENT); return; }
    if (!fault) latch(VbxeOwnerPalette(&display,rgb));
}

/* Only successful acquisition changes private renderer state. Another Task's
 * failed open must not discard an owner's queued commands. */
UWORD GemDrawingOpen(WORD *out)
{
    static const UBYTE template[21]={0,0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0};
    UWORD i,status;
    ULONG p=(ULONG)out;
    if (!out || p>0x1000000UL-114 || (p<0x9000UL && p+114>0x8000UL))
        return DISPLAY_BAD_ARGUMENT;
    status=VbxeOpen(&display);
    if (status!=DISPLAY_OK) return status;
    for (i=0;i<VBXE_LIST_RECORDS;i++) memcpy(commands+i*21,template,21);
    dirty=fault=commandCount=0;
    commandWork=0;
    pointer_reset();
    status=GemVdiOpen(out);
    flush();
    if (!status && !fault) latch(VbxeOwnerShow(&display));
    if (status || fault) { GemDrawingClose(); return DISPLAY_DEVICE_FAULT; }
    return DISPLAY_OK;
}
static UWORD close_owner(void)
{
    UWORD status=DISPLAY_OK;
    if (display.lease.state) {
        flush();
        if (display.lease.state) status=VbxeOwnerClose(&display);
    }
    GemVdiReset();
    dirty=commandCount=0; commandWork=0;
    stripActive=stripRedirect=0;
    return fault ? DISPLAY_DEVICE_FAULT : status;
}
static UWORD fence_owner(void)
{
    if (fault) return DISPLAY_DEVICE_FAULT;
    flush();
    if (!fault) latch(VbxeOwnerFence(&display));
    return fault ? DISPLAY_DEVICE_FAULT : DISPLAY_OK;
}
UWORD GemDrawingClose(void)
{
    UWORD status;
    if (display.lease.state) {
        status=DisplayCheck(&display.lease);
        if (status!=DISPLAY_OK) return status;
    }
    return close_owner();
}
UWORD GemDrawingFence(void)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    return fence_owner();
}
UWORD GemDrawingCopy(const struct VbxeCopy *copy)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    pointer_erase(0,0,640,240);
    status=fence_owner();
    if (status!=DISPLAY_OK) return status;
    status=VbxeOwnerCopyRect(&display,copy);
    if (status==DISPLAY_DEVICE_FAULT) latch(status);
    return status;
}
UWORD GemDrawingFill(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen)
{
    UWORD status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (GemBitmapFill(left,top,right,bottom,pen)) return DISPLAY_BAD_ARGUMENT;
    return fence_owner();
}
UWORD GemDrawingScrollStart(const struct VbxeCopy *copy,UWORD pen,ULONG *id)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (display.operationPending) return DISPLAY_BUSY;
    if (!copy || pen>=16) return DISPLAY_BAD_ARGUMENT;
    pointer_erase(copy->destinationX,copy->destinationY,copy->destinationX+copy->width,
                  copy->sourceY+copy->height);
    status=fence_owner();
    if (status!=DISPLAY_OK) return status;
    status=VbxeOwnerScrollStart(&display,copy,(UBYTE)(map_col[pen]*17),id);
    if (status==DISPLAY_DEVICE_FAULT) latch(status);
    return status;
}
UWORD GemDrawingCopyStart(const struct VbxeCopy *copy,ULONG *id)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (display.operationPending) return DISPLAY_BUSY;
    if (!copy || !id) return DISPLAY_BAD_ARGUMENT;
    /* Overlays are screen pixels only; offscreen captures/restores use the same
     * operation but must never try to erase an overlay in cache coordinates. */
    if (!copy->source.offset)
        pointer_erase(copy->sourceX,copy->sourceY,copy->sourceX+copy->width,
                      copy->sourceY+copy->height);
    if (!copy->destination.offset)
        pointer_erase(copy->destinationX,copy->destinationY,copy->destinationX+copy->width,
                      copy->destinationY+copy->height);
    status=fence_owner();
    if (status!=DISPLAY_OK) return status;
    status=VbxeOwnerCopyStart(&display,copy,id);
    if (status==DISPLAY_DEVICE_FAULT) latch(status);
    return status;
}
UWORD GemDrawingPoll(ULONG id)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    status=VbxeOwnerPoll(&display,id);
    if (status==DISPLAY_DEVICE_FAULT) latch(status);
    return status;
}
UWORD GemDrawingText(UWORD x,UWORD y,const UBYTE *text,UWORD count,UWORD fg,UWORD bg)
{
    UWORD status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (GemBitmapText(x,y,text,count,fg,bg)) return DISPLAY_BAD_ARGUMENT;
    return fence_owner();
}
UWORD GemDrawingTextFill(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD fg,UWORD bg,UWORD fillX,UWORD fillY,UWORD fillWidth,UWORD fillHeight,
    UWORD fillPen)
{
    UWORD status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if ((fillX&1) || (fillWidth&1) || !fillWidth || !fillHeight ||
        fillX>=640 || fillY>=240 || fillWidth>640-fillX || fillHeight>240-fillY ||
        (ULONG)fillWidth*fillHeight>VBXE_TEXT_FILL_WORK || fillPen>15)
        return DISPLAY_BAD_ARGUMENT;
    if (GemBitmapTextFill(x,y,text,count,fg,bg,fillX,fillY,fillWidth,fillHeight,fillPen))
        return DISPLAY_BAD_ARGUMENT;
    return fault ? DISPLAY_DEVICE_FAULT : DISPLAY_OK;
}

/* Called only by the admitted ordinary drawing operation. No caller pointers
 * or validation state survives this synchronous invocation. */
void blit_text(uint32_t font,uint16_t x,uint16_t y,const uint8_t *text,
               uint16_t count,uint8_t ink,uint8_t paper)
{
    flush();
    if (!fault) latch(VbxeOwnerText(&display,font,x,y,text,count,ink,paper));
}
void blit_text_fill(uint32_t font,uint16_t x,uint16_t y,const uint8_t *text,
    uint16_t count,uint8_t ink,uint8_t paper,uint16_t fillX,uint16_t fillY,
    uint16_t width,uint16_t height,uint8_t value)
{
    struct VbxeTextFill fill;
    fill.x=fillX; fill.y=fillY; fill.width=width; fill.height=height; fill.value=value;
    flush();
    if (!fault) latch(VbxeOwnerTextFill(&display,font,x,y,text,count,ink,paper,&fill));
}

#define CURSOR_SAVE 0x37000UL
#define CURSOR_AND  0x37100UL
#define CURSOR_OR   0x37200UL
#define CURSOR_PARITY_BYTES 512UL
static UWORD cursorX, cursorY, cursorVisible, cursorDrawn, cursorBytes, cursorRows;
static ULONG cursorAddress;
static UWORD cursorMasksReady;
#include "gem-cursor-masks.h"


/* Only the admitted cursor operation calls this producer. Fixed private VRAM
 * slots and clipped screen coordinates establish every extent; no record
 * flushes a partially prepared move. cursor_render bounds count and work. */
static void cursor_record(UWORD index,ULONG source,UWORD sourceStride,
    ULONG destination,UWORD destinationStride,UWORD bytes,UWORD rows,UBYTE mode)
{
    UBYTE *r=commands+index*21;
    r[0]=(UBYTE)source; r[1]=(UBYTE)(source>>8); r[2]=(UBYTE)(source>>16);
    r[3]=(UBYTE)sourceStride; r[4]=(UBYTE)(sourceStride>>8); r[5]=1;
    r[6]=(UBYTE)destination; r[7]=(UBYTE)(destination>>8); r[8]=(UBYTE)(destination>>16);
    r[9]=(UBYTE)destinationStride; r[10]=(UBYTE)(destinationStride>>8); r[11]=1;
    r[12]=(UBYTE)(bytes-1); r[13]=0; r[14]=(UBYTE)(rows-1);
    r[15]=255; r[16]=r[17]=r[18]=r[19]=0; r[20]=mode;
}
static void cursor_submit(UWORD count)
{
    latch(VbxeOwnerSubmit(&display,commands,count));
}

/* One synchronous list restores the old save before replacing it with the
 * new background. At most four records / 84 bytes / 1440 work units, inside
 * the existing staging and VRAM arenas. Both edge nibbles remain preserved.
 * Logical visibility is separate: drawing may temporarily erase the pointer. */
static void cursor_render(UWORD x,UWORD y,UWORD draw)
{
    UWORD width=0,bytes=0,rows=0,count=0;
    ULONG address=0,parity;
    if (fault) return;
    if ((!draw && !cursorDrawn) || (draw && cursorDrawn && x==cursorX && y==cursorY)) {
        cursorX=x; cursorY=y;
        return;
    }
    flush();
    if (fault) return;
    if (draw) {
        width=640-x;
        if (width>16) width=16;
        rows=240-y;
        if (rows>16) rows=16;
        bytes=((x&1)+width+1)/2;
        address=(ULONG)y*320+x/2;
        if (!cursorMasksReady) {
            memcpy(page,cursorMasks,1024);
            latch(VbxeOwnerWrite(&display,CURSOR_AND,page,1024));
            if (fault) return;
            cursorMasksReady=1;
        }
    }
    if (cursorDrawn)
        cursor_record(count++,CURSOR_SAVE,16,cursorAddress,320,cursorBytes,cursorRows,0);
    if (draw) {
        parity=(x&1)*CURSOR_PARITY_BYTES;
        cursor_record(count++,address,320,CURSOR_SAVE,16,bytes,rows,0);
        cursor_record(count++,CURSOR_AND+parity,16,address,320,bytes,rows,4);
        cursor_record(count++,CURSOR_OR+parity,16,address,320,bytes,rows,3);
    }
    cursor_submit(count);
    if (fault) return;
    cursorX=x; cursorY=y; cursorDrawn=draw;
    cursorAddress=address; cursorBytes=bytes; cursorRows=rows;
}
static void cursor_hide(void)
{ cursor_render(cursorX,cursorY,0); }
static void cursor_show(void)
{ if (cursorVisible) cursor_render(cursorX,cursorY,1); }
#ifndef GEM_DRAWING_ONLY
static UWORD cursor_backend(void *context,const struct GemCursor *cursor)
{
    UWORD status=DisplayCheck(&display.lease);
    (void)context;
    if (status!=DISPLAY_OK || fault) return GEM_DEVICE_FAULT;
    cursor_render(cursor->x,cursor->y,cursor->visible);
    if (!fault) cursorVisible=cursor->visible;
    return fault ? GEM_DEVICE_FAULT : GEM_OK;
}
static UWORD close_backend(void *context)
{
    UWORD status;
    (void)context;
    if (!display.lease.state) return close_owner()==DISPLAY_OK ? GEM_OK : GEM_DEVICE_FAULT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return GEM_DEVICE_FAULT;
    cursor_hide();
    cursorVisible=0;
    status=close_owner();
    return status==DISPLAY_OK ? GEM_OK : GEM_DEVICE_FAULT;
}
static UWORD open_backend(void *context,WORD *out)
{
    UWORD status;
    (void)context;
    status=GemDrawingOpen(out);
    if (status!=DISPLAY_OK)
        return status==DISPLAY_BUSY ? GEM_BUSY : status==DISPLAY_UNSUPPORTED ? GEM_UNSUPPORTED : GEM_DEVICE_FAULT;
    cursorX=cursorY=cursorVisible=cursorDrawn=cursorBytes=cursorRows=0;
    cursorAddress=0;
    cursorMasksReady=0;
    return GEM_OK;
}
/* The saved background includes the edge nibbles, not just visible arrow
 * pixels. Disjoint text/bars cannot invalidate it and need no cursor blits.
 * Other drawing remains conservative. Long arithmetic avoids WORD wrapping. */
static UWORD cursor_intersects(const struct GemCommand *cmd,const WORD *points)
{
    LONG left,right,top,bottom,swap;
    if (!cursorDrawn) return 0;
    if (cmd->opcode==8) {
        if (!cmd->int_words) return 0;
        left=(LONG)points[0]-1;
        right=(LONG)points[0]+(LONG)cmd->int_words*8;
        top=(LONG)points[1]-16; bottom=(LONG)points[1]+16;
    } else if (cmd->opcode==11) {
        left=points[0]; right=points[2]; top=points[1]; bottom=points[3];
        if (left>right) { swap=left; left=right; right=swap; }
        if (top>bottom) { swap=top; top=bottom; bottom=swap; }
    } else return 1;
    return !(right<(LONG)(cursorX&~1U) || left>(LONG)((cursorX+15)|1U) ||
             bottom<(LONG)cursorY || top>(LONG)cursorY+15);
}
static UWORD command_backend(void *context,const struct GemCommand *cmd,
    const WORD *points,const WORD *ints,WORD *reply)
{
    UWORD status=DisplayCheck(&display.lease);
    (void)context;
    if (status!=DISPLAY_OK || fault) return GEM_DEVICE_FAULT;
    if (cmd->opcode!=17 && cmd->opcode!=22 && cmd->opcode!=23 &&
        cmd->opcode!=25 && cmd->opcode!=32 && cmd->opcode!=129 &&
        cursor_intersects(cmd,points)) cursor_hide();
    if (fault) return GEM_DEVICE_FAULT;
    return GemVdiCommand(cmd->opcode,cmd->subopcode,cmd->point_pairs,cmd->int_words,points,ints,reply);
}
static UWORD fence_backend(void *context)
{
    UWORD status=DisplayCheck(&display.lease);
    (void)context;
    if (status!=DISPLAY_OK || fault) return GEM_DEVICE_FAULT;
    flush();
    cursor_show();
    if (!fault) latch(VbxeOwnerFence(&display));
    return fault ? GEM_DEVICE_FAULT : GEM_OK;
}
const struct GemBackend GemVbxeBackend={open_backend,command_backend,fence_backend,close_backend,cursor_backend,0};

#endif

ULONG GemDrawingCompletionMask(void)
{ return VbxeCompletionMask(&display); }

UWORD GemDrawingTextClip(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD fg,UWORD bg,UWORD left,UWORD top,UWORD right,UWORD bottom)
{
    extern UWORD GemBitmapTextClip(UWORD,UWORD,const UBYTE *,UWORD,UWORD,UWORD,
                                  UWORD,UWORD,UWORD,UWORD);
    UWORD status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (GemBitmapTextClip(x,y,text,count,fg,bg,left,top,right,bottom))
        return DISPLAY_BAD_ARGUMENT;
    return fence_owner();
}


static void pointer_reset(void)
{
    cursorX=cursorY=cursorVisible=cursorDrawn=cursorBytes=cursorRows=0;
    cursorAddress=0;
    cursorMasksReady=0;
    outlineVisible=outlineDrawn=0;
    stripActive=stripRedirect=0;
}

/* The save includes adjacent edge nibbles. Restore before either is changed. */
static void pointer_erase(UWORD left,UWORD top,UWORD right,UWORD bottom)
{
    if (outlineDrawn && left<outlineRight && right>outlineLeft &&
        top<outlineBottom && bottom>outlineTop) {
        cursor_hide();
        outline_hide();
    }
    if (cursorDrawn && left<(cursorX&~1U)+cursorBytes*2 && right>(cursorX&~1U) &&
        top<cursorY+cursorRows && bottom>cursorY) cursor_hide();
}

UWORD GemDrawingPointer(UWORD x,UWORD y,UWORD visible)
{
    UWORD status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (x>=640 || y>=240 || visible>1) return DISPLAY_BAD_ARGUMENT;
    if (display.operationPending) return DISPLAY_BUSY;
    cursor_render(x,y,visible);
    if (!fault) cursorVisible=visible;
    return fault ? DISPLAY_DEVICE_FAULT : DISPLAY_OK;
}

/* Called by the admitted bitmap operation after complete geometry/source
 * validation, before its first write. Invalid requests leave overlays intact. */
void GemDrawingPrepare(UWORD left,UWORD top,UWORD right,UWORD bottom)
{
    pointer_erase(left,top,right,bottom);
}

/* One XOR border with disjoint corners. Only the presenter updates it, between
 * DMA lists; background writes remove it before modifying the saved pixels. */
static void outline_record(UWORD index,ULONG address,UWORD bytes,UWORD rows,UBYTE mask)
{
    UBYTE *r=commands+index*21;
    memset(r,0,21);
    r[5]=1;
    r[6]=(UBYTE)address; r[7]=(UBYTE)(address>>8); r[8]=(UBYTE)(address>>16);
    r[9]=64; r[10]=1; r[11]=1;
    r[12]=(UBYTE)(bytes-1); r[13]=(UBYTE)((bytes-1)>>8);
    r[14]=(UBYTE)(rows-1); r[16]=mask; r[20]=5;
}
static void outline_toggle(void)
{
    ULONG address=(ULONG)outlineTop*320+outlineLeft/2;
    UWORD bytes=(outlineRight-outlineLeft)/2;
    UWORD rows=outlineBottom-outlineTop;
    flush();
    if (fault) return;
    /* Admitted even screen bounds give four legal records and at most 3348
     * work units: two 320-byte rows plus two 238-row single-byte edges. */
    outline_record(0,address,bytes,1,255);
    outline_record(1,address+(ULONG)(rows-1)*320,bytes,1,255);
    outline_record(2,address+320,1,rows-2,240);
    outline_record(3,address+320+bytes-1,1,rows-2,15);
    latch(VbxeOwnerSubmit(&display,commands,4));
}
static void outline_hide(void)
{
    if (outlineDrawn && !fault) outline_toggle();
    outlineDrawn=0;
}
UWORD GemDrawingOutline(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD visible)
{
    UWORD status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (visible>1 || (visible && ((left|right)&1 || left>=right || top>=bottom ||
        right>640 || bottom>240 || right-left<32 || bottom-top<32))) return DISPLAY_BAD_ARGUMENT;
    if (display.operationPending) return DISPLAY_BUSY;
    if (!visible || left!=outlineLeft || top!=outlineTop || right!=outlineRight || bottom!=outlineBottom) {
        if (outlineDrawn) { cursor_hide(); outline_hide(); }
        outlineLeft=left; outlineTop=top; outlineRight=right; outlineBottom=bottom;
    }
    outlineVisible=visible;
    if (outlineVisible && !outlineDrawn) {
        cursor_hide();
        outline_toggle();
        if (!fault) outlineDrawn=1;
    }
    return fault ? DISPLAY_DEVICE_FAULT : DISPLAY_OK;
}

/* Only a trusted, bounded renderer calls this synchronous closure. */
UWORD GemDrawingBatch(UWORD left,UWORD top,UWORD right,UWORD bottom,void (*draw)(void))
{
    UWORD status;
    if (!draw || left>=right || right>640 || top>=bottom || bottom>240 ||
        bottom-top>16) return DISPLAY_BAD_ARGUMENT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (display.operationPending) return DISPLAY_BUSY;
    GemDrawingPrepare(left,top,right,bottom);
    draw();
    return fence_owner();
}

/* Reconstruct a widget strip offscreen across bounded object continuations.
 * A callback returns nonzero only when every intersecting object is complete.
 * No callback or client pointer survives a call. The presenter freezes the
 * model until the strip retires; a new first chunk discards an abandoned one. */
UWORD GemDrawingWidgetBatch(UWORD left,UWORD top,UWORD right,UWORD bottom,
                            UWORD first,UWORD (*draw)(void))
{
    UWORD status,complete,lo,hi,rows;
    ULONG screen,scratch;
    if (!draw || left>=right || right>640 || top>=bottom || bottom>240 ||
        bottom-top>16) return DISPLAY_BAD_ARGUMENT;
    if (!first && (!stripActive || left!=stripLeft || top!=stripTop ||
        right!=stripRight || bottom!=stripBottom)) return DISPLAY_BAD_ARGUMENT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (display.operationPending) return DISPLAY_BUSY;
    if (first) {
        stripActive=1;stripLeft=left;stripTop=top;stripRight=right;stripBottom=bottom;
        stripOffset=WIDGET_STRIP_BASE-(ULONG)top*320;
    }
    stripRedirect=1;
    complete=draw();
    stripRedirect=0;
    if (complete && !fault) {
        /* Scratch writes precede the copy in the same ordered list when it
         * fits. Capacity drains still touch only completed scratch work. */
        /* Preserve the neighbouring nibble at either odd clip edge. Pointer
         * save/restore sees screen coordinates only at this publish boundary. */
        GemDrawingPrepare(left,top,right,bottom);
        screen=(ULONG)top*320;scratch=WIDGET_STRIP_BASE;
        lo=left/2;hi=right/2;rows=bottom-top;
        if (left&1) {
            blit_and(screen+lo,320,1,rows,0xf0);
            blit_mask(scratch+lo,320,screen+lo,320,1,rows,0x0f,0,3);
            ++lo;
        }
        if (hi>lo) blit_mask(scratch+lo,320,screen+lo,320,hi-lo,rows,255,0,0);
        if (right&1) {
            blit_and(screen+hi,320,1,rows,0x0f);
            blit_mask(scratch+hi,320,screen+hi,320,1,rows,0xf0,0,3);
        }
        stripActive=0;
    }
    return fence_owner();
}

/* The admitted disabled pattern is GEM IP_4PATT: alternating AAAA/5555,
 * transparent WHITE (hardware zero). Group alternate scanlines in a blit,
 * preserving partial packed bytes. Phase is anchored to screen coordinates. */
void GemWidgetStipple(UWORD left,UWORD top,UWORD right,UWORD bottom)
{
    UWORD y,lo,hi,rows;
    UBYTE mask;
    ULONG base;
    for (y=top;y<top+2 && y<bottom;y++) {
        rows=(bottom-y+1)/2;lo=left/2;hi=right/2;
        base=((ULONG)(y*20))<<4;
        mask=(y&1) ? 0xf0 : 0x0f;
        if (left&1) {
            if (y&1) blit_and(base+lo,640,1,rows,0xf0);
            lo++;
        }
        if ((right&1) && !(y&1)) blit_and(base+hi,640,1,rows,0x0f);
        if (hi>lo) blit_and(base+lo,640,hi-lo,rows,mask);
    }
}
