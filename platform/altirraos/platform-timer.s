; Shared POKEY timer 1. Fixed backends only; no callback registration or Task.
; State/code are in the existing upper Task arena. Task callers hold SWITCHING;
; acquisition/release mask IRQ locally. NMI records ticks without switching.
.segment "SIGNAL_CODE"
.a8
.i16
.export timer_tick,timer_sample,timer_poll
.export timer_fine_start,timer_fine_end

; A=owner bit (1 SIO, 2 pointer, 4 blitter). A=1 success, 0 busy. Preserve incoming I.
; First ownership establishes the platform's silent audio baseline. There is
; no audio owner/shadow to restore before that boundary; never read POT aliases.
timer_acquire:
    php
    sei
    pha
    and f:TM_USERS
    bne timer_acquire_busy
    lda f:TM_USERS
    bne timer_acquire_join
    lda f:$0010
    and #3
    bne timer_acquire_busy
    lda f:$0232
    and #3
    cmp #3
    bne timer_acquire_busy
    rep #$20
    lda f:$0210
    sta f:TM_VECTOR
    lda #sio_emu_alarm
    sta f:$0210
    sep #$20
    lda #TIMER_DIVISOR
    sta f:TM_AUDF1
    sta f:$d200
    lda #0
    sta f:TM_FINE
    sta f:TM_SAMPLE_PHASE
    sta f:$d201
    lda #TIMER_AUDCTL
    sta f:TM_AUDCTL
    sta f:$d208
    sta f:$d209
timer_acquire_join:
    pla
    ora f:TM_USERS
    sta f:TM_USERS
    plp
    lda #1
    rts
timer_acquire_busy:
    pla
    plp
    lda #0
    rts

; A=owner bit to remove, with that owner's demand already retired.
timer_release:
    php
    sei
    pha
    and f:TM_USERS
    bne :+
    pla
    plp
    rts
:
    pla
    eor #$ff
    and f:TM_USERS
    sta f:TM_USERS
    bne timer_release_mask
    rep #$20
    lda f:TM_VECTOR
    sta f:$0210
    sep #$20
    lda #0
    sta f:TM_FINE
    sta f:TM_SAMPLE_PHASE
    sta f:TM_AUDF1
    sta f:TM_AUDCTL
    sta f:$d200
    sta f:$d201
    sta f:$d208
    sta f:$d209
timer_release_mask:
    lda f:$0010
    jsr timer_mask
    plp
    rts

; SIO holds fine timing across COMMAND setup/transmission/hold and separately
; during write turnaround. Call M8/X16/I=1 under SWITCHING or IRQ_DEPTH, so NMI
; may record a tick but cannot switch through half-published cadence state.
; AUDF1 changes reload only: never reset STIMER here (it also clocks serial).
; A partial old period may survive the write. Reset the capture divider, skip
; the first fine edge, then sample every second edge. Normal edges all sample.
; No synthetic/catch-up samples are taken. Joining timer owners changes no rate.
timer_fine_start:
    lda #1
    sta f:TM_FINE
    lda #TIMER_FINE_DIVISOR
    bra timer_rate
timer_fine_end:
    lda #0
    sta f:TM_FINE
    lda #TIMER_DIVISOR
timer_rate:
    cmp f:TM_AUDF1
    beq timer_rate_done
    sta f:TM_AUDF1
    sta f:$d200
    lda #0
    sta f:TM_SAMPLE_PHASE
timer_rate_done:
    rts

; Compose the timer bit from demand, preserving all caller-selected other bits.
timer_mask:
    and #$fe
    pha
    lda f:TM_ALARM
    ora f:TM_POINTER
    ora f:TM_BLITTER
    beq :+
    pla
    ora #1
    bra :++
:
    pla
:
    sta f:$0010
    sta f:$d20e
    rts

; A=new logical alarm count. Retire a stale physical edge before admission.
; Pointer demand stays enabled; the skipped sampling opportunity is measured.
timer_arm:
    sta f:SD_ALARM
    lda f:$0010
    and #$fe
    sta f:$d20e
    lda #1
    sta f:TM_ALARM
    lda f:$0010
    jmp timer_mask

; Check, acknowledge once, then dispatch each eligible user at most once.
timer_poll:
    lda f:TM_USERS
    beq timer_poll_done
    lda f:$0010
    and #1
    beq timer_poll_done
    lda f:$d20e
    and #1
    bne timer_poll_done
timer_ack:
    lda f:$0010
    and #$fe
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
timer_tick:
    rep #$20
    lda f:TM_TICKS
    inc a
    sta f:TM_TICKS
    sep #$20
    lda f:TM_ALARM
    beq :+
    jsr sio_alarm
:
    lda f:TM_BLITTER
    beq :+
    jsr blitter_watchdog
:
    lda f:TM_POINTER
    beq timer_poll_done
    jsr sio_pointer_service
    lda f:TM_FINE
    beq timer_capture
    lda f:TM_SAMPLE_PHASE
    inc a
    cmp #TIMER_POINTER_DIVIDER
    bcc timer_skip_capture
    lda #0
    sta f:TM_SAMPLE_PHASE
timer_capture:
    jsr timer_sample
    jsr sio_pointer_service
timer_poll_done:
    rts
timer_skip_capture:
    sta f:TM_SAMPLE_PHASE
    ; Serial service remains bounded even on a fine tick with no capture.
    jmp sio_pointer_service

timer_sample:
.if INPUT_NATIVE
    jsr pointer_sample
.export pointer_sample_return
pointer_sample_return:
.endif
.if SIGNAL_IRQ_PROBE = 11
    ; Passive counters around the real M3 backend. These diagnostic counters
    ; and entry points are absent from production images.
    rep #$20
    lda f:TM_SAMPLES
    inc a
    sta f:TM_SAMPLES
    sep #$20
    lda f:$d300
    and #15
    cmp f:TM_PORT
    beq :+
    sta f:TM_PORT
    rep #$20
    lda f:TM_CHANGES
    inc a
    sta f:TM_CHANGES
    sep #$20
:
    lda f:$d010
    and #1
    sta f:TM_TRIGGER
.endif
    rts

.if SIGNAL_IRQ_PROBE = 11
.a16
.export timer_probe_start,timer_probe_start_end,timer_probe_stop,timer_probe_stop_end
timer_probe_start:
    jmp pointer_claim
timer_probe_start_end:
timer_probe_stop:
    jmp pointer_release
timer_probe_stop_end:
.endif
