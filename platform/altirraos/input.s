; Export observation points without adding instructions.
.export input_capture, input_notify
; Native keyboard producer. Kernel admission owns the binding; the worker is
; the only consumer. Local I=1 sections defer scheduling across NMI (the saved
; interrupted I flag is checked by interrupt_schedule); NMI may still tick.
.include "input-native.inc"
.include "input.inc"
.include "input-storage.inc"
CI_ACTIVE = IN_CAPTURE+IN_CAPTURE_ACTIVE
CI_HEAD = IN_CAPTURE+IN_CAPTURE_HEAD
CI_TAIL = IN_CAPTURE+IN_CAPTURE_TAIL
CI_LOST = IN_CAPTURE+IN_CAPTURE_LOST
CI_MASK = IN_CAPTURE+IN_CAPTURE_SAVEDMASK
CI_SKCTL = IN_CAPTURE+IN_CAPTURE_SAVEDSKCTL
CI_VKEY = IN_CAPTURE+IN_CAPTURE_KEYVECTOR
CI_VBREAK = IN_CAPTURE+IN_CAPTURE_BREAKVECTOR
CI_NATIVE = IN_CAPTURE+IN_CAPTURE_NATIVEEVENTS
CI_EMU = IN_CAPTURE+IN_CAPTURE_EMULATIONEVENTS
CI_ERRORS = IN_CAPTURE+IN_CAPTURE_ERRORS
CI_HARDWARE_LOST = IN_CAPTURE+IN_CAPTURE_HARDWARELOST
CI_BINDING = IN_CAPTURE+IN_CAPTURE_BINDING
CI_ROUTE = IN_CAPTURE+IN_CAPTURE_ROUTE
CI_TAKEN_ROUTE = IN_CAPTURE+IN_CAPTURE_TAKENROUTE
CI_BREAK_ROUTE = IN_CAPTURE+IN_CAPTURE_BREAKROUTE
CI_BREAK_PENDING = IN_CAPTURE+IN_CAPTURE_BREAKPENDING
CI_BREAK_MASK = IN_CAPTURE+IN_CAPTURE_BREAKMASK
CI_LOST_MASK = IN_CAPTURE+IN_CAPTURE_LOSTMASK
CI_ROUTES = IN_STATE+IN_STATE_TAGS
CI_CONFIG = IN_STATE+IN_STATE_CONFIG
IN_ROUTE_TAG = 0
CI_EVENTS = IN_CAPTURE+IN_CAPTURE_EVENTS
.segment "SIGNAL_CODE"
.export input_claim,input_claim_end,input_release,input_release_end
.export input_take,input_take_end,input_reset_input,input_reset_input_end
.export input_discard,input_discard_end
.export input_route,input_capture_phase,input_before_reset
.export input_publish,input_publish_end,input_take_break,input_take_break_end
.a16
.i16
; The Task caller holds Forbid and has fully initialized the route. I=1
; covers both halves; NMI can tick but cannot switch the interrupted Task.
input_publish:
    signal_stack_check 1
    php
    sei
    lda 5,s
    sta f:CI_ROUTE
    lda 7,s
    sta f:CI_ROUTE+2
    plp
    rtl
input_publish_end:

; Per-route bitmaps retain BREAK/loss independently, including a full ring.
; Only task context resolves the fixed route table; the IRQ posts scalar bits.
input_take_break:
    signal_stack_check 1
    php
    sei
    lda f:CI_BREAK_MASK
    beq input_take_break_empty
    ldx #0
:
    lsr a
    bcs :+
    inx
    inx
    bra :-
:
    lda f:input_route_bits,x
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
    tax
    lda f:CI_ROUTES+2,x
    sta f:CI_TAKEN_ROUTE+2
    lda f:CI_ROUTES,x
    sta f:CI_TAKEN_ROUTE
    txa
    lsr
    lsr
    tax
    lda f:IN_STATE+IN_STATE_CANCELCODE,x
    and #$ff
    ldx #0
    plp
    rtl
input_take_break_empty:
    lda #0
    tax
    plp
    rtl
input_take_break_end:

; Retire only this unit's captured input. Callers exclude task switching;
; IRQ stays enabled during the bounded table/ring walks. Clear loss BEFORE
; snapshotting head so a later overrun cannot be accidentally acknowledged.
; Bound BREAK mailboxes survive input clear/open/close.
input_discard:
    signal_stack_check 5
    php
    sei
    lda 5,s
    and #15
    asl
    tax
    lda f:input_route_bits,x
    eor #$ffff
    and f:CI_LOST_MASK
    sta f:CI_LOST_MASK
    bne :+
    sep #$20
    lda #0
    sta f:CI_LOST
    rep #$20
:
    lda f:CI_HEAD
    and #$ff
    pha
    lda f:CI_TAIL
    and #$ff
    tay
    ; Restore caller I while walking the immutable snapshot; new arrivals
    ; cannot overwrite unconsumed slots, and survive this clear boundary.
    lda 3,s
    and #4
    bne input_discard_loop
    cli
input_discard_loop:
    tya
    cmp 1,s
    beq input_discard_done
    and #63
    asl
    asl
    asl
    tax
    lda f:CI_EVENTS+4,x
    cmp 7,s
    bne input_discard_next
    lda f:CI_EVENTS+6,x
    cmp 9,s
    bne input_discard_next
    sep #$20
    lda #$ff
    sta f:CI_EVENTS+1,x
    rep #$20
input_discard_next:
    iny
    tya
    and #$ff
    tay
    bra input_discard_loop
input_discard_done:
    pla
    plp
    rtl
input_discard_end:

input_claim:
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
    bra input_claim_saved
:
    lda f:$0232
input_claim_saved:
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
    lda #input_emu_key
    sta f:$0208
    lda #input_emu_break
    sta f:$0236
    sep #$20
    lda f:$0232
    ora #3
    sta f:$0232
    sta f:$d20f
    lda #1
    sta f:CI_ACTIVE
    sta f:CI_BINDING+IN_BINDING_ACTIVE
    lda f:$0010
    ora #$c0
    sta f:$0010
    sta f:$d20e
    rep #$20
    lda #1
    plp
    rtl
input_claim_end:

input_release:
    signal_stack_check 3
input_release_unchecked:
    php
    sei
    sep #$20
    lda f:CI_ACTIVE
    beq input_release_done
    lda f:$0010
    and #$3f
    sta f:$0010
    sta f:$d20e
    lda #0
    sta f:CI_ACTIVE
    sta f:CI_BINDING+IN_BINDING_ACTIVE
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
    bra input_release_mask
:
    lda f:CI_SKCTL
    sta f:$0232
    sta f:$d20f
input_release_mask:
    lda f:$0010
    ora f:CI_MASK
    sta f:$0010
    sta f:$d20e
input_release_done:
    rep #$20
    plp
    rtl
input_release_end:

input_reset_input:
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
input_reset_input_end:

; Return key/kind in A, coherent captured tick in X. Loss identifies one
; captured route and leaves the other routes' ring events available.
input_take:
    signal_stack_check 5
    php
    sei
    lda f:CI_LOST_MASK
    beq input_take_ring
    ldx #0
:
    lsr a
    bcs :+
    inx
    inx
    bra :-
:
    lda f:input_route_bits,x
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
    tax
    lda f:CI_ROUTES+IN_ROUTE_TAG,x
    sta f:CI_TAKEN_ROUTE
    lda f:CI_ROUTES+IN_ROUTE_TAG+2,x
    sta f:CI_TAKEN_ROUTE+2
    txa
    lsr
    lsr
    tax
    sep #$20
    lda f:IN_STATE+IN_STATE_LOSSCODE,x
    sta f:IN_CAPTURE+IN_CAPTURE_PADDING
    rep #$20
    lda #$fffe
    bra input_take_sentinel
input_take_ring:
    sep #$20
    lda f:CI_TAIL
    cmp f:CI_HEAD
    bne :+
    rep #$20
    lda #$ffff
input_take_sentinel:
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
input_take_end:

.a8
input_route:
    lda f:CI_ACTIVE
    beq input_unowned
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
    jsr input_capture
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
    jsr input_capture
    rep #$20
    lda f:CI_NATIVE
    inc a
    sta f:CI_NATIVE
    sep #$20
:
    lda f:$d20e
    eor #$ff
    and f:$0010
    ; A keyboard/BREAK edge arriving after its capture check is still owned.
    ; Leave it latched for the next native entry rather than forwarding it.
    and #$3f
    bne input_unowned
    sec
    rtl
input_unowned:
    clc
    rtl

input_capture:
    pha
    jsr input_errors
    rep #$20
    lda f:CI_ROUTE
    ora f:CI_ROUTE+2
    bne :+
    sep #$20
    pla
    rts
:
    sep #$20
    lda 1,s
    cmp #1
    bne input_capture_filters
    lda f:CI_CONFIG+INPUT_CONFIG_FLAGS
    and #INPUT_CAPTURE_BREAK
    beq input_capture_ignore
    lda #INPUT_CANCEL_BREAK
    bra input_capture_cancel
input_capture_filters:
    lda f:CI_CONFIG+INPUT_CONFIG_FILTERCOUNT
    beq input_capture_ring
    lda f:$d209
    and f:CI_CONFIG+INPUT_CONFIG_FILTER0MASK
    cmp f:CI_CONFIG+INPUT_CONFIG_FILTER0VALUE
    beq input_capture_filter
    lda f:CI_CONFIG+INPUT_CONFIG_FILTERCOUNT
    cmp #2
    bne input_capture_ring
    lda f:$d209
    and f:CI_CONFIG+INPUT_CONFIG_FILTER1MASK
    cmp f:CI_CONFIG+INPUT_CONFIG_FILTER1VALUE
    bne input_capture_ring
input_capture_filter:
    lda #INPUT_CANCEL_KEY_FILTER
input_capture_cancel:
    pha
    rep #$20
    lda f:CI_ROUTE
    and #15
    tax
    sep #$20
    pla
    sta f:IN_STATE+IN_STATE_CANCELCODE,x
    rep #$20
    txa
    asl
    tax
    lda f:input_route_bits,x
    ora f:CI_BREAK_MASK
    sta f:CI_BREAK_MASK
    sep #$20
    lda #1
    sta f:CI_BREAK_PENDING
    pla
    jmp input_notify
input_capture_ignore:
    pla
    rts
input_capture_ring:
    lda f:SD_PHASE
input_capture_phase:
    lda f:CI_HEAD
    sec
    sbc f:CI_TAIL
    cmp #64
    bcs input_overflow
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
input_notify:
    jsr sio_console_service
    ldx #CI_BINDING-T_BASE
    jmp signal_post_binding
input_overflow:
    pla
    lda #INPUT_LOSS_RAW
    jsr input_mark_loss
    bra input_notify

input_mark_loss:
    pha
    rep #$20
    lda f:CI_ROUTE
    ora f:CI_ROUTE+2
    beq input_loss_unbound
    lda f:CI_ROUTE
    and #15
    tax
    sep #$20
    pla
    sta f:IN_STATE+IN_STATE_LOSSCODE,x
    rep #$20
    txa
    asl
    tax
    lda f:input_route_bits,x
    ora f:CI_LOST_MASK
    sta f:CI_LOST_MASK
    sep #$20
    lda #1
    sta f:CI_LOST
    rts
input_loss_unbound:
    sep #$20
    pla
    rts


; SIO calls this before SKREST, while its serial frame is not active. Keep
; error evidence and permit the next distinct hardware overrun to be reported.
input_before_reset:
    jsr input_errors
    lda #0
    sta f:CI_HARDWARE_LOST
    rts
input_errors:
    lda f:CI_ACTIVE
    beq input_errors_done
    lda f:$d20f
    eor #$ff
    and #$e0
    pha
    ora f:CI_ERRORS
    sta f:CI_ERRORS
    pla
    and #$40
    beq input_errors_rearmed
    lda f:CI_HARDWARE_LOST
    bne input_errors_reset
    lda #1
    sta f:CI_HARDWARE_LOST
    lda #INPUT_LOSS_HARDWARE
    jsr input_mark_loss
input_errors_reset:
    ; Reset only without a live serial frame. Idle/terminal owners also need
    ; keyboard recovery even if no later transaction calls SKREST.
    lda f:SD_OWNED
    beq input_errors_clear
    lda f:SD_PHASE
    beq input_errors_clear
    cmp #SIO_TERMINAL
    beq input_errors_clear
    cmp #15
    bne input_errors_done
input_errors_clear:
    sta f:$d20a
input_errors_rearmed:
    lda #0
    sta f:CI_HARDWARE_LOST
input_errors_done:
    rts

input_emu_post:
    jsr input_capture
    rep #$20
    lda f:CI_EMU
    inc a
    sta f:CI_EMU
    sep #$20
    rtl

.segment "STUBS"
.a8
.i8
input_emu_key:
    lda #0
    bra input_emu_entry
input_emu_break:
    lda #1
input_emu_entry:
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
    jsl input_emu_post
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

; Sixteen immutable route-slot masks, indexed without pointer lookup in IRQ.
input_route_bits:
    .word $0001,$0002,$0004,$0008,$0010,$0020,$0040,$0080
    .word $0100,$0200,$0400,$0800,$1000,$2000,$4000,$8000

