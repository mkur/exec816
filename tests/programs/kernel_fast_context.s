; Runtime-selected raw COP checks, replacing only the fixture's Main routine.
.p816
.smart
.include "tasks.inc"
.segment "PROBE"
.a16
.i16
    php
    phd
    phb
    tsc
    sta f:RESULT+14
    tdc
    sta f:RESULT+16
    lda f:VARIANT
    and #$ff
    cmp #7
    bne ordinary
    ldx #129
overflow:
    ldy #T_PROFILE_TAG
    lda #T_SERVICE_FORBID
    cop $50
    dex
    bne overflow
ordinary:
    lda f:VARIANT
    and #$ff
    cmp #8
    bne :+
    sei
:
    cmp #1
    bne :+
    ldy #$0100
    bra selected_tag
:
    ldy #T_PROFILE_TAG+$ab
selected_tag:
    cmp #5
    bne :+
    lda #0
    tcd
:
    ldx #$1234
    sep #$20
    lda #$12
    pha
    plb
    lda f:VARIANT
    cmp #2
    beq narrow_a
    cmp #3
    bne :+
    sep #$10
:
    rep #$20
    lda f:VARIANT
    and #$ff
    cmp #6
    bne :+
    lda #T_SERVICE_PERMIT
    bra invoke
:
    cmp #4
    bne :+
    lda #$0115
    bra invoke
:
    lda #T_SERVICE_FORBID
    bra invoke
narrow_a:
    lda #T_SERVICE_FORBID
invoke:
    sec
    clv
    sed
    cop $50
    php
    rep #$30
    sta f:RESULT
    txa
    sta f:RESULT+2
    tya
    sta f:RESULT+4
    tdc
    sta f:RESULT+6
    tsc
    sta f:RESULT+8
    phb
    sep #$20
    pla
    sta f:RESULT+10
    pla
    sta f:RESULT+11
    rep #$30
    cld
    jsl PERMIT
    plb
    pld
    plp
    lda #1
    sta f:REACHED
    rtl
