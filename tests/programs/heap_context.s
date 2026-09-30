; Qualification-only raw memory COP, entered in place of Main's prologue.
.setcpu "65816"
.smart
.include "tasks.inc"
.include "heap.inc"
.segment "PROBE"
.a16
.i16
    phb
    tsc
    sec
    sbc #5
    tcs
    sta f:CHECKS+12
    lda #0
    sta 1,s
    lda #8                    ; MEMF_TOTAL, four-byte packet
    sta 3,s
    sep #$20
    lda #$12
    pha
    plb
    rep #$20
    tsc
    inc a
    tax
    ldy #T_PROFILE_TAG
    lda #H_SERVICE_AVAIL_MEM
    .if VARIANT=1
        sep #$20
    .elseif VARIANT=2
        sep #$10
    .elseif VARIANT=3
        ldy #$0000
    .elseif VARIANT=4
        ldx #$47ff             ; packet extends beyond root stack
    .elseif VARIANT=5
        lda #$011e             ; nonzero reserved A bits
    .elseif VARIANT=6
        lda #0
        tcd
        jsl AVAIL              ; wrapper must reject wrong task DP
    .endif
    cop $50
    rep #$30
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
    adc #5
    tcs
    plb
    lda #1
    sta f:CHECKS+14
    rtl
