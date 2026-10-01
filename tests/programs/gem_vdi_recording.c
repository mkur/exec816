/* Exercise imported C algorithms without acquiring or writing the hardware. */
#include "hosted-vdi.h"
#include "vdi/font.h"

extern const uint8_t font8x8[];
static uint16_t errors, bound, events, flushes, fills, glyphs, diagonals, clears;
static int16_t last[5];
volatile uint32_t font_checksum;

static void check(uint16_t okay) { if (!okay) ++errors; }
static void fill(WORD x1, WORD y1, WORD x2, WORD y2, WORD colour)
{
    ++events; ++fills;
    last[0] = x1; last[1] = y1; last[2] = x2; last[3] = y2; last[4] = colour;
}
static void glyph(WORD ch, WORD x, WORD y, WORD overlay)
{
    ++events; ++glyphs;
    check(ch == 65 && x == 8 && y == 8 && overlay == 1);
}
static void font_changed(void)
{
    uint16_t i;
    const uint8_t *font = (const uint8_t *)vdi_font;
    uint32_t sum = 0;
    ++events;
    check(vdi_font == (uint32_t)font8x8 && vdi_font >= 0x10000UL);
    for (i = 0; i < 2048; ++i)
        sum = (sum << 1) ^ (sum >> 31) ^ font[i];
    font_checksum = sum;
}
static void diagonal(WORD x1, WORD y1, WORD x2, WORD y2, UWORD mask)
{
    ++events; ++diagonals;
    check(x1 == 8 && y1 == 8 && x2 == 15 && y2 == 15 && mask == 0xffff);
}
static void clear(void) { ++events; ++clears; }
static void palette(const uint8_t *rgb)
{
    ++events;
    check((uint32_t)rgb >= 0x10000UL && rgb[0] == 255 && rgb[3] == 0 && rgb[6] == 255);
}
static void flush(void) { ++events; ++flushes; }

static const VDIDEV recording = {
    .w = 640, .h = 240, .stride = 320,
    .font_w = 8, .font_h = 8, .font_top = 6, .font_ascent = 6, .font_half = 4,
    .font_descent = 1, .font_bottom = 1, .font_point = 9, .font_face = font8x8,
    .fill_rect = fill, .glyph = glyph, .font_changed = font_changed,
    .line_diag = diagonal, .clear_screen = clear, .palette_all = palette,
    .flush = flush, .text_prefill = 1
};

uint16_t GemProbeRun(void)
{
    static const int16_t work[] = {1,1,1,1,1,1,1,1,1,1,2};
    static const int16_t clip[] = {20,20,8,8};
    static const int16_t bar[] = {30,25,1,2};
    static const int16_t line[] = {30,10,1,10};
    static const int16_t diag[] = {8,8,15,15};
    static const int16_t text[] = {8,14};
    int16_t value = 1, letter = 65;
    uint16_t before;
    errors = events = flushes = fills = glyphs = diagonals = clears = 0;
    if (!bound) {
        check(GemVdiBind(0) == 1);
        check(GemVdiBind(&recording) == 0);
        check(GemVdiBind(&recording) == 1);
        bound = 1;
    }
    check((uint32_t)&hosted_vbxe_device >= 0x10000UL);
    check(hosted_vbxe_device.font_face == font8x8);
    check(GemVdiDispatch(1,0,0,0,11,0,work) == 0);
    check(contrl[6] == 1 && contrl[4] == 45 && contrl[2] == 6);
    check(intout[0] == 639 && intout[1] == 239 && intout[13] == 16);
    check(intout[8] == 0 && intout[11] == 0 && intout[14] == 1);
    check(GemVdiDispatch(129,0,1,2,1,clip,&value) == 0);
    check(GemVdiDispatch(23,0,1,0,1,0,&value) == 0);
    check(GemVdiDispatch(32,0,1,0,1,0,&value) == 0);
    value = 3;
    check(GemVdiDispatch(25,0,1,0,1,0,&value) == 0);
    check(GemVdiDispatch(11,1,1,2,0,bar,0) == 0);
    check(fills == 1 && last[0] == 8 && last[1] == 8 && last[2] == 20 && last[3] == 20 && last[4] == 3);
    value = 4;
    check(GemVdiDispatch(17,0,1,0,1,0,&value) == 0);
    check(GemVdiDispatch(6,0,1,2,0,line,0) == 0);
    check(fills == 2 && last[0] == 8 && last[1] == 10 && last[2] == 20 && last[3] == 10 && last[4] == 4);
    check(GemVdiDispatch(6,0,1,2,0,diag,0) == 0);
    check(GemVdiDispatch(22,0,1,0,1,0,&value) == 0);
    check(GemVdiDispatch(8,0,1,1,1,text,&letter) == 0);
    check(fills == 3 && last[0] == 8 && last[1] == 8 && last[2] == 15 && last[3] == 15 && last[4] == 0);
    check(glyphs == 1 && diagonals == 1);
    /* Rejections must not change attributes, parameter arrays or callbacks. */
    before = events;
    value = 16;
    check(GemVdiDispatch(25,0,1,0,1,0,&value) == 1);
    check(GemVdiDispatch(6,0,1,17,0,line,0) == 1);
    check(GemVdiDispatch(8,0,1,1,65,text,&letter) == 1);
    check(GemVdiDispatch(100,0,1,0,0,0,0) == 1);
    check(GemVdiDispatch(8,0,1,1,1,0,&letter) == 2);
    check(GemVdiDispatch(8,0,1,1,1,(const int16_t *)0x1000000UL,&letter) == 2);
    check(GemVdiDispatch(3,0,2,0,0,0,0) == 3);
    check(events == before && vwk.fill_color == 3 && contrl[0] == 8 && intin[0] == 65);
    check(GemVdiDispatch(3,0,1,0,0,0,0) == 0 && clears == 1);
    check(GemVdiDispatch(4,0,1,0,0,0,0) == 0);
    check(GemVdiDispatch(2,0,1,0,0,0,0) == 0);
    check(GemVdiDispatch(3,0,1,0,0,0,0) == 3);
    check(flushes == 14);
    return errors;
}
