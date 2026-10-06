.include "exec-abi.inc"
; Qualification only: native caller, arbitrary DBR, exact result/context capture.
.setcpu "65816"
.smart
.include "tasks.inc"
.include "io.inc"
.segment "PROBE"
.a16
.i16
    php
    phb
    lda #26
    sta f:ITEM+14
    sep #$20
    lda #6
    sta f:ITEM+6
    lda #$12
    pha
    plb
    rep #$20
    tsc
    sec
    sbc #17
    tcs
    sta f:CHECKS+12
    lda #.loword(ITEM)
    sta 1,s
    sep #$20
    lda #^ITEM
    sta 3,s
    rep #$20
    .if VARIANT=1
        sei
    .elseif VARIANT=2
        lda #0
        tcd
    .elseif VARIANT=3
        lda #1
        sta f:E816_IRQ_DEPTH
    .elseif VARIANT=4
        lda #1
        sta f:E816_SWITCHING
    .endif
    .if CHECK_PENDING
        sep #$20
        lda #5
        sta f:ITEM+6
        rep #$20
        jsl CALL
        sta f:CHECKS+16
        txa
        sta f:CHECKS+18
        sep #$20
        lda #6
        sta f:ITEM+6
        rep #$20
    .endif
    jsl CALL
    sta f:CHECKS
    txa
    sta f:CHECKS+2
    tya
    sta f:CHECKS+4
    tdc
    sta f:CHECKS+6
    tsc
    sta f:CHECKS+8
    php
    phb
    sep #$20
    pla
    sta f:CHECKS+10
    pla
    sta f:CHECKS+11
    rep #$20
    tsc
    clc
    adc #17
    tcs
    plb
    plp
    lda #1
    sta f:CHECKS+14
    rtl
