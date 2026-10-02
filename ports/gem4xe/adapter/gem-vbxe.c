/* Exec adapter for the selected GEM renderer. No donor hardware routines link.
 * The donor's window pointers address a private upper-RAM staging page. Flushing
 * it uses the checked G3 transfer and always closes the CPU aperture. A fault
 * latches for the whole call: subsequent void donor callbacks cannot touch HW.
 * Single, synchronous BCBs trade throughput for an explicit completion boundary.
 */
#include "gem-vbxe.h"
#include <hardware/vbxe.h>
#include <stdint.h>
#include <string.h>

extern uint16_t GemVdiOpen(int16_t *workout);
extern uint16_t GemVdiCommand(uint16_t op, uint16_t sub, uint16_t pairs,
    uint16_t words, const int16_t *points, const int16_t *ints, int16_t *reply);
extern void GemVdiReset(void);

static struct VbxeDisplay display;
static UBYTE page[4096];
static ULONG pageAddress;
static UWORD dirty, fault;
#define CURSOR_SAVE 0x37000UL
#define CURSOR_AND  0x37100UL
#define CURSOR_OR   0x37200UL
static UWORD cursorX, cursorY, cursorVisible, cursorDrawn, cursorBytes, cursorRows;
static ULONG cursorAddress;
/* Fixed 16x16 arrow, hotspot (0,0): black outline, white interior. */
static const UWORD cursorBlack[16]={0x8000,0xc000,0xa000,0x9000,0x8800,0x8400,0x8200,0x8100,0x8080,0x87c0,0x9400,0xa400,0xca00,0x8a00,0x0600,0x0000};
static const UWORD cursorWhite[16]={0x0000,0x0000,0x4000,0x6000,0x7000,0x7800,0x7c00,0x7e00,0x7f00,0x7800,0x6800,0x4800,0x0400,0x0400,0x0000,0x0000};


static void latch(UWORD status) { if (status && !fault) fault=status; }
static void flush(void)
{
    if (dirty && !fault) latch(VbxeWrite(&display,pageAddress,page,sizeof(page)));
    dirty=0;
}
volatile uint8_t *vram_win(uint32_t address)
{
    ULONG base=address&~0xfffUL;
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
uint8_t blit_pending(void) { return 0; }
void blit_mask(uint32_t source, uint16_t ss, uint32_t dest, uint16_t ds,
               uint16_t bytes, uint16_t rows, uint8_t am, uint8_t xm, uint8_t mode)
{
    flush();
    if (!fault) latch(VbxeBlit(&display,source,ss,dest,ds,bytes,rows,am,xm,mode));
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
    UWORD width,row,col,offset,shift,bit;
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
    memset(page,255,256);
    memset(page+256,0,256);
    for (row=0;row<cursorRows;++row) for (col=0;col<width;++col) {
        bit=0x8000U>>col;
        if ((cursorBlack[row]|cursorWhite[row])&bit) {
            offset=row*16+((cursorX&1)+col)/2;
            shift=((cursorX+col)&1) ? 0 : 4;
            page[offset]&=(UBYTE)~(15U<<shift);
            if (cursorBlack[row]&bit) page[256+offset]|=(UBYTE)(15U<<shift);
        }
    }
    latch(VbxeWrite(&display,CURSOR_AND,page,512));
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
    GemVdiReset();
    /* Recovery may already have quiesced/released. A retained FAULTED lease
     * never returns from the driver's reset-required path. */
    if (display.lease.state && VbxeClose(&display)!=DISPLAY_OK) status=GEM_DEVICE_FAULT;
    if (fault) status=GEM_DEVICE_FAULT;
    dirty=0;
    return status;
}
static UWORD open_backend(void *context,WORD *out)
{
    UWORD status;
    (void)context;
    dirty=fault=0;
    cursorX=cursorY=cursorVisible=cursorDrawn=cursorBytes=cursorRows=0;
    cursorAddress=0;
    status=VbxeOpen(&display);
    if (status!=DISPLAY_OK)
        return status==DISPLAY_BUSY ? GEM_BUSY : status==DISPLAY_UNSUPPORTED ? GEM_UNSUPPORTED : GEM_DEVICE_FAULT;
    status=GemVdiOpen(out);
    flush();
    if (!status && !fault) latch(VbxeShow(&display));
    if (status || fault) { close_backend(context); return GEM_DEVICE_FAULT; }
    return GEM_OK;
}
static UWORD command_backend(void *context,const struct GemCommand *cmd,
    const WORD *points,const WORD *ints,WORD *reply)
{
    (void)context;
    if (cmd->opcode!=17 && cmd->opcode!=22 && cmd->opcode!=23 &&
        cmd->opcode!=25 && cmd->opcode!=32 && cmd->opcode!=129) cursor_hide();
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
