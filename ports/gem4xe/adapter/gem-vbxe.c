/* Exec adapter for the selected GEM renderer. No donor hardware routines link.
 * The donor's window pointers address a private upper-RAM staging page. Flushing
 * it uses the checked G3 transfer and always closes the CPU aperture. A fault
 * latches for the whole call: subsequent void donor callbacks cannot touch HW.
 * Lists are bounded by count and work; every dependency drains queued DMA.
 */
#include "gem-drawing.h"
#include <hardware/vbxe-snapshots.h>
#ifndef GEM_DRAWING_ONLY
#include "gem-vbxe.h"
#endif
#include "vbxe-internal.h"
#include "gem-vbxe-tables.h"
#include "gem-frame-gadgets.h"
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
static UBYTE *commandNext;
static UWORD commandCount;
static UWORD commandWork;
/* Small CICONs share pixels across directory entries and windows. Retain a
 * source copy as well: application bitmaps may change or be freed/reallocated.
 * A hit compares at most 480 bytes, without retaining ownership of the source.
 * All cache access is under the existing physical display grant. */
#define ICON_CACHE_COUNT 16
#define ICON_CACHE_PITCH 17
#define ICON_CACHE_ROWS 24
#define ICON_CACHE_PLANE (ICON_CACHE_PITCH*ICON_CACHE_ROWS)
struct IconCache {
    const UWORD *mask;
    const UBYTE *data;
    UWORD width,height;
    UWORD savedMask[48];
    UBYTE savedData[384];
};
static struct IconCache iconCache[ICON_CACHE_COUNT];
static UWORD iconNext;
#if DESKTOP_ICON_CACHE_BYTES != ICON_CACHE_COUNT*2048UL
#error Icon cache reservation does not match its slots
#endif
/* The 5120 bytes immediately after the screen hold one 640 x 16 strip.
 * Only widget callbacks redirect drawing, never other owner operations. */
#define WIDGET_STRIP_BASE 76800UL
static UWORD stripActive,stripRedirect,stripLeft,stripTop,stripRight,stripBottom;
static ULONG stripOffset;
static UWORD stripPitch,stripCompact;
static void pointer_reset(void);
static void pointer_erase(UWORD left,UWORD top,UWORD right,UWORD bottom);
static void outline_hide(void);
static UWORD outlineLeft,outlineTop,outlineRight,outlineBottom,outlineVisible,outlineDrawn;



static UWORD render_enter(void)
{
    if (!display.lease.state) return DISPLAY_INVALID_OWNER;
    return DisplayOwnerEnter();
}
static UWORD render_exit(UWORD status)
{
    /* A successful physical close already retired and reset arbitration. */
    if (display.lease.state) DisplayOwnerEnd(display.operationPending);
    return status;
}
static void latch(UWORD status) { if (status && !fault) fault=status; }
/* Construction establishes record validity and enforces count/work bounds.
 * The admitted owner submits this private list without decoding it again. */
static void drain(void)
{
    if (commandCount && !fault) latch(VbxeOwnerSubmit(&display,commands,commandCount));
    commandCount=0;
    commandWork=0;
    commandNext=commands;
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
/* Producer strides are fixed screen/atlas pitches or a 0–320-byte raster
 * band. The work table also provides products for variable raster pitches. */
static UWORD row_step(UWORD stride,UWORD rows)
{
    if (!rows) return 0;
    switch (stride) {
    case 0: return 0;
    case 320: return GemStep320[rows];
    case 640: return GemStep640[rows];
    case 1024: return GemStep1024[rows];
    case 1280: return GemStep1280[rows];
    default: return GemWork2[((rows-1)<<9)|(stride-1)]>>1;
    }
}
void blit_mask(uint32_t source, uint16_t ss, uint32_t dest, uint16_t ds,
               uint16_t bytes, uint16_t rows, uint8_t am, uint8_t xm, uint8_t mode)
{
    UWORD n,limit,work,column=bytes-1;
    const UWORD *costs;
    UBYTE *record;
    if (fault) return;
    if (stripRedirect && dest<VBXE_SCREEN_BYTES) dest+=stripOffset;
    /* Private renderer geometry is already clipped to screen/strip/atlas.
     * The producer supplies nonempty dimensions and a known hardware mode. */
    if (dirty) flush();
    if (mode) { limit=GemRowLimit3[column]; costs=GemWork3; }
    else { limit=GemRowLimit2[column]; costs=GemWork2; }
    while (rows && !fault) {
        n=rows<limit ? rows : limit;
        work=costs[((n-1)<<9)|column];
        if (commandCount==VBXE_LIST_RECORDS || commandWork+work>(UWORD)VBXE_LIST_WORK) drain();
        if (fault) return;
        record=commandNext;

        record[0]=(UBYTE)source; record[1]=(UBYTE)(source>>8); record[2]=(UBYTE)(source>>16);
        record[3]=(UBYTE)ss; record[4]=(UBYTE)(ss>>8); record[5]=1;
        record[6]=(UBYTE)dest; record[7]=(UBYTE)(dest>>8); record[8]=(UBYTE)(dest>>16);
        record[9]=(UBYTE)ds; record[10]=(UBYTE)(ds>>8); record[11]=1;
        record[12]=(UBYTE)(bytes-1); record[13]=(UBYTE)((bytes-1)>>8);
        record[14]=(UBYTE)(n-1); record[15]=am; record[16]=xm; record[20]=mode;
        commandCount++;
        commandNext=record+21;
        commandWork+=work;
        rows-=n;
        if (rows) { source+=row_step(ss,n); dest+=row_step(ds,n); }
    }
}

/* Encode one already reserved atlas record; no queue or hardware policy. */
static UBYTE *glyph_record(UBYTE *r,ULONG source,UWORD stride,ULONG dest,UWORD bytes,UBYTE ink)
{
    r[0]=(UBYTE)source; r[1]=(UBYTE)(source>>8); r[2]=(UBYTE)(source>>16);
    r[3]=0; r[4]=(UBYTE)(stride>>8);
    r[6]=(UBYTE)dest; r[7]=(UBYTE)(dest>>8); r[8]=(UBYTE)(dest>>16);
    r[9]=64; r[10]=1; r[12]=(UBYTE)(bytes-1); r[13]=0;
    r[14]=7; r[15]=ink; r[16]=0; r[20]=6;
    return r+21;
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
    if (commandCount==VBXE_LIST_RECORDS || commandWork+work>(UWORD)VBXE_LIST_WORK) drain();
    if (fault) return;
    r=commandNext;
    r=glyph_record(r,source,stride,dest,bytes,ink);
    commandCount++; commandNext=r; commandWork+=work;
}
/* Complete visible cells, nonzero stencil ink and constant X parity. The
 * caller supplies immutable atlas geometry; only this boundary reserves list
 * capacity. Blank cells consume neither records nor work. */
void blit_glyph_run(uint32_t atlas,uint16_t stride,uint32_t dest,uint16_t bytes,
    const uint16_t *glyphs,uint16_t count,uint8_t ink,const uint8_t *inkmap)
{
    const UBYTE *capacity=bytes==4 ? GemGlyphCapacity96 : GemGlyphCapacity120;
    UWORD n,room,written,ch,offset;
    ULONG source;
    UBYTE *r;
    if (fault) return;
    if (stripRedirect && dest<VBXE_SCREEN_BYTES) dest+=stripOffset;
    if (dirty) flush();
    while (count && !fault) {
        /* Do not launch a full queue for a blank-only suffix. */
        while (count && !inkmap[*glyphs&255]) {
            ++glyphs;--count;dest+=4;
        }
        if (!count) return;
        n=VBXE_LIST_RECORDS-commandCount;
        room=capacity[((UWORD)VBXE_LIST_WORK-commandWork)>>3];
        if (room<n) n=room;
        if (!n) { drain(); continue; }
        if (count<n) n=count;
        count-=n;
        r=commandNext;written=0;
        do {
            ch=*glyphs++&255;
            if (inkmap[ch]) {
                offset=ch<<2;
                if (bytes==5) offset+=ch;
                source=atlas+offset;
                r=glyph_record(r,source,stride,dest,bytes,ink);
                ++written;
            }
            dest+=4;
        } while (--n);
        commandNext=r;
        commandCount+=written;
        commandWork+=bytes==4 ? (written<<6)+(written<<5) : (written<<7)-(written<<3);
    }
}

void blit_fill(uint32_t d,uint16_t s,uint16_t b,uint16_t r,uint8_t v)
{ blit_mask(0,0,d,s,b,r,0,v,0); }
void blit_and(uint32_t d,uint16_t s,uint16_t b,uint16_t r,uint8_t v)
{ blit_mask(0,0,d,s,b,r,0,v,4); }
void blit_or(uint32_t d,uint16_t s,uint16_t b,uint16_t r,uint8_t v)
{ blit_mask(0,0,d,s,b,r,0,v,3); }
void blit_xor(uint32_t d,uint16_t s,uint16_t b,uint16_t r,uint8_t v)
{ blit_mask(0,0,d,s,b,r,0,v,5); }

/* Clip once, then append to the admitted frame list. Compact sides retain
 * their own pitch; screen-address redirection alone cannot address them. */
void GemFrameGadget(UWORD image,WORD x,WORD y,UWORD left,UWORD top,
                    UWORD right,UWORD bottom)
{
    const struct GemFrameImage *g=&GemFrameImages[image];
    WORD l=x,t=y,r=x+g->width,b=y+g->height;
    UWORD lo,hi,rows,pitch=stripRedirect ? stripPitch:320;
    ULONG source,destination;
    if (l<(WORD)left) l=left;
    if (t<(WORD)top) t=top;
    if (r>(WORD)right) r=right;
    if (b>(WORD)bottom) b=bottom;
    if (l>=r || t>=b) return;
    source=GEM_FRAME_GADGET_BASE+g->offset+((x&1) ? GEM_FRAME_GADGET_PHASE:0)
        +((UWORD)(t-y)<<4)+((UWORD)(l-(x&~1))>>1);
    lo=(UWORD)l>>1;hi=(UWORD)r>>1;rows=b-t;
    if (stripRedirect && stripCompact)
        destination=WIDGET_STRIP_BASE+((t-stripTop)<<stripCompact)+lo-(stripLeft>>1);
    else {
        destination=GemScreenRows[t]+lo;
        if (stripRedirect) destination+=stripOffset;
    }
    if (l&1) {
        blit_and(destination,pitch,1,rows,0xf0);
        blit_mask(source,16,destination,pitch,1,rows,0x0f,0,3);
        ++lo;++source;++destination;
    }
    if (hi>lo) blit_mask(source,16,destination,pitch,hi-lo,rows,255,0,0);
    if (r&1) {
        source+=hi-lo;destination+=hi-lo;
        blit_and(destination,pitch,1,rows,0x0f);
        blit_mask(source,16,destination,pitch,1,rows,0xf0,0,3);
    }
}

UWORD GemSolidRows(UWORD left,UWORD right)
{
    UWORD bytes=(right>>1)-((left+1)>>1);
    return GemFillRows[bytes+3*((left&1)+(right&1))];
}

/* One already reserved constant-source record. Geometry and list capacity
 * are established once for the whole fill, not again for each nibble edge. */
static UBYTE *solid_record(UBYTE *r,ULONG dest,UWORD bytes,UWORD rows,UWORD pitch,UBYTE mask,UBYTE value,UBYTE mode)
{
    r[0]=r[1]=r[2]=r[3]=r[4]=0;
    r[6]=(UBYTE)dest;r[7]=(UBYTE)(dest>>8);r[8]=(UBYTE)(dest>>16);
    r[9]=(UBYTE)pitch;r[10]=(UBYTE)(pitch>>8);
    --bytes;r[12]=(UBYTE)bytes;r[13]=(UBYTE)(bytes>>8);
    r[14]=(UBYTE)(rows-1);r[15]=mask;r[16]=value;r[20]=mode;
    return r+21;
}

void GemSolidFill(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen)
{
    UWORD lo=(left+1)>>1,hi=right>>1,bytes=hi-lo;
    UWORD edges=(left&1)+(right&1),units=bytes+3*edges;
    UWORD records=(bytes!=0)+(edges<<1),limit=GemFillRows[units],rows,work;
    ULONG dest;
    UWORD pitch=stripRedirect ? stripPitch:320;
    UBYTE *r,ink=map_col[pen];
    if (fault) return;
    if (dirty) flush();
    while (top<bottom && !fault) {
        rows=bottom-top;if (rows>limit) rows=limit;
        /* Height is bounded before the product, so work fits a UWORD. */
        work=(units*rows)<<1;
        if (commandCount+records>VBXE_LIST_RECORDS || commandWork+work>VBXE_LIST_WORK) drain();
        if (fault) return;
        if (stripRedirect && stripCompact) {
            /* Geometry is still available here; no screen-address division. */
            dest=WIDGET_STRIP_BASE+((top-stripTop)<<stripCompact)-(stripLeft>>1);
        } else {
            dest=GemScreenRows[top];if (stripRedirect) dest+=stripOffset;
        }
        r=commandNext;
        if (left&1) {
            r=solid_record(r,dest+lo-1,1,rows,pitch,0,0xf0,4);
            r=solid_record(r,dest+lo-1,1,rows,pitch,0,ink,3);
        }
        if (bytes) r=solid_record(r,dest+lo,bytes,rows,pitch,0,(ink<<4)|ink,0);
        if (right&1) {
            r=solid_record(r,dest+hi,1,rows,pitch,0,0x0f,4);
            r=solid_record(r,dest+hi,1,rows,pitch,0,ink<<4,3);
        }
        commandNext=r;commandCount+=records;commandWork+=work;
        top+=rows;
    }
}

#ifdef EXEC_DESKTOP_STYLE
#include "gem-desktop-palette.h"
#endif
void vbxe_palette(uint8_t pal,uint8_t first,const uint8_t *rgb,uint16_t count)
{
    if (pal!=1 || first || count!=16) { latch(DISPLAY_BAD_ARGUMENT); return; }
    #ifdef EXEC_DESKTOP_STYLE
    rgb=desktop_rgb;
    #endif
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
    status=DisplayOwnerWake(VbxeCompletionMask(&display));
    if (status==DISPLAY_OK) status=render_enter();
    if (status!=DISPLAY_OK) { VbxeOwnerClose(&display); return status; }
    for (i=0;i<VBXE_LIST_RECORDS;i++) memcpy(commands+GemRecordOffsets[i],template,21);
    dirty=fault=commandCount=0;
    commandWork=0;
    commandNext=commands;
    pointer_reset();
    memset(iconCache,0,sizeof(iconCache));iconNext=0;
    status=GemVdiOpen(out);
    flush();
    if (!status && !fault)
        latch(VbxeOwnerWrite(&display,GEM_FRAME_GADGET_BASE,GemFramePixels,sizeof(GemFramePixels)));
    if (!status && !fault) latch(VbxeOwnerShow(&display));
    if (status || fault) { GemDrawingClose(); return DISPLAY_DEVICE_FAULT; }
    return render_exit(DISPLAY_OK);
}
static UWORD close_owner(void)
{
    UWORD status=DISPLAY_OK;
    if (display.lease.state) {
        flush();
        if (display.lease.state) status=VbxeOwnerClose(&display);
        if (status==DISPLAY_BUSY) return status;
    }
    GemVdiReset();
    dirty=commandCount=0; commandWork=0;
    commandNext=commands;
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
static UWORD draw_Close(void)
{
    return close_owner();
}
static UWORD draw_Fence(void)
{
    if (fault) return DISPLAY_DEVICE_FAULT;
    return fence_owner();
}
static UWORD draw_Copy(const struct VbxeCopy *copy)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    pointer_erase(0,0,640,240);
    status=fence_owner();
    if (status!=DISPLAY_OK) return status;
    status=VbxeOwnerCopyRect(&display,copy);
    if (status==DISPLAY_DEVICE_FAULT) latch(status);
    return status;
}
static UWORD draw_Fill(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen)
{
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (GemBitmapFill(left,top,right,bottom,pen)) return DISPLAY_BAD_ARGUMENT;
    return fence_owner();
}
static UWORD draw_ScrollStart(const struct VbxeCopy *copy,UWORD pen,ULONG *id)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
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
static UWORD draw_CopyStart(const struct VbxeCopy *copy,ULONG *id)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
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
static UWORD draw_Poll(ULONG id)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    status=VbxeOwnerPoll(&display,id);
    if (status==DISPLAY_DEVICE_FAULT) latch(status);
    return status;
}
static UWORD draw_Text(UWORD x,UWORD y,const UBYTE *text,UWORD count,UWORD fg,UWORD bg)
{
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (GemBitmapText(x,y,text,count,fg,bg)) return DISPLAY_BAD_ARGUMENT;
    return fence_owner();
}
static UWORD draw_TextFill(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD fg,UWORD bg,UWORD fillX,UWORD fillY,UWORD fillWidth,UWORD fillHeight,
    UWORD fillPen)
{
    if (fault) return DISPLAY_DEVICE_FAULT;
    if ((fillX&1) || (fillWidth&1) || !fillWidth || !fillHeight ||
        fillX>=640 || fillY>=240 || fillWidth>640-fillX || fillHeight>240-fillY ||
        (ULONG)fillWidth*fillHeight>VBXE_TEXT_FILL_WORK || fillPen>15)
        return DISPLAY_BAD_ARGUMENT;
    if (GemBitmapTextFill(x,y,text,count,fg,bg,fillX,fillY,fillWidth,fillHeight,fillPen))
        return DISPLAY_BAD_ARGUMENT;
    return fault ? DISPLAY_DEVICE_FAULT : DISPLAY_OK;
}

/* Explicit fixed offscreen destination: never erase a screen overlay here. */
static UWORD draw_BackingText(UWORD x,UWORD y,const UBYTE *text,UWORD count,UWORD fg,UWORD bg)
{
    UWORD status=fence_owner();
    if (status!=DISPLAY_OK) return status;
    status=VbxeOwnerBackingText(&display,(x&1) ? 0x33000UL:0x31000UL,
        x,y,text,count,(UBYTE)(map_col[fg]*17),(UBYTE)(map_col[bg]*17));
    if (status==DISPLAY_DEVICE_FAULT) latch(status);
    return status;
}
static UWORD draw_BackingFill(UWORD x,UWORD y,UWORD width,UWORD height,UWORD pen)
{
    UWORD status=fence_owner();
    if (status!=DISPLAY_OK) return status;
    blit_fill(DESKTOP_SHELL_BACKING_BASE+((ULONG)y<<8)+(x>>1),
        256,width>>1,height,(UBYTE)(map_col[pen]*17));
    return fence_owner();
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
    UBYTE *r=commands+GemRecordOffsets[index];
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
        address=GemScreenRows[y]+x/2;
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
    UWORD status=render_enter();
    (void)context;
    if (status!=DISPLAY_OK) return GEM_DEVICE_FAULT;
    if (fault) return render_exit(GEM_DEVICE_FAULT);
    cursor_render(cursor->x,cursor->y,cursor->visible);
    if (!fault) cursorVisible=cursor->visible;
    return render_exit(fault ? GEM_DEVICE_FAULT : GEM_OK);
}
static UWORD close_backend(void *context)
{
    UWORD status;
    (void)context;
    if (!display.lease.state) return close_owner()==DISPLAY_OK ? GEM_OK : GEM_DEVICE_FAULT;
    status=render_enter();
    if (status!=DISPLAY_OK) return GEM_DEVICE_FAULT;
    cursor_hide();
    cursorVisible=0;
    status=close_owner();
    return render_exit(status==DISPLAY_OK ? GEM_OK : GEM_DEVICE_FAULT);
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
    UWORD status=render_enter();
    (void)context;
    if (status!=DISPLAY_OK) return GEM_DEVICE_FAULT;
    if (fault) return render_exit(GEM_DEVICE_FAULT);
    if (cmd->opcode!=17 && cmd->opcode!=22 && cmd->opcode!=23 &&
        cmd->opcode!=25 && cmd->opcode!=32 && cmd->opcode!=129 &&
        cursor_intersects(cmd,points)) cursor_hide();
    if (fault) return render_exit(GEM_DEVICE_FAULT);
    status=GemVdiCommand(cmd->opcode,cmd->subopcode,cmd->point_pairs,cmd->int_words,points,ints,reply);
    if (!status && fence_owner()!=DISPLAY_OK) status=GEM_DEVICE_FAULT;
    return render_exit(status);
}
static UWORD fence_backend(void *context)
{
    UWORD status=render_enter();
    (void)context;
    if (status!=DISPLAY_OK) return GEM_DEVICE_FAULT;
    if (fault) return render_exit(GEM_DEVICE_FAULT);
    flush();
    cursor_show();
    if (!fault) latch(VbxeOwnerFence(&display));
    return render_exit(fault ? GEM_DEVICE_FAULT : GEM_OK);
}
const struct GemBackend GemVbxeBackend={open_backend,command_backend,fence_backend,close_backend,cursor_backend,0};

#endif

ULONG GemDrawingCompletionMask(void)
{ return VbxeCompletionMask(&display); }

static UWORD draw_TextClip(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD fg,UWORD bg,UWORD left,UWORD top,UWORD right,UWORD bottom)
{
    extern UWORD GemBitmapTextClip(UWORD,UWORD,const UBYTE *,UWORD,UWORD,UWORD,
                                  UWORD,UWORD,UWORD,UWORD);
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

static UWORD draw_Pointer(UWORD x,UWORD y,UWORD visible)
{
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
    UBYTE *r=commands+GemRecordOffsets[index];
    memset(r,0,21);
    r[5]=1;
    r[6]=(UBYTE)address; r[7]=(UBYTE)(address>>8); r[8]=(UBYTE)(address>>16);
    r[9]=64; r[10]=1; r[11]=1;
    r[12]=(UBYTE)(bytes-1); r[13]=(UBYTE)((bytes-1)>>8);
    r[14]=(UBYTE)(rows-1); r[16]=mask; r[20]=5;
}
static void outline_span(UWORD left,UWORD right,UWORD top,UWORD rows)
{
    ULONG address=GemScreenRows[top];
    UWORD lo=left>>1,hi=right>>1;
    if (left&1) { blit_xor(address+lo,320,1,rows,15); ++lo; }
    if (hi>lo) blit_xor(address+lo,320,hi-lo,rows,255);
    if (right&1) blit_xor(address+hi,320,1,rows,240);
}
/* Selection touches only completed plain rows. One admission/list/fence covers
 * both changes; overlay saves must be removed before their pixels are read. */
static UWORD draw_InvertRows(const WORD *rectangles,UWORD count)
{
    UWORD i;
    const WORD *r;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (display.operationPending) return DISPLAY_BUSY;
    for (i=0,r=rectangles;i<count;++i,r+=4)
        pointer_erase(r[0],r[1],r[2],r[3]);
    for (i=0,r=rectangles;i<count;++i,r+=4)
        outline_span(r[0],r[2],r[1],r[3]-r[1]);
    return fence_owner();
}
static void outline_toggle(void)
{
    ULONG address=GemScreenRows[outlineTop]+outlineLeft/2;
    UWORD bytes=(outlineRight-outlineLeft)/2;
    UWORD rows=outlineBottom-outlineTop;
    flush();
    if (fault) return;
    if ((outlineLeft|outlineRight)&1) {
        outline_span(outlineLeft,outlineRight,outlineTop,1);
        outline_span(outlineLeft,outlineRight,outlineBottom-1,1);
        outline_span(outlineLeft,outlineLeft+1,outlineTop+1,rows-2);
        outline_span(outlineRight-1,outlineRight,outlineTop+1,rows-2);
        flush();
        return;
    }
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
static UWORD draw_Outline(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD visible)
{
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (visible>1 || (visible && (left>=right || top>=bottom ||
        right>640 || bottom>240 || right-left<8 || bottom-top<8))) return DISPLAY_BAD_ARGUMENT;
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
static UWORD draw_Batch(UWORD left,UWORD top,UWORD right,UWORD bottom,void (*draw)(void))
{
    if (!draw || left>=right || right>640 || top>=bottom || bottom>240 ||
        bottom-top>16) return DISPLAY_BAD_ARGUMENT;
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
static UWORD widget_batch(UWORD left,UWORD top,UWORD right,UWORD bottom,
                            UWORD first,UWORD compact,UWORD (*draw)(void))
{
    UWORD complete,lo,hi,rows;
    ULONG screen,scratch;
    if (!draw || left>=right || right>640 || top>=bottom || bottom>240 ||
        (compact ? right-left>16:bottom-top>16)) return DISPLAY_BAD_ARGUMENT;
    if (!first && (!stripActive || left!=stripLeft || top!=stripTop ||
        right!=stripRight || bottom!=stripBottom)) return DISPLAY_BAD_ARGUMENT;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (display.operationPending) return DISPLAY_BUSY;
    if (first) {
        stripActive=1;stripLeft=left;stripTop=top;stripRight=right;stripBottom=bottom;
        stripOffset=WIDGET_STRIP_BASE-GemScreenRows[top];
        /* Power-of-two pitch keeps tall source offsets out of the sixteen-row
         * work tables. At most 16*240 bytes, still inside the same scratch. */
        stripCompact=compact ? ((((right+1)>>1)-(left>>1)>8) ? 4:3):0;
        stripPitch=compact ? 1U<<stripCompact:320;
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
        screen=GemScreenRows[top];scratch=WIDGET_STRIP_BASE;
        if (compact) scratch-=left>>1;
        lo=left/2;hi=right/2;rows=bottom-top;
        if (left&1) {
            blit_and(screen+lo,320,1,rows,0xf0);
            blit_mask(scratch+lo,stripPitch,screen+lo,320,1,rows,0x0f,0,3);
            ++lo;
        }
        if (hi>lo) blit_mask(scratch+lo,stripPitch,screen+lo,320,hi-lo,rows,255,0,0);
        if (right&1) {
            blit_and(screen+hi,320,1,rows,0x0f);
            blit_mask(scratch+hi,stripPitch,screen+hi,320,1,rows,0xf0,0,3);
        }
        stripActive=0;
    }
    return fence_owner();
}

/* Tall, non-text frame sides need at most nine bytes per row, including
 * odd clip edges. An 8/16-byte pitch fits all 240 rows in the existing strip.
 * Only solid fills and fixed atlas images use this private destination. */
static UWORD draw_FrameBatch(UWORD left,UWORD top,UWORD right,UWORD bottom,
                            UWORD (*draw)(void))
{
    return widget_batch(left,top,right,bottom,1,1,draw);
}
static UWORD draw_WidgetBatch(UWORD left,UWORD top,UWORD right,UWORD bottom,
                             UWORD first,UWORD (*draw)(void))
{
    return widget_batch(left,top,right,bottom,first,0,draw);
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

/* The icon owns no persistent hardware state. Flush before reusing the CPU
 * page, upload just the clipped planes, and retain them until both blits fence.
 * Transparent pixels and the two possible outside nibbles remain unchanged. */
void GemIconBitmap(const UWORD *mask,const UWORD *data,UWORD width,
    WORD x,WORD y,UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD fg,UWORD bg)
{
    UWORD row,sx,px,bit,mi,di,at=0,stride=(width>>4);
    UWORD bytes=((right+1)>>1)-(left>>1),rows=bottom-top;
    UWORD source=(top-y)*stride,index;
    UBYTE ink=map_col[fg],paper=map_col[bg],a,o,shift;
    flush();
    if (fault) return;
    for (row=0;row<rows;++row,source+=stride) {
        sx=left-x;index=source+(sx>>4);bit=0x8000U>>(sx&15);
        mi=mask[index];di=data[index];a=255;o=0;
        for (px=left&~1U;px<((right+1)&~1U);++px) {
            shift=(px&1) ? 0:4;
            if (px>=left && px<right) {
                if ((mi|di)&bit) {
                    a&=~(15U<<shift);
                    o|=((di&bit) ? ink:paper)<<shift;
                }
                bit>>=1;
                if (!bit && px+1<right) { bit=0x8000U;mi=mask[++index];di=data[index]; }
            }
            if (px&1) { page[at]=a;page[2048+at]=o;++at;a=255;o=0; }
        }
    }
    latch(VbxeOwnerWrite(&display,0x36000UL,page,at));
    if (!fault) latch(VbxeOwnerWrite(&display,0x36800UL,page+2048,at));
    blit_mask(0x36000UL,bytes,GemScreenRows[top]+(left>>1),320,bytes,rows,255,0,4);
    blit_mask(0x36800UL,bytes,GemScreenRows[top]+(left>>1),320,bytes,rows,255,0,3);
}

/* Prepare both X phases once. A pair of source pixels produces one mask byte;
 * shifting that byte with its predecessor also makes the odd-X version.
 * Unused nibbles remain transparent, including the final odd-X byte. */
static void icon_cache_build(const UWORD *mask,const UBYTE *data,UWORD width,UWORD height,
                             UWORD slot)
{
    UWORD row,col,at=0,words=0,pixel=0,mi=0,bit=0,a,o,previousA,previousO;
    UWORD bytes=width>>1;
    flush();
    if (fault) return;
    memset(page,255,ICON_CACHE_PLANE);
    memset(page+ICON_CACHE_PLANE,0,ICON_CACHE_PLANE);
    memset(page+2*ICON_CACHE_PLANE,255,ICON_CACHE_PLANE);
    memset(page+3*ICON_CACHE_PLANE,0,ICON_CACHE_PLANE);
    for (row=0;row<height;++row,at+=ICON_CACHE_PITCH) {
        previousA=255;previousO=0;
        for (col=0;col<bytes;++col) {
            if (!(col&7)) { mi=mask[words++];bit=0x8000; }
            a=(mi&bit ? 0:0xf0)|(mi&(bit>>1) ? 0:0x0f);bit>>=2;
            o=data[pixel++]&~a;
            page[at+col]=(UBYTE)a;
            page[ICON_CACHE_PLANE+at+col]=(UBYTE)o;
            page[2*ICON_CACHE_PLANE+at+col]=(UBYTE)((previousA<<4)|(a>>4));
            page[3*ICON_CACHE_PLANE+at+col]=(UBYTE)((previousO<<4)|(o>>4));
            previousA=a;previousO=o;
        }
        page[2*ICON_CACHE_PLANE+at+bytes]=(UBYTE)((previousA<<4)|15);
        page[3*ICON_CACHE_PLANE+at+bytes]=(UBYTE)(previousO<<4);
    }
    latch(VbxeOwnerWrite(&display,DESKTOP_ICON_CACHE_BASE+((ULONG)slot<<11),
                        page,4*ICON_CACHE_PLANE));
}

/* Source mask ORs protect clipped edge nibbles, while the matching ink ANDs
 * suppress those same nibbles. Interior bytes need just the usual two blits. */
static void icon_cache_blit(UWORD slot,WORD x,WORD y,UWORD left,UWORD top,
                            UWORD right,UWORD bottom)
{
    UWORD lo=left>>1,hi=right>>1,rows=bottom-top;
    ULONG source=DESKTOP_ICON_CACHE_BASE+((ULONG)slot<<11)
        +((x&1) ? 2*ICON_CACHE_PLANE:0)
        +(top-y)*ICON_CACHE_PITCH+((left-(x&~1))>>1);
    ULONG dest=GemScreenRows[top]+lo;
    if (left&1) {
        blit_mask(source,ICON_CACHE_PITCH,dest,320,1,rows,0x0f,0xf0,4);
        blit_mask(source+ICON_CACHE_PLANE,ICON_CACHE_PITCH,dest,320,1,rows,0x0f,0,3);
        ++source;++dest;++lo;
    }
    if (hi>lo) {
        blit_mask(source,ICON_CACHE_PITCH,dest,320,hi-lo,rows,255,0,4);
        blit_mask(source+ICON_CACHE_PLANE,ICON_CACHE_PITCH,dest,320,hi-lo,rows,255,0,3);
        source+=hi-lo;dest+=hi-lo;
    }
    if ((right&1) && hi>=lo) {
        blit_mask(source,ICON_CACHE_PITCH,dest,320,1,rows,0xf0,0x0f,4);
        blit_mask(source+ICON_CACHE_PLANE,ICON_CACHE_PITCH,dest,320,1,rows,0xf0,0,3);
    }
}

static void colour_icon_cached(const UWORD *mask,const UBYTE *data,UWORD width,UWORD height,
    WORD x,WORD y,UWORD left,UWORD top,UWORD right,UWORD bottom)
{
    UWORD i,maskBytes=width==32 ? height<<2:height<<1,dataBytes=maskBytes<<2;
    struct IconCache *entry;
    for (i=0,entry=iconCache;i<ICON_CACHE_COUNT;++i,++entry) {
        if (entry->mask==mask && entry->data==data && entry->width==width && entry->height==height) {
            if (!memcmp(entry->savedMask,mask,maskBytes) && !memcmp(entry->savedData,data,dataBytes))
                goto ready;
            break;
        }
    }
    if (i==ICON_CACHE_COUNT) { i=iconNext;iconNext=(iconNext+1)&(ICON_CACHE_COUNT-1); }
    entry=&iconCache[i];
    icon_cache_build(mask,data,width,height,i);
    if (fault) return;
    entry->mask=mask;entry->data=data;entry->width=width;entry->height=height;
    memcpy(entry->savedMask,mask,maskBytes);memcpy(entry->savedData,data,dataBytes);
ready:
    icon_cache_blit(i,x,y,left,top,right,bottom);
}

/* CICON pixels are already in the device format. Only clipping/alignment and
 * the one-bit transparency mask are expanded here; no palette/plane conversion.
 * objc_draw supplies the same bounded strips and display grant as G_ICON. */
void GemColourIconBitmap(const UWORD *mask,const UBYTE *data,UWORD width,UWORD height,
    WORD x,WORD y,UWORD left,UWORD top,UWORD right,UWORD bottom)
{
    UWORD row,px,sx,bit,mi,index,at=0,stride=width>>4;
    UWORD bytes=((right+1)>>1)-(left>>1),rows=bottom-top;
    UWORD source=(top-y)*stride,pixels=(top-y)*(width>>1);
    /* Keep nibble arithmetic native-width; narrow only at the page stores. */
    UWORD a,o,shift,value;
    if (width<=32 && height<=ICON_CACHE_ROWS) {
        colour_icon_cached(mask,data,width,height,x,y,left,top,right,bottom);
        return;
    }
    flush();
    if (fault) return;
    for (row=0;row<rows;++row,source+=stride,pixels+=width>>1) {
        sx=left-x;index=source+(sx>>4);bit=0x8000U>>(sx&15);
        mi=mask[index];a=255;o=0;
        for (px=left&~1U;px<((right+1)&~1U);++px) {
            shift=(px&1) ? 0:4;
            if (px>=left && px<right) {
                if (mi&bit) {
                    value=data[pixels+(sx>>1)];
                    value=(sx&1) ? value&15:value>>4;
                    a&=~(15U<<shift);o|=value<<shift;
                }
                ++sx;bit>>=1;
                if (!bit && px+1<right) { bit=0x8000U;mi=mask[++index]; }
            }
            if (px&1) { page[at]=a;page[2048+at]=o;++at;a=255;o=0; }
        }
    }
    latch(VbxeOwnerWrite(&display,0x36000UL,page,at));
    if (!fault) latch(VbxeOwnerWrite(&display,0x36800UL,page+2048,at));
    blit_mask(0x36000UL,bytes,GemScreenRows[top]+(left>>1),320,bytes,rows,255,0,4);
    blit_mask(0x36800UL,bytes,GemScreenRows[top]+(left>>1),320,bytes,rows,255,0,3);
}

/* GEM's flat-title dither (0000/5555 rows), expressed as constant packed
 * pixels. Scratch is already white. Each strided command covers every second
 * row, including a preserved neighbour at odd clipped byte edges. */
void GemFramePattern(UWORD left,UWORD top,UWORD right,UWORD bottom,
                     UWORD originX,UWORD originY)
{
    UWORD y=top+(((top-originY)&1)^1),lo=left>>1,hi=right>>1,rows;
    UBYTE ink=map_col[1],value=(originX&1) ? ink<<4:ink;
    ULONG base;
    if (y>=bottom) return;
    rows=(bottom-y+1)>>1;
    base=GemScreenRows[y];
    if (left&1) {
        blit_and(base+lo,640,1,rows,0xf0);
        blit_or(base+lo,640,1,rows,value&15);
        ++lo;
    }
    if (hi>lo) blit_fill(base+lo,640,hi-lo,rows,value);
    if (right&1) {
        blit_and(base+hi,640,1,rows,0x0f);
        blit_or(base+hi,640,1,rows,value&0xf0);
    }
}

/* Native callers never block their service loop waiting for renderer access.
 * A complete unit protects its callback, scratch and final fence. CPU-only
 * presenter work holds no reservation; DMA alone pins access after return. */
#define NATIVE_UNIT(name, parameters, arguments) \
UWORD GemDrawing##name parameters \
{ \
    UWORD status=render_enter(); \
    if (status!=DISPLAY_OK) return status; \
    return render_exit(draw_##name arguments); \
}
NATIVE_UNIT(Close,(void),())
NATIVE_UNIT(Fence,(void),())
NATIVE_UNIT(Copy,(const struct VbxeCopy *copy),(copy))
NATIVE_UNIT(Fill,(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen),(left,top,right,bottom,pen))
NATIVE_UNIT(ScrollStart,(const struct VbxeCopy *copy,UWORD pen,ULONG *id),(copy,pen,id))
NATIVE_UNIT(CopyStart,(const struct VbxeCopy *copy,ULONG *id),(copy,id))
NATIVE_UNIT(Poll,(ULONG id),(id))
NATIVE_UNIT(Text,(UWORD x,UWORD y,const UBYTE *text,UWORD count,UWORD fg,UWORD bg),(x,y,text,count,fg,bg))
NATIVE_UNIT(BackingText,(UWORD x,UWORD y,const UBYTE *text,UWORD count,UWORD fg,UWORD bg),(x,y,text,count,fg,bg))
NATIVE_UNIT(BackingFill,(UWORD x,UWORD y,UWORD width,UWORD height,UWORD pen),(x,y,width,height,pen))
NATIVE_UNIT(TextFill,(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD fg,UWORD bg,UWORD fillX,UWORD fillY,UWORD fillWidth,UWORD fillHeight,
    UWORD fillPen),(x,y,text,count,fg,bg,fillX,fillY,fillWidth,fillHeight,fillPen))
NATIVE_UNIT(TextClip,(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD fg,UWORD bg,UWORD left,UWORD top,UWORD right,UWORD bottom),(x,y,text,count,fg,bg,left,top,right,bottom))
NATIVE_UNIT(Pointer,(UWORD x,UWORD y,UWORD visible),(x,y,visible))
NATIVE_UNIT(Outline,(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD visible),(left,top,right,bottom,visible))
NATIVE_UNIT(InvertRows,(const WORD *rectangles,UWORD count),(rectangles,count))
NATIVE_UNIT(Batch,(UWORD left,UWORD top,UWORD right,UWORD bottom,void (*draw)(void)),(left,top,right,bottom,draw))
NATIVE_UNIT(WidgetBatch,(UWORD left,UWORD top,UWORD right,UWORD bottom,
                            UWORD first,UWORD (*draw)(void)),(left,top,right,bottom,first,draw))

/* A linked, bounded callback executes only after a delegated access grant.
 * Ownership survives Task preemption. The callback must return with no
 * external wait, RPC or caller buffer retained. */
static UWORD drawing_borrow(struct DisplayGrant *grant,UWORD left,UWORD top,
    UWORD right,UWORD bottom,void (*draw)(void *),void *context)
{
    UWORD status;
    status=DisplayEnter(grant);
    if (status!=DISPLAY_OK) return status;
    if (!fault) {
        pointer_erase(left,top,right,bottom);
        if (!fault) {
            if (draw) draw(context);
            else GemSolidFill(left,top,right,bottom,*(const UWORD *)context);
        }
        status=fence_owner();
        if (!fault && outlineVisible && !outlineDrawn) {
            outline_toggle();
            if (!fault) outlineDrawn=1;
        }
        cursor_show();
        if (!fault) status=fence_owner();
    }
    if (fault) status=DISPLAY_DEVICE_FAULT;
    DisplayLeave(grant);
    return status;
}

UWORD GemDrawingBorrow(struct DisplayGrant *grant,UWORD left,UWORD top,
    UWORD right,UWORD bottom,void (*draw)(void *),void *context)
{
    if (!draw || left>=right || right>640 || top>=bottom || bottom>240 || bottom-top>32)
        return DISPLAY_BAD_ARGUMENT;
    return drawing_borrow(grant,left,top,right,bottom,draw,context);
}

UWORD GemDrawingSolidBorrow(struct DisplayGrant *grant,UWORD left,UWORD top,
    UWORD right,UWORD bottom,UWORD pen)
{
    /* Private VDI caller already clipped and bounded this fixed operation. */
    return drawing_borrow(grant,left,top,right,bottom,0,&pen);
}

NATIVE_UNIT(FrameBatch,(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD (*draw)(void)),(left,top,right,bottom,draw))
