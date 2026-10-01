/* Private hosted adapter appended to the selected GEM primitives. G2 owns
 * message/session lifetime; G3 owns hardware acquisition and completion.
 * No renderer call is safe until its caller owns the bound device.
 */
#include "hosted-vdi.h"
#include "operation-checks.inc"

uint16_t GemVdiBind(const VDIDEV *device)
{
    if (vdev || !device || (uint32_t)device > 0xffffffUL ||
        device->w != 640 || device->h != 240 || device->stride != 320 ||
        device->font_w != 8 || device->font_h != 8 || device->font_top != 6 ||
        !device->font_face || !device->fill_rect || !device->glyph ||
        !device->font_changed || !device->line_diag || !device->clear_screen ||
        !device->palette_all || !device->flush)
        return 1;
    vdev = device;
    return 0;
}

uint16_t GemVdiDispatch(uint16_t op, uint16_t sub, uint16_t handle,
                       uint16_t pairs, uint16_t words,
                       const int16_t *points, const int16_t *ints)
{
    uint16_t i, result = GemVdiValidate(op, sub, pairs, words, points, ints);
    if (result)
        return result;
    if (!vdev || (op == 1 ? (handle != 0 || vwk.handle != 0) :
                 (handle != VDI_PHYS_HANDLE || vwk.handle != VDI_PHYS_HANDLE)))
        return 3;
    /* Validate first: no globals or callback state change on rejection. */
    for (i = 0; i < pairs * 2; ++i)
        ptsin[i] = points[i];
    for (i = 0; i < words; ++i)
        intin[i] = ints[i];
    contrl[0] = op; contrl[1] = pairs; contrl[2] = 0;
    contrl[3] = words; contrl[4] = 0; contrl[5] = sub; contrl[6] = handle;
    switch (op) {
    case 1: vdi_v_opnwk(); break;
    case 2: vwk.handle = 0; break;
    case 3: vdi_v_clrwk(); break;
    case 4: break; /* The flush below is the device update. */
    case 6: vdi_v_pline(); break;
    case 8: vdi_v_gtext(); break;
    case 11: vdi_vr_recfl(); break;
    case 17: vdi_vsl_color(); break;
    case 22: vdi_vst_color(); break;
    case 23: vdi_vsf_interior(); break;
    case 25: vdi_vsf_color(); break;
    case 32: vdi_vswr_mode(); break;
    case 129: vdi_vs_clip(); break;
    default: return 1;
    }
    /* This private call submits work; successful service replies will fence. */
    dev_flush();
    return 0;
}

/* Service-facing entry points keep GEM typedefs out of the Exec unit. */
uint16_t GemVdiOpen(int16_t *workout)
{
    static const int16_t input[11]={1,1,1,1,1,1,1,1,1,1,2};
    uint16_t i,status=GemVdiBind(&hosted_vbxe_device);
    if (!status) status=GemVdiDispatch(1,0,0,0,11,0,input);
    if (status) return status;
    for (i=0;i<45;i++) workout[i]=intout[i];
    for (i=0;i<12;i++) workout[45+i]=ptsout[i];
    /* Deterministic initial pixels, before enabling the overlay. */
    return GemVdiDispatch(3,0,1,0,0,0,0);
}
uint16_t GemVdiCommand(uint16_t op,uint16_t sub,uint16_t pairs,uint16_t words,
    const int16_t *points,const int16_t *ints,int16_t *reply)
{
    uint16_t status=GemVdiDispatch(op,sub,1,pairs,words,points,ints);
    if (!status && contrl[4]==1) *reply=intout[0];
    return status;
}
void GemVdiReset(void)
{
    vwk.handle=0;
    vdev=0;
}
