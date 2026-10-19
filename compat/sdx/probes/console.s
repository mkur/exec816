.setcpu "6502"
.include "calls.inc"
.segment "CODE"
.export MAIN
MAIN:
    sdx_call PRINTF
    .byte "discard",$7d,"AB",$7e,"C",$7f,"Z",$9b,0
    lda #0
    rts
