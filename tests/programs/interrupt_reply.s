; Diagnostic overlay: retain one fixture-owned message, reply in a real IRQ,
; and check every register without relying on the compiled caller's ABI.
.setcpu "65816"
.smart
.macpack longbranch
.include "tasks.inc"
.include "exec-abi.inc"
.segment "PROBE"
.a16
.i16
.export arm, consumer

arm:
    php
    sei
    lda 5,s
    sta f:CONTROL
    sep #$20
    lda 7,s
    sta f:CONTROL+2
    lda #1
    sta f:CONTROL+3
    rep #$20
.ifdef INVALID_NATIVE
    lda f:CONTROL+30
    and #$ff
    bne :+
    ; A Task cannot acquire interrupt authority by masking IRQs.
    lda f:CONTROL+2
    and #$ff
    tax
    lda f:CONTROL
    jsl REPLY
:
.endif
    plp
    rtl

.a8
consumer:
    rep #$30
    tsc
    cmp #$0200
    jcc original
    lda f:CONTROL+3
    and #$ff
    jeq original
    php
    phd
    phb
    sep #$20
    lda #0
    sta f:CONTROL+3
    lda #$12
    pha
    plb
    rep #$20
    lda #$4321
    tcd
    tsc
    sta f:CONTROL+8
    lda f:CONTROL
    ldx #0
    sep #$20
    lda f:CONTROL+2
    sta f:CONTROL+15
    rep #$20
    lda f:CONTROL+2
    and #$ff
    tax
    lda f:CONTROL
    ldy #$abcd
    clv
    sed
    sec
    php
.ifdef INVALID_NATIVE
    lda f:CONTROL+30
    and #$ff
    cmp #1
    bne :+
    cli
:
    cmp #7
    bne :+
    sep #$20
    lda #1
    sta f:PORT+11
    rep #$20
:
    lda f:CONTROL+30
    and #$ff
    cmp #8
    bne :+
    sep #$20
    lda #1
    sta f:E816_OS_BUSY
    rep #$20
:
    lda f:CONTROL
    ; Read the variant through Y, then restore the diagnostic Y value.
    pha
    lda f:CONTROL+30
    and #$ff
    tay
    pla
    cpy #4
    bne :+
    lda #0
    ldx #0
:
    cpy #5
    bne :+
    inc a
:
    cpy #6
    bne :+
    ldx #$100
:
    cpy #2
    bne :+
    sep #$20
:
    cpy #3
    bne :+
    sep #$10
:
.endif
    jsl REPLY
.ifdef INVALID_NATIVE
    jml failed
    .a16
    .i16
.endif
    php
    sta f:CONTROL+12
    txa
    sta f:CONTROL+14
    tya
    sta f:CONTROL+16
    sep #$20
    pla
    cmp 1,s
    jne failed
    rep #$20
    cld
    lda f:CONTROL+12
    cmp f:CONTROL
    jne failed
    lda f:CONTROL+2
    and #$ff
    cmp f:CONTROL+14
    jne failed
    lda f:CONTROL+16
    cmp #$abcd
    jne failed
    tdc
    cmp #$4321
    jne failed
    tsc
    inc a
    cmp f:CONTROL+8
    jne failed
    phb
    sep #$20
    pla
    cmp #$12
    jne failed
    pla                          ; discard expected flags
    rep #$20
    lda f:CONTROL+4
    inc a
    sta f:CONTROL+4
    plb
    pld
    plp
original:
    ; Preserve the original signal_post prologue and continue its real binding
    ; publication. This independent signal also wakes PA_IGNORE/null cases.
    ldx #T_SERIAL_BINDING-T_BASE
    rep #$20
    phd
    tsc
    jml POST_CONTINUE
failed:
    rep #$30
    cld
    lda #$ffed
    pha
    jsl FAULT
