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
#include <hardware/vbxe.h>
#include <stdint.h>
#include <string.h>

extern uint16_t GemVdiOpen(int16_t *workout);
extern uint16_t GemVdiCommand(uint16_t op, uint16_t sub, uint16_t pairs,
    uint16_t words, const int16_t *points, const int16_t *ints, int16_t *reply);
extern void GemVdiReset(void);
extern UWORD GemBitmapFill(UWORD,UWORD,UWORD,UWORD,UWORD);
extern UWORD GemBitmapText(UWORD,UWORD,const UBYTE *,UWORD,UWORD,UWORD);

static struct VbxeDisplay display;
static UBYTE page[4096];
static ULONG pageAddress;
static UWORD dirty, fault;
static UBYTE commands[VBXE_BCB_BYTES];
static UWORD commandCount;
static ULONG commandWork;


static void latch(UWORD status) { if (status && !fault) fault=status; }
static void drain(void)
{
    if (commandCount && !fault) latch(VbxeSubmit(&display,commands,commandCount));
    commandCount=0;
    commandWork=0;
}
static void flush(void)
{
    drain();
    if (dirty && !fault) latch(VbxeWrite(&display,pageAddress,page,sizeof(page)));
    dirty=0;
}
volatile uint8_t *vram_win(uint32_t address)
{
    ULONG base=address&~0xfffUL;
    drain();
    if (!dirty || base!=pageAddress) {
        flush();
        if (!fault) latch(VbxeRead(&display,base,page,sizeof(page)));
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
    /* Check the whole operation before an arena flush could draw a prefix. */
    if (mode>6 || !VbxeBlitExtent(source,ss,bytes,rows) ||
        !VbxeBlitExtent(dest,ds,bytes,rows)) {
        latch(DISPLAY_BAD_ARGUMENT); return;
    }
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
 * supplies four/five bytes by eight rows. Submission still validates every
 * address and record; this private producer avoids general rectangle setup. */
void blit_glyph(uint32_t source,uint16_t stride,uint32_t dest,uint16_t bytes,uint8_t ink)
{
    UBYTE *r;
    UWORD work=bytes*24;
    if (fault) return;
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
    if (!fault) latch(VbxePalette(&display,rgb));
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
    status=GemVdiOpen(out);
    flush();
    if (!status && !fault) latch(VbxeShow(&display));
    if (status || fault) { GemDrawingClose(); return DISPLAY_DEVICE_FAULT; }
    return DISPLAY_OK;
}
UWORD GemDrawingClose(void)
{
    UWORD status=DISPLAY_OK;
    if (display.lease.state) {
        status=DisplayCheck(&display.lease);
        if (status!=DISPLAY_OK) return status;
        flush();
        if (display.lease.state) status=VbxeClose(&display);
    }
    GemVdiReset();
    dirty=commandCount=0; commandWork=0;
    return fault ? DISPLAY_DEVICE_FAULT : status;
}
UWORD GemDrawingFence(void)
{
    UWORD status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    flush();
    if (!fault) latch(VbxeFence(&display));
    return fault ? DISPLAY_DEVICE_FAULT : DISPLAY_OK;
}
UWORD GemDrawingCopy(const struct VbxeCopy *copy)
{
    UWORD status=GemDrawingFence();
    if (status!=DISPLAY_OK) return status;
    status=VbxeCopyRect(&display,copy);
    if (status==DISPLAY_DEVICE_FAULT) latch(status);
    return status;
}
UWORD GemDrawingFill(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen)
{
    UWORD status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (GemBitmapFill(left,top,right,bottom,pen)) return DISPLAY_BAD_ARGUMENT;
    return GemDrawingFence();
}
UWORD GemDrawingText(UWORD x,UWORD y,const UBYTE *text,UWORD count,UWORD fg,UWORD bg)
{
    UWORD status=DisplayCheck(&display.lease);
    if (status!=DISPLAY_OK) return status;
    if (fault) return DISPLAY_DEVICE_FAULT;
    if (GemBitmapText(x,y,text,count,fg,bg)) return DISPLAY_BAD_ARGUMENT;
    return GemDrawingFence();
}

#ifndef GEM_DRAWING_ONLY
#define CURSOR_SAVE 0x37000UL
#define CURSOR_AND  0x37100UL
#define CURSOR_OR   0x37200UL
static UWORD cursorX, cursorY, cursorVisible, cursorDrawn, cursorBytes, cursorRows;
static ULONG cursorAddress;
static UWORD cursorMaskParity;
#include "gem-cursor-masks.h"


/* Cursor transfers use the same fenced driver as drawing. The existing CPU
 * page stages masks only after donor writes have been flushed. Glyph scratch
 * remains untouched. Save/restore includes both edge nibbles; the masks retain
 * the neighboring pixels when an odd coordinate uses nine packed bytes. */
static void cursor_hide(void)
{
    flush();
    if (cursorDrawn && !fault)
        latch(VbxeBlit(&display,CURSOR_SAVE,16,cursorAddress,320,cursorBytes,cursorRows,255,0,0));
    cursorDrawn=0;
}
static void cursor_show(void)
{
    UWORD width;
    if (!cursorVisible || cursorDrawn || fault) return;
    flush();
    if (fault) return;
    width=640-cursorX;
    if (width>16) width=16;
    cursorRows=240-cursorY;
    if (cursorRows>16) cursorRows=16;
    cursorBytes=((cursorX&1)+width+1)/2;
    cursorAddress=(ULONG)cursorY*320+cursorX/2;
    latch(VbxeBlit(&display,cursorAddress,320,CURSOR_SAVE,16,cursorBytes,cursorRows,255,0,0));
    if (fault) return;
    /* Prepacked masks keep redraw/cursor work bounded in raw C builds too.
     * Clipping changes the blit extent; unused edge nibbles remain preserved. */
    if (cursorMaskParity!=(cursorX&1)) {
        memcpy(page,cursorMasks[cursorX&1],512);
        latch(VbxeWrite(&display,CURSOR_AND,page,512));
        if (!fault) cursorMaskParity=cursorX&1;
    }
    if (!fault) latch(VbxeBlit(&display,CURSOR_AND,16,cursorAddress,320,cursorBytes,cursorRows,255,0,4));
    if (!fault) latch(VbxeBlit(&display,CURSOR_OR,16,cursorAddress,320,cursorBytes,cursorRows,255,0,3));
    if (!fault) cursorDrawn=1;
}
static UWORD cursor_backend(void *context,const struct GemCursor *cursor)
{
    (void)context;
    cursor_hide();
    cursorX=cursor->x;
    cursorY=cursor->y;
    cursorVisible=cursor->visible;
    cursor_show();
    return fault ? GEM_DEVICE_FAULT : GEM_OK;
}
static UWORD close_backend(void *context)
{
    UWORD status=GEM_OK;
    (void)context;
    cursor_hide();
    cursorVisible=0;
    status=GemDrawingClose();
    return status==DISPLAY_OK ? GEM_OK : GEM_DEVICE_FAULT;
}
static UWORD open_backend(void *context,WORD *out)
{
    UWORD status;
    (void)context;
    cursorX=cursorY=cursorVisible=cursorDrawn=cursorBytes=cursorRows=0;
    cursorAddress=0;
    cursorMaskParity=2;
    status=GemDrawingOpen(out);
    if (status!=DISPLAY_OK)
        return status==DISPLAY_BUSY ? GEM_BUSY : status==DISPLAY_UNSUPPORTED ? GEM_UNSUPPORTED : GEM_DEVICE_FAULT;
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
    (void)context;
    if (cmd->opcode!=17 && cmd->opcode!=22 && cmd->opcode!=23 &&
        cmd->opcode!=25 && cmd->opcode!=32 && cmd->opcode!=129 &&
        cursor_intersects(cmd,points)) cursor_hide();
    if (fault) return GEM_DEVICE_FAULT;
    return GemVdiCommand(cmd->opcode,cmd->subopcode,cmd->point_pairs,cmd->int_words,points,ints,reply);
}
static UWORD fence_backend(void *context)
{
    (void)context;
    flush();
    cursor_show();
    if (!fault) latch(VbxeFence(&display));
    return fault ? GEM_DEVICE_FAULT : GEM_OK;
}
const struct GemBackend GemVbxeBackend={open_backend,command_backend,fence_backend,close_backend,cursor_backend,0};

#endif
