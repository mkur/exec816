; SPDX-License-Identifier: MIT
; Copyright (c) 2026 Michal Kurcewicz and Exec816 contributors.
; Convert an unsigned snapshot to Atari FP. IFP preserves FR1 but FMUL does not.
.include "atari.inc"
.include "fastbasic.inc"
.export fb_unsigned32, fp_uint32_scale
.segment "RUNTIME"
fb_unsigned32:
    lda FB_SNAPSHOT+2
    sta FR0
    lda FB_SNAPSHOT+3
    sta FR0+1
    jsr IFP
    ldx #<fp_word_scale
    ldy #>fp_word_scale
    jsr FLD1R
    jsr FMUL
    ldx #<FPSCR
    ldy #>FPSCR
    jsr FST0R
    lda FB_SNAPSHOT
    sta FR0
    lda FB_SNAPSHOT+1
    sta FR0+1
    jsr IFP
    ldx #<FPSCR
    ldy #>FPSCR
    jsr FLD1R
    jmp FADD
fp_word_scale:
    .byte $42,$06,$55,$36,$00,$00
fp_uint32_scale:
    .byte $44,$42,$94,$96,$72,$96
