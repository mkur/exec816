/* Exec816 source interface for the selected GEM AES profile. New native
 * declarations, checked against ports/gem4xe/aes-binding-inputs.json. */
#ifndef EXEC816_GEM_H
#define EXEC816_GEM_H
#include <exec/types.h>
#include <gem/objects.h>
#include <exec816/gem-constants.h>
#define FAR
#define SIMPLE_CALL EXEC_CALL

typedef struct {
    WORD *control, *global, *int_in, *int_out;
    LONG *addr_in, *addr_out;
} AESPB;
typedef struct { WORD *contrl, *intin, *ptsin, *intout, *ptsout; } VDIPB;
#define MD_REPLACE 1
#define FIS_SOLID 1

typedef struct { WORD m_out, m_x, m_y, m_w, m_h; } MOBLK;
#define END_UPDATE 0
#define BEG_UPDATE 1
#define END_MCTRL 2
#define BEG_MCTRL 3
#define BEG_CHECK 0x0100

WORD appl_init(void);
WORD appl_exit(void);
WORD graf_handle(WORD *wchar, WORD *hchar, WORD *wbox, WORD *hbox);
void v_opnvwk(WORD *work_in, WORD *handle, WORD *work_out);
void v_clsvwk(WORD handle);
void v_bar(WORD handle, const WORD *pxy);
void v_gtext(WORD handle, WORD x, WORD y, const char *text);
void vs_clip(WORD handle, WORD clip, const WORD *pxy);
WORD vswr_mode(WORD handle, WORD mode);
WORD vsf_interior(WORD handle, WORD style);
WORD vsf_color(WORD handle, WORD color);
WORD vst_color(WORD handle, WORD color);
void EXEC_CALL vdi_call(VDIPB *pb);
WORD appl_write(WORD id, WORD length, const WORD *message);
WORD evnt_mesag(WORD *message);
WORD evnt_keybd(void);
WORD evnt_button(WORD clicks, WORD mask, WORD state,
    WORD *x, WORD *y, WORD *buttons, WORD *qualifiers);
WORD evnt_timer(UWORD lo, UWORD hi);
WORD wind_update(WORD code);
WORD wind_create(WORD kind, WORD x, WORD y, WORD w, WORD h);
WORD wind_open(WORD handle, WORD x, WORD y, WORD w, WORD h);
WORD wind_close(WORD handle);
WORD wind_delete(WORD handle);
WORD wind_get(WORD handle, WORD field, WORD *o1, WORD *o2, WORD *o3, WORD *o4);
WORD wind_set(WORD handle, WORD field, WORD w1, WORD w2, WORD w3, WORD w4);
WORD wind_set_str(WORD handle, WORD field, const char *str);
WORD wind_calc(WORD type, WORD kind, WORD x, WORD y, WORD w, WORD h,
    WORD *ox, WORD *oy, WORD *ow, WORD *oh);
WORD evnt_multi(WORD flags, WORD bclk, WORD bmsk, WORD bst,
    WORD m1flags, WORD m1x, WORD m1y, WORD m1w, WORD m1h,
    WORD m2flags, WORD m2x, WORD m2y, WORD m2w, WORD m2h,
    WORD *msg, WORD tlo, WORD thi,
    WORD *mx, WORD *my, WORD *mb, WORD *ks, WORD *kr, WORD *br);
WORD evnt_multi_moblk(UWORD flags, WORD bclk, UWORD bmsk, UWORD bst,
    const MOBLK *m1, const MOBLK *m2, WORD *msg, UWORD tlo, UWORD thi,
    WORD *mx, WORD *my, WORD *mb, WORD *ks, WORD *kr, WORD *br);
void EXEC_CALL aes_call(AESPB *pb);
#endif
