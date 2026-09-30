; Slice-1 fixture only. The upper Task arena already reserves this range;
; max DOS descriptors end at $A60, native code starts at $1000.
CP_BASE = T_BASE+$c00
CP_ACTIVE = CP_BASE
CP_HEAD = CP_BASE+1
CP_TAIL = CP_BASE+2
CP_LOST = CP_BASE+3
CP_MASK = CP_BASE+4
CP_SKCTL = CP_BASE+5
CP_VKEY = CP_BASE+6
CP_VBREAK = CP_BASE+8
CP_NATIVE = CP_BASE+10
CP_EMU = CP_BASE+12
CP_ERRORS = CP_BASE+14
CP_BINDING = CP_BASE+16
CP_EVENTS = CP_BASE+32
.segment "SIGNAL_CODE"
.export console_probe_claim,console_probe_claim_end
.export console_probe_release,console_probe_release_end
.export console_probe_take,console_probe_take_end,console_probe_route
.export console_probe_phase
.a16
.i16
console_probe_claim:
    signal_stack_check 5
    php
    sei
    lda #0
    sta f:CP_ACTIVE
    sta f:CP_TAIL
    sta f:CP_NATIVE
    sta f:CP_EMU
    sta f:CP_ERRORS
    lda f:$0208
    sta f:CP_VKEY
    lda f:$0236
    sta f:CP_VBREAK
    lda #console_probe_emu_key
    sta f:$0208
    lda #console_probe_emu_break
    sta f:$0236
    lda #.loword(T_ROOT)
    sta f:CP_BINDING+T_BINDING_TASK
    lda #.loword(T_BASE)
    sta f:CP_BINDING+T_BINDING_CONTEXT
    lda #0
    sta f:CP_BINDING+T_BINDING_MASK
    lda #1
    sta f:CP_BINDING+T_BINDING_MASK+2
    sep #$20
    lda #^T_ROOT
    sta f:CP_BINDING+T_BINDING_TASK+2
    lda #^T_BASE
    sta f:CP_BINDING+T_BINDING_CONTEXT+2
    lda f:$0010
    and #$c0
    sta f:CP_MASK
    lda f:$0232
    sta f:CP_SKCTL
    ora #3
    sta f:$0232
    sta f:$d20f
    lda f:$0010
    ora #$c0
    sta f:$0010
    sta f:$d20e
    lda #1
    sta f:CP_ACTIVE
    rep #$20
    plp
    rtl
console_probe_claim_end:
console_probe_release:
    signal_stack_check 5
    php
    sei
    sep #$20
    lda f:$0010
    and #$3f
    sta f:$0010
    sta f:$d20e
    lda #0
    sta f:CP_ACTIVE
    rep #$20
    lda f:CP_VKEY
    sta f:$0208
    lda f:CP_VBREAK
    sta f:$0236
    sep #$20
    lda f:$0010
    ora f:CP_MASK
    sta f:$0010
    sta f:$d20e
    ; The SIO owner controls SKCTL until its own shutdown.
    lda f:SD_OWNED
    bne :+
    lda f:CP_SKCTL
    sta f:$0232
    sta f:$d20f
:
    rep #$20
    plp
    rtl
console_probe_release_end:
console_probe_take:
    signal_stack_check 5
    php
    sei
    lda f:CP_TAIL
    and #$ff
    tax
    sep #$20
    cmp f:CP_HEAD
    beq console_probe_empty
    rep #$20
    txa
    asl
    asl
    tax
    lda f:CP_EVENTS,x
    pha
    sep #$20
    lda f:CP_TAIL
    inc a
    and #63
    sta f:CP_TAIL
    rep #$20
    pla
    plp
    rtl
console_probe_empty:
    rep #$20
    lda #$ffff
    plp
    rtl
console_probe_take_end:

.a8
console_probe_route:
    lda f:CP_ACTIVE
    beq console_probe_unowned
    lda f:$d20e
    eor #$ff
    and f:$0010
    and #$40
    beq :+
    lda f:$0010
    and #$bf
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    lda #0
    jsr console_probe_capture
    rep #$20
    lda f:CP_NATIVE
    inc a
    sta f:CP_NATIVE
    sep #$20
:
    lda f:$d20e
    eor #$ff
    and f:$0010
    and #$80
    beq :+
    lda f:$0010
    and #$7f
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    lda #1
    jsr console_probe_capture
    rep #$20
    lda f:CP_NATIVE
    inc a
    sta f:CP_NATIVE
    sep #$20
:
    lda f:$d20e
    eor #$ff
    and f:$0010
    bne console_probe_unowned
    sec
    rtl
console_probe_unowned:
    clc
    rtl

; A=kind, saved native registers and an IRQ activation already exist.
console_probe_capture:
    pha
    jsr console_probe_errors
    lda f:SD_PHASE
console_probe_phase:                 ; observer reads A, no guest trace buffer
    lda f:CP_HEAD
    inc a
    and #63
    cmp f:CP_TAIL
    beq console_probe_overflow
    pha
    lda f:CP_HEAD
    rep #$20
    and #$ff
    asl
    asl
    tax
    lda f:E816_VBI_COUNT
    sta f:CP_EVENTS+2,x
    sep #$20
    lda f:$d209
    sta f:CP_EVENTS,x
    pla
    tay
    pla
    sta f:CP_EVENTS+1,x
    tya
    sta f:CP_HEAD
console_probe_notify:
    ldx #CP_BINDING-T_BASE
    jmp signal_post_binding
console_probe_overflow:
    pla
    lda #1
    sta f:CP_LOST
    bra console_probe_notify

; Preserve both serial and keyboard error evidence before a shared SKREST.
; The fixture reports keyboard overrun as input loss; SIO keeps its own error
; policy. No console-side write clears the serial latches during a transfer.
console_probe_errors:
    lda f:CP_ACTIVE
    beq :+
    lda f:$d20f
    eor #$ff
    and #$e0
    ora f:CP_ERRORS
    sta f:CP_ERRORS
    and #$40
    beq :+
    lda #1
    sta f:CP_LOST
:
    rts

console_probe_emu_post:
    jsr console_probe_capture
    rep #$20
    lda f:CP_EMU
    inc a
    sta f:CP_EMU
    sep #$20
    rtl

; ROM acknowledged the source and saved A. Native helpers preserve hidden
; halves, X/Y, D/DBR and the live OS stack; no scheduling in this callback.
.segment "STUBS"
.a8
.i8
console_probe_emu_key:
    lda #0
    bra console_probe_emu_entry
console_probe_emu_break:
    lda #1
console_probe_emu_entry:
    php
    clc
    xce
    rep #$30
    pha
    phx
    phy
    phd
    phb
    sep #$20
    jsl console_probe_emu_post
    rep #$30
    plb
    pld
    ply
    plx
    pla
    sep #$30
    sec
    xce
    plp
    pla
    rti
.segment "SIGNAL_CODE"
.a16
.i16
