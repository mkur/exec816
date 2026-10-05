#include "vdi/vdi.h"
#include "vdi/vdidev.h"

uint16_t GlyphClipTop;

/* Partial rows, both X parities, one-nibble clips, zero/nonzero ink,
 * replace/transparent modes, empty glyphs and all four screen edges. */
void ClippedGlyphsProbe(void)
{
    uint16_t i;
    WORD x,y;
    Vwk saved=vwk;
    for (i=0;i<64;i++) {
        x=16+(i%8)*32+(i&1);y=8+(i/8)*16;
        if (y<GlyphClipTop || y>=GlyphClipTop+16) continue;
        vwk.wrt_mode=(i>>1)&1;
        vwk.text_color=(i&4) ? 0 : 2;
        vwk.clip=1;
        vwk.xmn_clip=x+1;vwk.xmx_clip=x+1+(i>>3);
        vwk.ymn_clip=y+1;vwk.ymx_clip=y+5;
        dev_glyph((i%7) ? 'A' : ' ',x,y,0);
    }
    vwk.clip=0;vwk.wrt_mode=1;vwk.text_color=0;
    if (GlyphClipTop==144) {
        dev_glyph('A',-3,150,0);
        dev_glyph('A',637,150,0);
    }
    if (GlyphClipTop==0) dev_glyph('A',300,-3,0);
    if (GlyphClipTop==224) dev_glyph('A',300,237,0);
    vwk=saved;
}
