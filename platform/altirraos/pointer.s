; ST quadrature capture. IRQ owns phase/counters/head; Tasks own tail and
; normalization. Every native transaction saves I and masks IRQ. A nested NMI
; preserves interrupted I and cannot schedule across IRQ_DEPTH/Forbid. No PIA,
; paddle, trigger-latch or SKCTL writes are made by this backend.
PI = IN_POINTER_CAPTURE
PI_CONFIG = IN_POINTER_STATE+IN_STATE_CONFIG
PI_BINDING = PI+IN_POINTERCAPTURE_BINDING
PI_ROUTE = PI+IN_POINTERCAPTURE_ROUTE
PI_EVENTS = PI+IN_POINTERCAPTURE_EVENTS
PI_NOTICES = PI+IN_POINTERCAPTURE_NOTICES
; Fixed scratch is used only with I=1, including Task entry points.
PI_NEW_PHASE = PI+4
PI_NEW_BUTTONS = PI+5
PI_DX = PI+6
PI_DY = PI+7
PI_KIND = PI+8
PI_FLAGS = PI+9
PI_SLOT = PI+10
PI_LOSS_TAG = PI+36
PI_LOSS_CODE = PI+40
PI_AGE = PI+IN_POINTERCAPTURE_MOTIONAGE
PI_BEAM = PI+IN_POINTERCAPTURE_MOTIONBEAM
PI_LAST_X = PI+IN_POINTERCAPTURE_MOTIONX
PI_LAST_Y = PI+IN_POINTERCAPTURE_MOTIONY
PI_CLASS = PI+IN_POINTERCAPTURE_MOTIONCLASS
PI_VECTOR = PI+IN_POINTERCAPTURE_MOTIONVECTOR
PI_STEPS = PI+IN_POINTERCAPTURE_MOTIONSTEPS
PI_CLOCK_SCRATCH = PI+IN_POINTERCAPTURE_MOTIONSCRATCH
; Use spare native-work code in the same upper bank. Near calls and interrupt
; entry costs stay unchanged; SIGNAL_CODE has no room for timed capture.
.segment "NATIVE_WORK"
.export pointer_claim,pointer_claim_end,pointer_release,pointer_release_end
.export pointer_publish,pointer_publish_end,pointer_discard,pointer_discard_end
.export pointer_take,pointer_take_end,pointer_sample,pointer_notify,pointer_port_read
.a16
.i16
pointer_claim:
    signal_stack_check 40
    php
    sei
    sep #$20
    lda f:PI
    ora f:OS_BUSY
    beq :+
    jmp pointer_claim_busy
:
    lda #2
    jsr timer_acquire
    bne :+
    jmp pointer_claim_busy
:
    rep #$20
    lda #0
    sta f:PI+1                 ; head/tail
    sta f:PI+42                ; keyboard-only cancel mask stays zero
    sta f:PI+44
    sta f:PI_ROUTE
    sta f:PI_ROUTE+2
    sta f:PI+52
    sta f:PI+54
    sta f:PI+56
    sta f:PI+58
    sta f:PI+64                ; seeded/baseline
    sta f:PI+66                ; disabled
    sta f:PI+68                ; coalescing directions
    sta f:PI+74
    sta f:PI+84                ; consumed epoch
    sta f:PI+86                ; pending
    sta f:PI+112               ; consumed route
    sta f:PI+114
    lda #1
    sta f:PI+60                ; nonzero epoch, never reused in this acquisition
    lda f:IN_POINTER_STATE+IN_STATE_GENERATION
    sta f:PI+48
    lda f:IN_POINTER_STATE+IN_STATE_GENERATION+2
    sta f:PI+50
    lda f:PI_CONFIG+INPUT_CONFIG_INITIALX
    sta f:PI+70
    lda f:PI_CONFIG+INPUT_CONFIG_INITIALY
    sta f:PI+72
    sep #$20
    jsr pointer_history_reset
    lda f:$d300
    and #15
    sta f:PI+62
    lda f:$d010
    and #1
    eor #1
    sta f:PI+63
    lda #0
    sta f:TM_SAMPLE_PHASE
    lda #1
    sta f:PI
    sta f:PI_BINDING+IN_BINDING_ACTIVE
    sta f:TM_POINTER
    lda f:$0010
    jsr timer_mask
    rep #$20
    lda #1
    plp
    rtl
pointer_claim_busy:
    rep #$20
    lda #0
    plp
    rtl
pointer_claim_end:

pointer_release:
    signal_stack_check 40
pointer_release_unchecked:
    php
    sei
    sep #$20
    lda #0
    sta f:TM_POINTER
    sta f:TM_SAMPLE_PHASE
    sta f:PI
    sta f:PI_BINDING+IN_BINDING_ACTIVE
    sta f:PI+86
    lda f:PI+1
    sta f:PI+2
    rep #$20
    lda #0
    sta f:PI+44
    sta f:PI_ROUTE
    sta f:PI_ROUTE+2
    sep #$20
    lda #2
    jsr timer_release
    rep #$20
    plp
    rtl
pointer_release_end:

pointer_publish:
    signal_stack_check 40
    php
    sei
    lda 5,s
    sta f:PI_ROUTE
    lda 7,s
    sta f:PI_ROUTE+2
    sep #$20
    lda #1
    sta f:PI+65
    jsr pointer_history_reset
    lda f:PI+66
    beq :+
    lda #INPUT_LOSS_HARDWARE
    jsr pointer_loss
:
    rep #$20
    plp
    rtl
pointer_publish_end:

; Discard establishes an addressed loss boundary. It need not scan the ring:
; the durable route epoch invalidates all of its earlier records at Take.
pointer_discard:
    signal_stack_check 40
    php
    sei
    lda 5,s
    sta f:PI_LOSS_TAG
    lda 7,s
    sta f:PI_LOSS_TAG+2
    sep #$20
    lda #INPUT_LOSS_RAW
    jsr pointer_loss_tag
    rep #$20
    plp
    rtl
pointer_discard_end:

.a8
pointer_sample:
    lda f:PI
    bne :+
    rts
:
pointer_port_read:
    lda f:$d300
    and #15
    sta f:PI_NEW_PHASE
    lda f:$d010
    and #1
    eor #1
    sta f:PI_NEW_BUTTONS
pointer_decode:
    jsr pointer_age
    ; Most ticks observe an idle mouse. Keep both electrical reads, but avoid
    ; table decoding, counter arithmetic and queue work for an unchanged level.
    lda f:PI_NEW_PHASE
    cmp f:PI+62
    bne pointer_changed
    lda f:PI_NEW_BUTTONS
    cmp f:PI+63
    bne pointer_changed
    lda f:PI+65
    bne pointer_changed
    rts
pointer_changed:
    lda f:PI+62
    and #3
    asl
    asl
    sta f:PI_DX
    lda f:PI_NEW_PHASE
    and #3
    ora f:PI_DX
    rep #$20
    and #15
    tax
    sep #$20
    lda f:pointer_gray,x
    sta f:PI_DX
    lda f:PI_NEW_PHASE
    lsr
    lsr
    sta f:PI_DY
    lda f:PI+62
    and #12
    ora f:PI_DY
    rep #$20
    and #15
    tax
    sep #$20
    lda f:pointer_gray,x
    sta f:PI_DY
    lda f:PI_NEW_PHASE
    sta f:PI+62
    lda f:PI_DX
    cmp #2
    bne :+
    jmp pointer_bad_phase
:
    lda f:PI_DY
    cmp #2
    bne :+
    jmp pointer_bad_phase
:
    ldx #52
    lda f:PI_DX
    jsr pointer_count
    bcs pointer_bad_phase
    ldx #56
    lda f:PI_DY
    jsr pointer_count
    bcs pointer_bad_phase
    jsr pointer_motion_time
    lda f:PI+66
    bne pointer_sample_done
    rep #$20
    lda f:PI_ROUTE
    ora f:PI_ROUTE+2
    sep #$20
    beq pointer_track_button
    lda #0
    sta f:PI_FLAGS
    lda #IN_POINTER_MOTION
    sta f:PI_KIND
    lda f:PI+65
    beq :+
    lda #IN_POINTER_BASELINE
    sta f:PI_FLAGS
    bra pointer_state_sample
:
    lda f:PI_NEW_BUTTONS
    cmp f:PI+63
    bne pointer_state_sample
    lda f:PI_DX
    ora f:PI_DY
    beq pointer_sample_done
    jmp pointer_enqueue
pointer_state_sample:
    jsr pointer_qualifiers
    lda #IN_POINTER_STATE_SAMPLE
    sta f:PI_KIND
    lda f:PI_NEW_BUTTONS
    sta f:PI+63
    jmp pointer_enqueue
pointer_track_button:
    lda f:PI_NEW_BUTTONS
    sta f:PI+63
pointer_sample_done:
    rts
pointer_bad_phase:
    rep #$20
    lda #0
    sta f:PI+52
    sta f:PI+54
    sta f:PI+56
    sta f:PI+58
    sep #$20
    lda f:PI_NEW_BUTTONS
    sta f:PI+63
    lda #INPUT_LOSS_HARDWARE
    jmp pointer_loss

pointer_qualifiers:
    ; Capture qualifiers with the edge/baseline, never during the idle path.
    ; SKSTAT has live Shift; Control is observable only while a key is held.
    lda f:$d20f
    eor #$ff
    and #8
    lsr
    lsr
    ora f:PI_FLAGS
    sta f:PI_FLAGS
    lda f:$d20f
    and #4
    bne pointer_state_modifiers
    lda f:$d209
    and #$80
    beq pointer_state_modifiers
    lda f:PI_FLAGS
    ora #IN_POINTER_CONTROL
    sta f:PI_FLAGS
pointer_state_modifiers:
    rts

; Checked signed cumulative counter, X=52 or56, A=0/+1/-1. C=overflow.
pointer_count:
    cmp #0
    beq pointer_count_unchanged
    cmp #1
    rep #$20
    bne pointer_count_negative
    lda f:PI+2,x
    cmp #$7fff
    bne :+
    lda f:PI,x
    cmp #$ffff
    beq pointer_count_overflow
:
    lda f:PI,x
    inc
    sta f:PI,x
    bne pointer_count_ok
    lda f:PI+2,x
    inc
    sta f:PI+2,x
    bra pointer_count_ok
pointer_count_negative:
    lda f:PI+2,x
    cmp #$8000
    bne :+
    lda f:PI,x
    beq pointer_count_overflow
:
    lda f:PI,x
    bne :+
    lda f:PI+2,x
    dec
    sta f:PI+2,x
:
    lda f:PI,x
    dec
    sta f:PI,x
pointer_count_ok:
    sep #$20
pointer_count_unchanged:
    clc
    rts
pointer_count_overflow:
    sep #$20
    sec
    rts

; Raw records and durable notices deliberately have different strides.
pointer_slot:
    rep #$20
    and #IN_POINTER_SLOTS-1
    asl
    asl
    sta f:PI_SLOT
    asl
    asl
    asl
    sec
    sbc f:PI_SLOT
    tax
    rts
.assert IN_POINTERSAMPLE_SIZE = 28, error, "Update raw pointer stride"

.a8
pointer_notice_slot:
    rep #$20
    and #15
    asl
    asl
    asl
    sta f:PI_SLOT
    asl
    clc
    adc f:PI_SLOT
    tax
    rts
.assert IN_POINTERNOTICE_SIZE = 24, error, "Update pointer notice stride"

; Age uses beam differences at the existing captures, including idle samples.
; Under the capture-gap contract at most one beam wrap can occur per sample.
; Saturation restores the cheap idle path; motion then restarts from slow.
.a8
pointer_history_reset:
    lda #255
    sta f:PI_AGE
    lda #0
    sta f:PI_LAST_X
    sta f:PI_LAST_Y
    rts
pointer_age:
    lda f:PI_AGE
    cmp #255
    beq pointer_age_done
    lda f:$d40b
pointer_age_at:
    sta f:PI_CLOCK_SCRATCH
    sec
    sbc f:PI_BEAM
    bcs :+
    clc
    adc #IN_POINTER_CLOCK_QUANTA
:
    clc
    adc f:PI_AGE
    bcc :+
    lda #255
:
    sta f:PI_AGE
    lda f:PI_CLOCK_SCRATCH
    sta f:PI_BEAM
pointer_age_done:
    rts

; Producer history survives ring draining. Timing is a fact, not GUI gain.
pointer_motion_time:
    lda #0
    sta f:PI_CLASS
    sta f:PI_VECTOR
    sta f:PI_STEPS
    lda f:PI_DX
    ora f:PI_DY
    bne :+
    rts
:
    lda #1
    sta f:PI_STEPS
    lda f:PI_DX
    beq pointer_time_y
    cmp f:PI_LAST_X
    beq pointer_time_x_known
    lda f:PI_LAST_X
    beq pointer_time_x_known
    lda #255
    sta f:PI_AGE
pointer_time_x_known:
    lda f:PI_DX
    sta f:PI_LAST_X
    cmp #255
    bne :+
    lda #2
:
    sta f:PI_VECTOR
pointer_time_y:
    lda f:PI_DY
    beq pointer_time_class
    cmp f:PI_LAST_Y
    beq pointer_time_y_known
    lda f:PI_LAST_Y
    beq pointer_time_y_known
    lda #255
    sta f:PI_AGE
pointer_time_y_known:
    lda f:PI_DY
    sta f:PI_LAST_Y
    cmp #255
    bne :+
    lda #2
:
    asl
    asl
    ora f:PI_VECTOR
    sta f:PI_VECTOR
pointer_time_class:
    lda f:PI_AGE
    rep #$20
    and #255
    tax
    sep #$20
    lda f:pointer_age_class,x
    sta f:PI_CLASS
    lda f:$d40b
    sta f:PI_BEAM
    lda #0
    sta f:PI_AGE
    rts

.a8
pointer_enqueue:
    lda f:PI_KIND
    cmp #IN_POINTER_MOTION
    bne pointer_append
    lda f:PI+1
    cmp f:PI+2
    beq pointer_append
    dec
    jsr pointer_slot
    .a16
    lda f:PI_EVENTS+4,x
    cmp f:PI_ROUTE
    bne pointer_append16
    lda f:PI_EVENTS+6,x
    cmp f:PI_ROUTE+2
    bne pointer_append16
    lda f:PI_EVENTS+20,x
    cmp f:PI+60
    bne pointer_append16
    sep #$20
    lda f:PI_EVENTS+10,x
    cmp #IN_POINTER_MOTION
    bne pointer_append
    lda f:PI_EVENTS+11,x
    cmp f:PI+63
    bne pointer_append
    lda f:PI_CLASS
    cmp f:PI_EVENTS+IN_POINTERSAMPLE_INTERVAL,x
    bne pointer_append
    lda f:PI_VECTOR
    cmp f:PI_EVENTS+IN_POINTERSAMPLE_VECTOR,x
    bne pointer_append
    lda f:PI_EVENTS+IN_POINTERSAMPLE_STEPS,x
    cmp #IN_POINTER_RUN_LIMIT
    bcs pointer_append
    inc
    sta f:PI_EVENTS+IN_POINTERSAMPLE_STEPS,x
    jsr pointer_store_counts
    rts
pointer_append16:
    sep #$20
pointer_append:
    lda f:PI+1
    sec
    sbc f:PI+2
    cmp #IN_POINTER_SLOTS
    bcc :+
    lda #INPUT_LOSS_RAW
    jmp pointer_loss
:
    lda f:PI+1
    jsr pointer_slot
    .a16
    lda f:PI+48
    sta f:PI_EVENTS,x
    lda f:PI+50
    sta f:PI_EVENTS+2,x
    lda f:PI_ROUTE
    sta f:PI_EVENTS+4,x
    lda f:PI_ROUTE+2
    sta f:PI_EVENTS+6,x
    lda f:E816_VBI_COUNT
    sta f:PI_EVENTS+8,x
    lda f:PI+60
    sta f:PI_EVENTS+20,x
    lda f:PI_FLAGS
    and #$ff
    sta f:PI_EVENTS+22,x
    lda f:PI_CLASS
    sta f:PI_EVENTS+IN_POINTERSAMPLE_INTERVAL,x
    lda f:PI_STEPS
    and #255
    sta f:PI_EVENTS+IN_POINTERSAMPLE_STEPS,x
    sep #$20
    lda f:PI_KIND
    sta f:PI_EVENTS+10,x
    lda f:PI+63
    sta f:PI_EVENTS+11,x
    jsr pointer_store_counts
    lda #0
    sta f:PI+65
    lda f:PI+1
    inc
    sta f:PI+1
    jmp pointer_notify
pointer_store_counts:
    rep #$20
    lda f:PI+52
    sta f:PI_EVENTS+12,x
    lda f:PI+54
    sta f:PI_EVENTS+14,x
    lda f:PI+56
    sta f:PI_EVENTS+16,x
    lda f:PI+58
    sta f:PI_EVENTS+18,x
    sep #$20
    rts

pointer_loss:
    pha
    rep #$20
    lda f:PI_ROUTE
    sta f:PI_LOSS_TAG
    lda f:PI_ROUTE+2
    sta f:PI_LOSS_TAG+2
    sep #$20
    pla
pointer_loss_tag:
    sta f:PI_LOSS_CODE
    rep #$20
    lda f:PI+60
    cmp #$ffff
    beq :+
    inc
    sta f:PI+60
    cmp #$ffff
    bne :++
:
    sep #$20
    lda #1
    sta f:PI+66              ; no sample can ever carry epoch $ffff
    rep #$20
:
    lda f:PI_LOSS_TAG
    ora f:PI_LOSS_TAG+2
    bne :+
    sep #$20
    rts
:
    .a16                         ; nonzero route branch still has M=16
    lda f:PI_LOSS_TAG
    and #15
    asl
    tax
    lda f:input_route_bits,x
    and f:PI+44
    beq :+
    ; Preserve the first unacknowledged cause, but advance its baseline/epoch.
    txa
    lsr
    jsr pointer_notice_slot
    .a16
    sep #$20
    lda f:PI_NOTICES+10,x
    sta f:PI_LOSS_CODE
    rep #$20
    bra pointer_notice_store
:
    lda f:input_route_bits,x
    ora f:PI+44
    sta f:PI+44
    txa
    lsr
    jsr pointer_notice_slot
    .a16
pointer_notice_store:
    lda f:PI+48
    sta f:PI_NOTICES,x
    lda f:PI+50
    sta f:PI_NOTICES+2,x
    lda f:PI_LOSS_TAG
    sta f:PI_NOTICES+4,x
    lda f:PI_LOSS_TAG+2
    sta f:PI_NOTICES+6,x
    lda #0
    sta f:PI_NOTICES+8,x
    sta f:PI_NOTICES+22,x
    lda f:PI+52
    sta f:PI_NOTICES+12,x
    lda f:PI+54
    sta f:PI_NOTICES+14,x
    lda f:PI+56
    sta f:PI_NOTICES+16,x
    lda f:PI+58
    sta f:PI_NOTICES+18,x
    lda f:PI+60
    sta f:PI_NOTICES+20,x
    sep #$20
    lda f:PI_LOSS_CODE
    sta f:PI_NOTICES+10,x
    lda f:PI+63
    sta f:PI_NOTICES+11,x
    ; A discard of a different retained route does not rebase live motion.
    ; Epochs allocate globally, but invalidation is qualified by route/acq.
    rep #$20
    lda f:PI_LOSS_TAG
    cmp f:PI_ROUTE
    bne pointer_loss_other_route
    lda f:PI_LOSS_TAG+2
    cmp f:PI_ROUTE+2
    bne pointer_loss_other_route
    sep #$20
    lda #1
    sta f:PI+65
    jsr pointer_history_reset
    bra pointer_notify
pointer_loss_other_route:
    .a16
    lda f:PI_ROUTE
    ora f:PI_ROUTE+2
    sep #$20
    beq pointer_notify
    lda f:PI+66
    beq pointer_notify
    ; Exhaustion disables the current route too. Retain its own notice before
    ; notifying; the tail call visits the current route once, never a scan.
    lda #INPUT_LOSS_HARDWARE
    jmp pointer_loss
pointer_notify:
    jsr sio_pointer_service
    ldx #PI_BINDING-T_BASE
    jmp signal_post_binding

.a16
; Take one coherent record (28-byte raw, 24-byte loss/public event).
; 0 empty,1 sample,2 durable loss,3 pending
; public event,4 invalidated sample. No ring scan with IRQ masked.
pointer_take:
    signal_stack_check 40
    php
    sei
    phd
    tsc
    sec
    sbc #4
    tcs
    tcd
    lda 11,s
    sta 1
    lda 13,s
    and #$ff
    sta 3
    lda f:PI+44
    beq pointer_take_pending
    ldx #0
:
    lsr
    bcs :+
    inx
    inx
    bra :-
:
    lda f:input_route_bits,x
    eor #$ffff
    and f:PI+44
    sta f:PI+44
    txa
    lsr
    jsr pointer_notice_slot
    .a16
    txa
    clc
    adc #IN_POINTERCAPTURE_NOTICES
    tax
    lda #2
    bra pointer_take_copy
pointer_take_pending:
    lda f:PI+86
    and #$ff
    beq pointer_take_raw
    sep #$20
    lda #0
    sta f:PI+86
    rep #$20
    ldx #IN_POINTERCAPTURE_OUTPUT
    lda f:PI+116
    jsr pointer_obsolete
    bcs pointer_take_raw
    lda #3
    bra pointer_take_copy
pointer_take_raw:
    sep #$20
    lda f:PI+2
    cmp f:PI+1
    bne :+
    rep #$20
    lda #0
    jmp pointer_take_return
:
    inc
    sta f:PI+2
    dec
    jsr pointer_slot
    .a16
    txa
    clc
    adc #IN_POINTERCAPTURE_EVENTS
    tax
    lda f:PI+20,x
    jsr pointer_obsolete
    bcc :+
    lda #4
    jmp pointer_take_return
:
    lda #1
pointer_take_copy:
    pha
    .repeat 12, word
        ldy #word*2
        lda f:PI+word*2,x
        sta [1],y
    .endrepeat
    pla
    cmp #1
    bne pointer_take_return
    pha
    ldy #24
    lda f:PI+24,x
    sta [1],y
    ldy #26
    lda f:PI+26,x
    sta [1],y
    pla
pointer_take_return:
    tax
    tsc
    clc
    adc #4
    tcs
    txa
    pld
    plp
    rtl
pointer_take_end:

; X=record offset, A=its epoch. Carry set iff a newer matching route notice
; invalidated it, even after the notice was acknowledged. X preserved.
pointer_obsolete:
    pha
    phx
    lda f:PI,x
    pha
    lda f:PI+2,x
    pha
    lda f:PI+4,x
    pha
    lda f:PI+6,x
    pha
    lda 3,s
    and #15
    jsr pointer_notice_slot
    .a16
    lda f:PI_NOTICES+4,x
    cmp 3,s
    bne pointer_obsolete_no
    lda f:PI_NOTICES+6,x
    cmp 1,s
    bne pointer_obsolete_no
    lda f:PI_NOTICES,x
    cmp 7,s
    bne pointer_obsolete_no
    lda f:PI_NOTICES+2,x
    cmp 5,s
    bne pointer_obsolete_no
    lda f:PI_NOTICES+20,x
    cmp 11,s
    beq pointer_obsolete_no
    bcc pointer_obsolete_no
    pla
    pla
    pla
    pla
    plx
    pla
    sec
    rts
pointer_obsolete_no:
    pla
    pla
    pla
    pla
    plx
    pla
    clc
    rts
pointer_gray:
    .byte 0,255,1,2, 1,0,2,255, 255,2,0,1, 2,1,255,0
.include "pointer-timing.inc"

; Diagnostic-only decoder entry. The real-controller acceptance path never
; uses it. A fixture holds Forbid; saved I protects the same shared scratch.
.if SIGNAL_IRQ_PROBE = 12
.export pointer_probe_suspend,pointer_probe_suspend_end
.export pointer_probe_sample,pointer_probe_sample_end
.export pointer_probe_nmi,pointer_probe_nmi_end
.export pointer_probe_clock,pointer_probe_clock_end
.export pointer_probe_timed,pointer_probe_timed_end
.a16
; Inject captured facts for deterministic decoder/coalescing proofs. Electrical
; timing acceptance continues to use pointer_port_read and the real controller.
pointer_probe_timed:
    signal_stack_check 40
    php
    sei
    lda 5,s
    sta f:PI_NEW_PHASE
    sep #$20
    lda 7,s
    sta f:PI_AGE
    jsr pointer_changed
    rep #$20
    plp
    rtl
pointer_probe_timed_end:
.a16
pointer_probe_clock:
    signal_stack_check 40
    php
    sei
    sep #$20
    lda 5,s
    sta f:PI_BEAM
    lda 9,s
    sta f:PI_AGE
    lda 7,s
    jsr pointer_age_at
    rep #$20
    lda f:PI_AGE
    and #255
    plp
    rtl
pointer_probe_clock_end:
.a16
pointer_probe_suspend:
    signal_stack_check 40
    php
    sei
    sep #$20
    lda #0
    sta f:TM_POINTER
    lda f:$0010
    jsr timer_mask
    rep #$20
    plp
    rtl
pointer_probe_suspend_end:
pointer_probe_sample:
    signal_stack_check 40
    php
    sei
    lda 5,s
    sta f:PI_NEW_PHASE
    sep #$20
    jsr pointer_decode
    rep #$20
    plp
    rtl
pointer_probe_sample_end:
pointer_probe_nmi:
    signal_stack_check 40
    php
    sei
    lda f:E816_VBI_COUNT
:
    cmp f:E816_VBI_COUNT
    beq :-
    plp
    rtl
pointer_probe_nmi_end:
.endif
.segment "SIGNAL_CODE"
