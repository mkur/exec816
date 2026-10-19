.setcpu "6502"
.include "calls.inc"
.segment "CODE"
.export MAIN
MAIN:
    .byte $ad
    near_word table_pointer
    .byte $ae
    near_word table_pointer+1
    ldy #4
    sdx_call U_SLASH
    sta $0500
    lda #$a0
    sdx_call U_GETATR
    php
    pla
    sta $0501
    lda $0779
    sta $0502
    lda #0
    rts
table_pointer:
    near_word options
options:
    .byte 0,'C',0,'H'
