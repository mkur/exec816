.setcpu "6502"
.include "calls.inc"
.segment "CODE"
.export MAIN
MAIN:
    lda #$a0
    sdx_call U_GETATR
    lda #4
    sta $0778
    sdx_call FOPEN
    lda #$a0
    sdx_call U_GETATR
    sdx_call FOPEN
    lda #170
    sdx_call U_FAIL
    lda #$ee
    sta $0500
    rts
