.setcpu "6502"
.include "calls.inc"
.segment "CODE"
.export MAIN, patch_irq
MAIN:
patch_irq:
    sei                         ; exact loader patch must replace this with NOP
    lda #0
    sta $20
    sta $21
    sta $22
loop:
    inc $20
    bne loop
    inc $21
    bne loop
    inc $22
    lda $22
    cmp #2
    bne loop
    sdx_call PRINTF
    .byte "SDX Process",$9b,0
    lda #7
    rts
