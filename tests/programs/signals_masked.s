; Replace the test Main entry before its prologue. Native task ABI, M=X=0.
; Calls the same generated wrappers as Action code with caller I set.
.setcpu "65816"
.smart
.include "tasks.inc"
.segment "PROBE"
.export start
.a16
.i16
start:
    sei
    sep #$20
    lda #31
    pha
    rep #$20
    jsl ALLOC
    sta f:CHECKS
    tsc
    inc a
    tcs
    php
    sep #$20
    pla
    sta f:CHECKS+2
    rep #$20
    ; SetSignal($80000001,$ffffffff): 8-byte packet plus trailing ABI pad.
    sep #$20
    lda #0
    pha
    rep #$20
    lda #$ffff
    pha
    pha
    lda #$8000
    pha
    lda #1
    pha
    jsl SET
    sta f:VALUES
    txa
    sta f:VALUES+2
    tsc
    clc
    adc #9
    tcs
    php
    sep #$20
    pla
    sta f:CHECKS+4
    lda #31
    pha
    rep #$20
    jsl FREE
    tsc
    inc a
    tcs
    php
    sep #$20
    pla
    sta f:CHECKS+6
    ; Snapshot through SetSignal(0,0). FreeSignal must retain pending bits.
    lda #0
    pha
    rep #$20
    lda #0
    pha
    pha
    pha
    pha
    jsl SET
    sta f:VALUES+4
    txa
    sta f:VALUES+6
    tsc
    clc
    adc #9
    tcs
    php
    sep #$20
    pla
    sta f:CHECKS+8
    rep #$20
.if WAIT_TEST
    .if WAIT_TEST = 2
        ; Clear the received mask before testing a masked blocking Wait.
        sep #$20
        lda #0
        pha
        rep #$20
        lda #$ffff
        pha
        pha
        lda #0
        pha
        pha
        jsl SET
        tsc
        clc
        adc #9
        tcs
    .endif
    sep #$20
    lda #0
    pha
    rep #$20
    lda #0
    pha
    lda #1
    pha
    jsl WAIT_CALL
    lda #1
    sta f:CHECKS+10
    tsc
    clc
    adc #5
    tcs
.endif
    cli
    rtl
