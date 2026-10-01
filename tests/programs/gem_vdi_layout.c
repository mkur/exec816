#include <stddef.h>
#include "hosted-vdi.h"
#include "vdi/font.h"

__attribute__((section("exec_layout")))
const uint16_t GemLayout[] = {
    sizeof(WORD), sizeof(UWORD), sizeof(uint32_t), sizeof(void *),
    sizeof(vdev->fill_rect), sizeof(vwk.dev), sizeof(vdi_font),
    sizeof(contrl), sizeof(intin), sizeof(ptsin), sizeof(intout), sizeof(ptsout)
};
