; Test-only source: retain one request, notify at a controlled real VBI, then
; suppress further VBI. The deferred callback uses the public native reply.
.setcpu "65816"
.smart
.macpack longbranch
.include "tasks.inc"
.include "exec-abi.inc"
.include "native-interrupts.inc"
.segment "PROBE"
.a16
.i16
.export arm, raw_notify, complete
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
    sta f:NI_ENABLED+NI_SOURCE_PROBE
    lda #0
    sta f:E816_PROBE0
    sta f:E816_PROBE0+1
    rep #$20
    plp
    rtl

; E=1, M=X=1. Do not alter X/Y or the hidden accumulator byte.
.a8
.i8
raw_notify:
    lda f:CONTROL+3
    bne raw_armed
    lda #$80
    sta f:E816_PROBE0+1             ; release pre-arm initialization checkpoints
    rtl
raw_armed:
    lda f:E816_PROBE0
    beq raw_done
    lda #0
    sta f:CONTROL+3
    sta f:$d40e
    lda #$80
    sta f:E816_PROBE0+1
    lda #1
    sta f:NI_PENDING+NI_SOURCE_PROBE
    sta f:CONTROL+5
    lda f:E816_VBI_COUNT
    sta f:CONTROL+6
    lda f:E816_VBI_COUNT+1
    sta f:CONTROL+7
raw_done:
    rtl

.a8
.i16
complete:
    rep #$20
    lda f:CONTROL+8
    inc a
    sta f:CONTROL+8
    tax
    sep #$20
    lda f:NI_BUDGET
    sta f:CONTROL+15,x
    cpx #BURST
    beq :+
    lda #1
    rtl
:
    lda f:CONTROL+4
    bne duplicate
    lda #1
    sta f:CONTROL+4
    rep #$30
    lda f:CONTROL+2
    and #$ff
    tax
    lda f:CONTROL
    jsl REPLY
    sep #$20
    lda #0
    sta f:NI_ENABLED+NI_SOURCE_PROBE
    rtl
duplicate:
    rep #$30
    lda #$ffec
    pha
    jsl FAULT

.ifdef RESUME_PROBE
; Test-only replacement of the private COP: interrupt the restored Task before
; it consumes its saved PC. No callback or policy activation may overtake it.
.export before_resume, resume_cop
.a16
.i16
before_resume:
    php
    rep #$30
    pha
    phx
    phy
    phd
    phb
    lda f:E816_VBI_DISPATCHES
    sta f:CONTROL+40
    lda f:E816_VBI_COUNT
    sta f:CONTROL+42
    sep #$20
    lda #$40
    sta f:$d40e
    rep #$20
resume_tick:
    lda f:E816_VBI_COUNT
    cmp f:CONTROL+42
    beq resume_tick
    sep #$20
    lda #0
    sta f:$d40e
    lda f:CONTROL+4
    bne duplicate
    rep #$20
    lda f:E816_VBI_DISPATCHES
    cmp f:CONTROL+40
    bne duplicate
    lda f:CONTROL+44
    inc a
    sta f:CONTROL+44
    plb
    pld
    ply
    plx
    pla
    plp
resume_cop:
    cop E816_COP
    jml FAULT
.endif
