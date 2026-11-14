/* Selected from GEM4XE 0.17 src/vdi/dev_vbxe.c; see ../inputs.json. */
/* ---- the pointer ------------------------------------------------------
 * The form as this device keeps it: the sixteen rows the VDI handed over,
 * and the 4bpp strips they expand into. */
static WORD  cur_bg, cur_fg;
static UWORD cur_mask[16], cur_data[16];
static WORD  sv_bx, sv_y, sv_nb, sv_nr;   /* what cursor_save() captured */

/* The pointer is drawn by the blitter.  vsc_form expands the form to 4bpp
 * strips, one pair per parity of x: an AND strip ($0 under the form, $F
 * elsewhere) and an OR strip (the data colour under the data, the mask colour
 * under the rest of the mask, $0 elsewhere).  A show is then the save copy
 * and two blits, one chain, wherever the pointer is; a hide is one copy.
 *
 * The first version plotted the 256 pixels through the MEMAC window.  At
 * ~60 us a pixel that was 12 ms a show -- most of a frame -- paid on every
 * move and twice around every primitive the AES hides the pointer for, and
 * it is what pushed the window sizer's release past the frame it was due in
 * (docs/phase8b.md).  The four strips are a kilobyte written once per form.
 *
 * Like real GEM the pointer ignores the clipping rectangle: it is drawn
 * wherever it is on the screen (the plotted version clipped it, and so did
 * the model -- both were wrong the same way). */
#define CUR_W          16
#define CUR_ROWS       VR_CURSOR_ROWS
#define CUR_STRIDE     VR_CURSOR_STRIDE
#define CUR_BYTES      (CUR_W / 2 + 1)         /* the odd-x span; even pads */
#define CUR_STRIP_LEN  ((uint32_t)CUR_STRIDE * CUR_ROWS)
#define VR_CUR_AND(par) (VR_CURSOR + (uint32_t)(par) * 2 * CUR_STRIP_LEN)
#define VR_CUR_OR(par)  (VR_CUR_AND(par) + CUR_STRIP_LEN)
typedef char cursor_strips_fit_one_page
    [((VR_CURSOR & 0xFFFUL) + VR_CURSOR_LEN <= 0x1000UL) ? 1 : -1];
typedef char cursor_stride_holds_the_odd_span[(CUR_STRIDE >= CUR_BYTES) ? 1 : -1];

void dev_cursor_form(WORD bg_pen, WORD fg_pen, const UWORD *mask,
                    const UWORD *data)
{
    cur_bg = bg_pen;  cur_fg = fg_pen;
    {
        WORD i;
        for (i = 0; i < 16; i++) {
            cur_mask[i] = mask[i];
            cur_data[i] = data[i];
        }
    }
    volatile uint8_t *w;
    WORD par, row, p;
    uint8_t fg = (uint8_t)HW(cur_fg), bg = (uint8_t)HW(cur_bg);

    if (blit_pending())         /* a show may still be reading the strips */
        blit_run();
    w = vram_win(VR_CURSOR);
    for (par = 0; par < 2; par++) {
        volatile uint8_t *pa = w + (uint16_t)(par * 2 * CUR_STRIP_LEN);
        volatile uint8_t *po = pa + (uint16_t)CUR_STRIP_LEN;
        for (row = 0; row < CUR_ROWS; row++) {
            UWORD m = cur_mask[row], d = cur_data[row];
            uint8_t a = 0, o = 0;
            /* strip pixel p holds form column p - par: at odd x the form
             * starts in the low nibble of its first byte */
            for (p = 0; p < 2 * CUR_BYTES; p++) {
                WORD col = (WORD)(p - par);
                uint8_t an = 0x0F, on = 0x00;
                if (col >= 0 && col < CUR_W) {
                    UWORD bit = (UWORD)(0x8000u >> col);
                    if (d & bit)      { an = 0; on = fg; }
                    else if (m & bit) { an = 0; on = bg; }
                }
                if (p & 1) {
                    pa[p >> 1] = (uint8_t)(a | an);
                    po[p >> 1] = (uint8_t)(o | on);
                } else {
                    a = (uint8_t)(an << 4);
                    o = (uint8_t)(on << 4);
                }
            }
            pa += CUR_STRIDE;
            po += CUR_STRIDE;
        }
    }
}

