/* Exec adapter for the selected GEM renderer. No donor hardware routines link.
 * The donor's window pointers address a private upper-RAM staging page. Flushing
 * it uses the checked G3 transfer and always closes the CPU aperture. A fault
 * latches for the whole call: subsequent void donor callbacks cannot touch HW.
 * Single, synchronous BCBs trade throughput for an explicit completion boundary.
 */
#include "gem-vbxe.h"
#include <hardware/vbxe.h>
#include <stdint.h>

extern uint16_t GemVdiOpen(int16_t *workout);
extern uint16_t GemVdiCommand(uint16_t op, uint16_t sub, uint16_t pairs,
    uint16_t words, const int16_t *points, const int16_t *ints, int16_t *reply);
extern void GemVdiReset(void);

static struct VbxeDisplay display;
static UBYTE page[4096];
static ULONG pageAddress;
static UWORD dirty, fault;

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

static UWORD close_backend(void *context)
{
    UWORD status=GEM_OK;
    (void)context;
    flush();
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
    if (fault) return GEM_DEVICE_FAULT;
    return GemVdiCommand(cmd->opcode,cmd->subopcode,cmd->point_pairs,cmd->int_words,points,ints,reply);
}
static UWORD fence_backend(void *context)
{
    (void)context;
    flush();
    if (!fault) latch(VbxeFence(&display));
    return fault ? GEM_DEVICE_FAULT : GEM_OK;
}
const struct GemBackend GemVbxeBackend={open_backend,command_backend,fence_backend,close_backend,0};
