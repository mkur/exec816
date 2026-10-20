; SPDX-License-Identifier: MIT
; Copyright (c) 2026 Michal Kurcewicz and Exec816 contributors.
; Source-level replacements for the two ROM string helpers used by integer BASIC.
.include "atari.inc"
.export fb_intlbuf, fb_skipblank
.segment "RUNTIME"
fb_intlbuf:
    lda #<LBUFF
    sta INBUFF
    lda #>LBUFF
    sta INBUFF+1
    rts
fb_skipblank:
    ldy CIX
loop:
    lda (INBUFF),y
    cmp #9
    beq advance
    cmp #' '
    bne done
advance:
    iny
    bne loop
done:
    sty CIX
    rts
