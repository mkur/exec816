.setcpu "6502"
.include "calls.inc"
.segment "CODE"
.export MAIN
MAIN:
    .byte $ad
    near_word handler_pointer
    .byte $ae
    near_word handler_pointer+1
    sdx_call U_SFAIL
    lda #$a0
    sdx_call U_GETATR
    lda #4
    sta $0778
    sdx_call FOPEN              ; missing file: SDX 170, native cause 205
    lda #$ee
    sta $0500
    rts
handler:
    sta $0500
    sdx_call FCLOSEAL
    lda #$a0
    sdx_call U_GETATR
    cmp #1                     ; S: rethrow the same error
    beq same
    cmp #2                     ; DD: deliberately choose a different error
    beq different
    lda #$a0                   ; RRR: recover with new input, then raise 170
    sdx_call U_GETATR
    sdx_call FOPEN
same:
    lda #170
    sdx_call U_FAIL
    rts
different:
    lda #171
    sdx_call U_FAIL
    rts
handler_pointer:
    near_word handler
