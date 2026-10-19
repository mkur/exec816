.setcpu "6502"
.include "calls.inc"
.segment "CODE"
.export MAIN
MAIN:
    sdx_call PRINTF
    .byte "AB",0
    lda #'C'
    sdx_call PUTC
    ldx #0
full:
    lda #'x'
    sdx_call PUTC
    inx
    bne full
    ldx #44
rest:
    lda #'x'
    sdx_call PUTC
    dex
    bne rest
    sdx_call PRINTF
    .byte ":key? ",0
    sdx_call U_GETKEY
    sta $0500
    sdx_call PUTC
    sdx_call PRINTF
    .byte $9b,"tail",0
    ; A nonzero argument exercises error exit after a partial final record.
    ldx $100a
    lda $103f,x
    cmp #'F'
    bne done
    lda #170
    sdx_call U_FAIL
done:
    lda #0
    rts
