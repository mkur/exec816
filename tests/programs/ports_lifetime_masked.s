; Test-only replacement for the native Masked import; 10-byte local peak
; including saved P, six invocation bytes and a nested JSL return address.
.setcpu "65816"
.smart
.segment "PROBE"
.a16
.i16
    php
    sei
    tsc
    sec
    sbc #6
    tcs
    jsl CREATE
    sta 1,s
    txa
    sta 3,s
    ora 1,s
    beq failed
    php
    sep #$20
    pla
    sta f:CHECKS
    rep #$20
    jsl DELETE
    php
    sep #$20
    pla
    sta f:CHECKS+2
    rep #$20
    ldx #1
    bra finished
failed:
    ldx #0
finished:
    tsc
    clc
    adc #6
    tcs
    plp
    txa
    rtl
