; Export observation points without adding instructions.
.export console_capture, console_notify
; Native keyboard producer. Kernel admission owns the binding; the worker is
; the only consumer. Local I=1 sections defer scheduling across NMI (the saved
; interrupted I flag is checked by interrupt_schedule); NMI may still tick.
.include "console-layout.inc"
.include "console-storage.inc"
CI_ACTIVE = CS_CAPTURE+CON_CAPTURE_ACTIVE
CI_HEAD = CS_CAPTURE+CON_CAPTURE_HEAD
CI_TAIL = CS_CAPTURE+CON_CAPTURE_TAIL
CI_LOST = CS_CAPTURE+CON_CAPTURE_LOST
CI_MASK = CS_CAPTURE+CON_CAPTURE_SAVEDMASK
CI_SKCTL = CS_CAPTURE+CON_CAPTURE_SAVEDSKCTL
CI_VKEY = CS_CAPTURE+CON_CAPTURE_KEYVECTOR
CI_VBREAK = CS_CAPTURE+CON_CAPTURE_BREAKVECTOR
CI_NATIVE = CS_CAPTURE+CON_CAPTURE_NATIVEEVENTS
CI_EMU = CS_CAPTURE+CON_CAPTURE_EMULATIONEVENTS
CI_ERRORS = CS_CAPTURE+CON_CAPTURE_ERRORS
CI_HARDWARE_LOST = CS_CAPTURE+CON_CAPTURE_HARDWARELOST
CI_BINDING = CS_CAPTURE+CON_CAPTURE_BINDING
CI_ROUTE = CS_CAPTURE+CON_CAPTURE_ROUTE
CI_TAKEN_ROUTE = CS_CAPTURE+CON_CAPTURE_TAKENROUTE
CI_BREAK_ROUTE = CS_CAPTURE+CON_CAPTURE_BREAKROUTE
CI_BREAK_PENDING = CS_CAPTURE+CON_CAPTURE_BREAKPENDING
CI_BREAK_MASK = CS_CAPTURE+CON_CAPTURE_BREAKMASK
CI_LOST_MASK = CS_CAPTURE+CON_CAPTURE_LOSTMASK
CI_ROUTES = CS_ROUTES+CON_ROUTES_ITEMS
CI_EVENTS = CS_CAPTURE+CON_CAPTURE_EVENTS
.segment "SIGNAL_CODE"
.export console_claim,console_claim_end,console_release,console_release_end
.export console_take,console_take_end,console_reset_input,console_reset_input_end
.export console_clear_unit,console_clear_unit_end
.export console_route,console_capture_phase,console_before_reset
.export console_publish,console_publish_end,console_take_break,console_take_break_end
.a16
.i16
; The Task caller holds Forbid and has fully initialized the route. I=1
; covers both halves; NMI can tick but cannot switch the interrupted Task.
console_publish:
    signal_stack_check 1
    php
    sei
    lda 5,s
    sta f:CI_ROUTE
    lda 7,s
    sta f:CI_ROUTE+2
    plp
    rtl
console_publish_end:

; Per-route bitmaps retain BREAK/loss independently, including a full ring.
; Only task context resolves the fixed route table; the IRQ posts scalar bits.
console_take_break:
    signal_stack_check 1
    php
    sei
    lda f:CI_BREAK_MASK
    beq console_take_break_empty
    ldx #0
:
    lsr a
    bcs :+
    inx
    inx
    bra :-
:
    lda f:console_route_bits,x
    eor #$ffff
    and f:CI_BREAK_MASK
    sta f:CI_BREAK_MASK
    bne :+
    sep #$20
    lda #0
    sta f:CI_BREAK_PENDING
    rep #$20
:
    txa
    asl
    asl
    asl
    tax
    lda f:CI_ROUTES+CON_ROUTE_TAG+2,x
    tay
    lda f:CI_ROUTES+CON_ROUTE_TAG,x
    tyx
    plp
    rtl
console_take_break_empty:
    lda #0
    tax
    plp
    rtl
console_take_break_end:

; Retire only this unit's captured input. Callers exclude task switching;
; IRQ stays enabled during the bounded table/ring walks. Clear loss BEFORE
; snapshotting head so a later overrun cannot be accidentally acknowledged.
; Bound BREAK mailboxes survive input clear/open/close.
console_clear_unit:
    signal_stack_check 5
    php
    ldx #0
    ldy #1
console_clear_loss:
    lda f:CI_ROUTES+CON_ROUTE_UNIT,x
    cmp 5,s
    bne console_clear_next_route
    lda f:CI_ROUTES+CON_ROUTE_UNIT+2,x
    cmp 7,s
    bne console_clear_next_route
    php
    sei
    tya
    eor #$ffff
    and f:CI_LOST_MASK
    sta f:CI_LOST_MASK
    bne :+
    sep #$20
    lda #0
    sta f:CI_LOST
    rep #$20
:
    plp
console_clear_next_route:
    txa
    clc
    adc #CON_ROUTE_SIZE
    tax
    tya
    asl
    tay
    bne console_clear_loss
    lda f:CI_HEAD
    and #$ff
    pha
    lda f:CI_TAIL
    and #$ff
    tay
console_clear_event:
    tya
    cmp 1,s
    beq console_clear_done
    and #63
    asl
    asl
    asl
    tax
    phx
    lda f:CI_EVENTS+4,x
    and #15
    asl
    asl
    asl
    asl
    tax
    lda f:CI_ROUTES+CON_ROUTE_UNIT,x
    cmp 9,s
    bne console_clear_keep
    lda f:CI_ROUTES+CON_ROUTE_UNIT+2,x
    cmp 11,s
    bne console_clear_keep
    plx
    sep #$20
    lda #$ff
    sta f:CI_EVENTS+1,x
    rep #$20
    bra console_clear_advance
console_clear_keep:
    plx
console_clear_advance:
    tya
    inc a
    and #$ff
    tay
    bra console_clear_event
console_clear_done:
    pla
    plp
    rtl
console_clear_unit_end:

console_claim:
    signal_stack_check 3
    php
    sei
    sep #$20
    lda f:CI_ACTIVE
    ora f:OS_BUSY
    beq :+
    rep #$20
    lda #0
    plp
    rtl
:
    .a8                    ; success branch retains M=1
    lda f:$0010
    and #$c0
    sta f:CI_MASK
    lda f:$0010
    and #$3f
    sta f:$d20e             ; retire pre-claim keyboard/BREAK requests
    lda f:SD_OWNED
    beq :+
    lda f:SD_OLD_SKCTL      ; restore the common baseline, not a serial phase
    bra console_claim_saved
:
    lda f:$0232
console_claim_saved:
    sta f:CI_SKCTL
    rep #$20
    lda #0
    sta f:CI_HEAD
    sta f:CI_NATIVE
    sta f:CI_EMU
    sta f:CI_ERRORS
    sta f:CI_BREAK_MASK
    sta f:CI_LOST_MASK
    sep #$20
    sta f:CI_BREAK_PENDING
    sta f:CI_LOST
    rep #$20
    lda f:$0208
    sta f:CI_VKEY
    lda f:$0236
    sta f:CI_VBREAK
    lda #console_emu_key
    sta f:$0208
    lda #console_emu_break
    sta f:$0236
    sep #$20
    lda f:$0232
    ora #3
    sta f:$0232
    sta f:$d20f
    lda #1
    sta f:CI_ACTIVE
    sta f:CI_BINDING+CON_BINDING_ACTIVE
    lda f:$0010
    ora #$c0
    sta f:$0010
    sta f:$d20e
    rep #$20
    lda #1
    plp
    rtl
console_claim_end:

console_release:
    signal_stack_check 3
console_release_unchecked:
    php
    sei
    sep #$20
    lda f:CI_ACTIVE
    beq console_release_done
    lda f:$0010
    and #$3f
    sta f:$0010
    sta f:$d20e
    lda #0
    sta f:CI_ACTIVE
    sta f:CI_BINDING+CON_BINDING_ACTIVE
    sta f:CI_LOST
    sta f:CI_BREAK_PENDING
    lda f:CI_HEAD
    sta f:CI_TAIL
    rep #$20
    lda #0
    sta f:CI_BREAK_MASK
    sta f:CI_LOST_MASK
    lda f:CI_VKEY
    sta f:$0208
    lda f:CI_VBREAK
    sta f:$0236
    sep #$20
    lda f:SD_OWNED
    beq :+
    lda f:CI_SKCTL
    sta f:SD_OLD_SKCTL      ; last remaining owner restores the shared baseline
    bra console_release_mask
:
    lda f:CI_SKCTL
    sta f:$0232
    sta f:$d20f
console_release_mask:
    lda f:$0010
    ora f:CI_MASK
    sta f:$0010
    sta f:$d20e
console_release_done:
    rep #$20
    plp
    rtl
console_release_end:

console_reset_input:
    signal_stack_check 1
    php
    sei
    sep #$20
    lda #0
    sta f:CI_LOST
    lda f:CI_HEAD
    sta f:CI_TAIL
    rep #$20
    lda #0
    sta f:CI_LOST_MASK
    plp
    rtl
console_reset_input_end:

; Return key/kind in A, coherent captured tick in X. Loss identifies one
; captured route and leaves the other routes' ring events available.
console_take:
    signal_stack_check 5
    php
    sei
    lda f:CI_LOST_MASK
    beq console_take_ring
    ldx #0
:
    lsr a
    bcs :+
    inx
    inx
    bra :-
:
    lda f:console_route_bits,x
    eor #$ffff
    and f:CI_LOST_MASK
    sta f:CI_LOST_MASK
    bne :+
    sep #$20
    lda #0
    sta f:CI_LOST
    rep #$20
:
    txa
    asl
    asl
    asl
    tax
    lda f:CI_ROUTES+CON_ROUTE_TAG,x
    sta f:CI_TAKEN_ROUTE
    lda f:CI_ROUTES+CON_ROUTE_TAG+2,x
    sta f:CI_TAKEN_ROUTE+2
    lda #$fffe
    bra console_take_sentinel
console_take_ring:
    sep #$20
    lda f:CI_TAIL
    cmp f:CI_HEAD
    bne :+
    rep #$20
    lda #$ffff
console_take_sentinel:
    ldx #$ffff
    plp
    rtl
:
    rep #$20
    and #63
    asl
    asl
    asl
    tax
    lda f:CI_EVENTS+4,x
    sta f:CI_TAKEN_ROUTE
    lda f:CI_EVENTS+6,x
    sta f:CI_TAKEN_ROUTE+2
    lda f:CI_EVENTS,x
    pha
    lda f:CI_EVENTS+2,x
    tay
    sep #$20
    lda f:CI_TAIL
    inc a
    sta f:CI_TAIL          ; release only after both words have been copied
    rep #$20
    pla
    tyx
    plp
    rtl
console_take_end:

.a8
console_route:
    lda f:CI_ACTIVE
    beq console_unowned
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
    jsr console_capture
    rep #$20
    lda f:CI_NATIVE
    inc a
    sta f:CI_NATIVE
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
    jsr console_capture
    rep #$20
    lda f:CI_NATIVE
    inc a
    sta f:CI_NATIVE
    sep #$20
:
    lda f:$d20e
    eor #$ff
    and f:$0010
    bne console_unowned
    sec
    rtl
console_unowned:
    clc
    rtl

console_capture:
    pha
    jsr console_errors
    lda 1,s
    cmp #1
    beq console_capture_break
    lda f:$d209
    and #$bf               ; Ctrl-C, with either Shift state (key-map slot 18)
    cmp #$92
    bne console_capture_ring
console_capture_break:
    rep #$20
    lda f:CI_ROUTE
    ora f:CI_ROUTE+2
    beq console_capture_unbound
    lda f:CI_ROUTE
    sta f:CI_BREAK_ROUTE
    lda f:CI_ROUTE+2
    sta f:CI_BREAK_ROUTE+2
    lda f:CI_ROUTE
    and #15
    asl
    tax
    lda f:console_route_bits,x
    ora f:CI_BREAK_MASK
    sta f:CI_BREAK_MASK
    sep #$20
    lda #1
    sta f:CI_BREAK_PENDING
    bra console_capture_ring
console_capture_unbound:
    sep #$20
console_capture_ring:
    lda f:SD_PHASE
console_capture_phase:
    lda f:CI_HEAD
    sec
    sbc f:CI_TAIL
    cmp #64
    bcs console_overflow
    lda f:CI_HEAD
    rep #$20
    and #63
    asl
    asl
    asl
    tax
    lda f:CI_ROUTE
    sta f:CI_EVENTS+4,x
    lda f:CI_ROUTE+2
    sta f:CI_EVENTS+6,x
    lda f:E816_VBI_COUNT
    sta f:CI_EVENTS+2,x
    sep #$20
    lda f:$d209
    sta f:CI_EVENTS,x
    pla
    sta f:CI_EVENTS+1,x
    lda f:CI_HEAD
    inc a
    sta f:CI_HEAD          ; publish the complete event before notification
console_notify:
    jsr sio_console_service
    ldx #CI_BINDING-T_BASE
    jmp signal_post_binding
console_overflow:
    pla
    jsr console_mark_loss
    bra console_notify

console_mark_loss:
    rep #$20
    lda f:CI_ROUTE
    ora f:CI_ROUTE+2
    beq console_loss_unbound
    lda f:CI_ROUTE
    and #15
    asl
    tax
    lda f:console_route_bits,x
    ora f:CI_LOST_MASK
    sta f:CI_LOST_MASK
    sep #$20
    lda #1
    sta f:CI_LOST
    rts
console_loss_unbound:
    sep #$20
    rts


; SIO calls this before SKREST, while its serial frame is not active. Keep
; error evidence and permit the next distinct hardware overrun to be reported.
console_before_reset:
    jsr console_errors
    lda #0
    sta f:CI_HARDWARE_LOST
    rts
console_errors:
    lda f:CI_ACTIVE
    beq console_errors_done
    lda f:$d20f
    eor #$ff
    and #$e0
    pha
    ora f:CI_ERRORS
    sta f:CI_ERRORS
    pla
    and #$40
    beq console_errors_rearmed
    lda f:CI_HARDWARE_LOST
    bne console_errors_reset
    lda #1
    sta f:CI_HARDWARE_LOST
    jsr console_mark_loss
console_errors_reset:
    ; Reset only without a live serial frame. Idle/terminal owners also need
    ; keyboard recovery even if no later transaction calls SKREST.
    lda f:SD_OWNED
    beq console_errors_clear
    lda f:SD_PHASE
    beq console_errors_clear
    cmp #SIO_TERMINAL
    beq console_errors_clear
    cmp #15
    bne console_errors_done
console_errors_clear:
    sta f:$d20a
console_errors_rearmed:
    lda #0
    sta f:CI_HARDWARE_LOST
console_errors_done:
    rts

console_emu_post:
    jsr console_capture
    rep #$20
    lda f:CI_EMU
    inc a
    sta f:CI_EMU
    sep #$20
    rtl

.segment "STUBS"
.a8
.i8
console_emu_key:
    lda #0
    bra console_emu_entry
console_emu_break:
    lda #1
console_emu_entry:
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
    jsl console_emu_post
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

; Terminal safe-bus cleanup, after finish has selected the kernel stack/domain
; and disabled IRQ/NMI. Never reached on the reset-required $FF93 path.
; Normal worker shutdown uses preemptible Action copies instead.
.segment "SIGNAL_CODE"
.export console_shutdown
.a16
.i16
console_shutdown:
    jsl console_release_unchecked
    sep #$20
    lda f:CS_PRESENTATION+CON_PRESENTATION_CLAIMED
    bne :+
    rep #$20
    rtl
:
    rep #$30
    phd
    tsc
    sec
    sbc #6
    tcs
    tcd
    lda f:CS_PRESENTATION+CON_PRESENTATION_SCREEN
    sta 1
    lda f:CS_PRESENTATION+CON_PRESENTATION_SNAPSHOT
    sta 4
    sep #$20
    lda f:CS_PRESENTATION+CON_PRESENTATION_SCREEN+2
    sta 3
    lda f:CS_PRESENTATION+CON_PRESENTATION_SNAPSHOT+2
    sta 6
    ldy #0
:
    lda [4],y
    sta [1],y
    iny
    cpy #960
    bcc :-
    lda f:CS_PRESENTATION+CON_PRESENTATION_SAVEDCURSOR
    sta f:$02f0
    lda f:CS_PRESENTATION+CON_PRESENTATION_SAVEDATTRACT
    sta f:$004d
    lda #0
    sta f:CS_PRESENTATION+CON_PRESENTATION_CLAIMED
    sta f:CS_PRESENTATION+CON_PRESENTATION_VISIBLE
    sta f:CS_BASE+CON_SERVICE_STATE
    rep #$30
    tsc
    clc
    adc #6
    tcs
    pld
    rtl

; Sixteen immutable route-slot masks, indexed without pointer lookup in IRQ.
console_route_bits:
    .word $0001,$0002,$0004,$0008,$0010,$0020,$0040,$0080
    .word $0100,$0200,$0400,$0800,$1000,$2000,$4000,$8000

; Translate an admitted span without changing D, DBR, S or interrupt masking.
; All temporaries belong to the calling domain. No stack frame or patched code.
.segment "SIGNAL_CODE"
.export console_span,console_span_end,console_span_store
.a16
.i16
console_span:
    lda 4,s
    sta A816_DP_SCRATCH_OFFSET
    lda 5,s
    sta A816_DP_SCRATCH_OFFSET+1
    lda 7,s
    sta A816_DP_SCRATCH_OFFSET+3
    lda 8,s
    sta A816_DP_SCRATCH_OFFSET+4
    lda 10,s
    sta A816_DP_SCRATCH_OFFSET+6
    beq console_span_done
    ldy #0
console_span_next:
    sep #$20
    lda [A816_DP_SCRATCH_OFFSET+3],y
    cmp #128
    bcs console_span_unknown
    rep #$20
    and #$ff
    tax
    sep #$20
    lda f:CS_GLYPHS,x
    bra console_span_store
console_span_unknown:
    lda #31
console_span_store:
    sta [A816_DP_SCRATCH_OFFSET],y
    iny
    rep #$20
    cpy A816_DP_SCRATCH_OFFSET+6
    bne console_span_next
console_span_done:
    rtl
console_span_end:
