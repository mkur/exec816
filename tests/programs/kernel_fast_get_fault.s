; One overlay for ten invalid GetMsg calls, selected by VARIANT at runtime.
.p816
.smart
.include "tasks.inc"
.include "ports.inc"
.segment "PROBE"
.a16
.i16
    lda #P_NT_MSGPORT
    sta f:RESULT+6
    lda #P_PA_IGNORE
    sta f:RESULT+11
    tsc
    sec
    sbc #3
    tcs
    inc a
    tax
    lda #.loword(RESULT)
    sta 1,s
    sep #$20
    lda #^RESULT
    sta 3,s
    rep #$20
    lda f:VARIANT
    and #$ff
    bne :+
    lda #0
    sta 1,s
    sep #$20
    sta 3,s
    rep #$20
:
    lda f:VARIANT
    and #$ff
    cmp #1
    bne :+
    lda #$ffff
    sta 1,s
    sep #$20
    sta 3,s
    rep #$20
:
    cmp #2
    bne :+
    lda #0
    sta f:RESULT+6
:
    lda f:VARIANT
    and #$ff
    cmp #3
    bne :+
    lda #$80
    sta f:RESULT+11
:
    cmp #4
    bne :+
    ldx #0
:
    cmp #5
    bne :+
    lda $46
    dec a
    tax
:
    ldy #T_PROFILE_TAG
    lda f:VARIANT
    and #$ff
    cmp #6
    bne :+
    iny
:
    cmp #7
    bne :+
    sep #$20
    lda #P_SERVICE_GET_MSG
    cop $50
    bra returned
:
    .a16
    cmp #8
    bne :+
    sep #$10
:
    cmp #9
    bne :+
    lda #$0121
    bra invoke
:
    lda #P_SERVICE_GET_MSG
invoke:
    cop $50
returned:
    rep #$30
    lda #1
    sta f:REACHED
    rtl
