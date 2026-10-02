; Shared POKEY timer 1. Fixed backends only; no callback registration or Task.
; State/code are in the existing upper Task arena. Task callers hold SWITCHING;
; acquisition/release mask IRQ locally. NMI records ticks without switching.
.segment "SIGNAL_CODE"
.a8
.i16
.export timer_tick,timer_sample,timer_poll

; A=owner bit (1 SIO, 2 pointer). A=1 success, 0 busy. Preserve incoming I.
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

; Compose the timer bit from demand, preserving all caller-selected other bits.
timer_mask:
    and #$fe
    pha
    lda f:TM_ALARM
    ora f:TM_POINTER
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
    lda f:TM_POINTER
    beq timer_poll_done
    jsr sio_pointer_service
    jsr timer_sample
    jsr sio_pointer_service
timer_poll_done:
    rts

timer_sample:
.if SIGNAL_IRQ_PROBE = 11
    ; Fixed bounded electrical sampler. M3 substitutes the real decoder and
    ; repeats gap/cost checks; this code is absent from production images.
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
    signal_stack_check 25
    jsr sio_enter
    sep #$20
    lda #2
    jsr timer_acquire
    beq :+
    php
    sei
    lda #1
    sta f:TM_POINTER
    lda f:$0010
    jsr timer_mask
    plp
    lda #1
:
    rep #$20
    and #$ff
    jmp sio_leave
timer_probe_start_end:
timer_probe_stop:
    signal_stack_check 25
    jsr sio_enter
    sep #$20
    lda #0
    sta f:TM_POINTER
    lda #2
    jsr timer_release
    rep #$20
    jmp sio_leave
timer_probe_stop_end:
.endif
