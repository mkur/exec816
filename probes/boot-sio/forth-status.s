; Test-only native routine called by a Forth CODE word through JSL.
; Use the same pinned COP $00 ROM-call protocol as OF816's CIO bridge.
.setcpu "65816"
.segment "CODE"
.a16
.i16
    php
    rep #$30
    pha
    phx
    phy
    phd
    phb
    sei
    tsc
    tay
    and #$ff00
    cmp #$0100
    beq :+
    lda f:OF_OS_STACK
    tcs
:
    phy
    lda #0
    tcd
    pea 0
    plb
    plb
    sep #$20
.a8
.repeat 12,I
    .if I=0
        lda #$31
    .elseif I=1
        lda #1
    .elseif I=2
        lda #$53
    .elseif I=3
        lda #$40
    .elseif I=4
        lda #<TEST_BUFFER
    .elseif I=5
        lda #>TEST_BUFFER
    .elseif I=6
        lda #3
    .elseif I=8
        lda #4
    .else
        lda #0
    .endif
    sta f:$0300+I
.endrepeat
    rep #$20
.a16
    pea $e459
    cli
    cop $00
    rep #$30
    pla
    sei
    pla
    tcs
    plb
    pld
    ply
    plx
    pla
    plp
    rtl
