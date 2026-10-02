; Buffered SIO hardware adapter. All persistent state/code is in upper RAM.
; The descriptor is private: publish only after preparation, retire before reuse.
.segment "SIGNAL_CODE"
.a16
.i16
.export sio_init,sio_init_end,sio_start,sio_start_end,sio_cancel,sio_cancel_end
.export sio_retire,sio_retire_end,sio_shutdown,sio_shutdown_end
.export sio_recovered,sio_recovered_end
.export sio_route,sio_terminal,sio_rx,sio_tx,sio_alarm,sio_watchdog
.export sio_probe_os
.export SIO_STATE,SD_PHASE,SD_POSTS,SD_EMULATIONS,SD_ACTUAL,SD_ERROR

; All public native entries are private task-only imports. SWITCHING guards
; NMI re-entry during descriptor/configuration writes; only publication masks IRQ.
sio_enter:
    jsr io_context
    sep #$20
    lda #1
    sta f:E816_SWITCHING
    rep #$20
    rts
sio_leave:
    pha
    sep #$20
    lda #0
    sta f:E816_SWITCHING
    rep #$20
    pla
    rtl

sio_init:
    signal_stack_check 19
    jsr sio_enter
    lda f:SD_OWNED
    and #$ff
    beq :+
    jmp sio_init_busy
:
    lda f:SIO_ACTIVE
    and #$ff
    bne :+
    jmp sio_init_busy
:
    lda f:OS_BUSY
    and #$ff
    beq :+
    jmp sio_init_busy
:
    ; Existing timer owners have no protocol for lending their configuration.
    lda f:$0010
    and #3
    beq :+
    jmp sio_init_busy
:
    ; The serial binding is already stable, with sources disabled. Take timer
    ; vectors and masks too. IRQ remains enabled during all multi-byte copies.
    ldx #0
:
    lda f:$020a,x
    sta f:SD_VECTORS,x
    inx
    inx
    cpx #10
    bcc :-
    sep #$20
    lda f:$0010
    and #SIO_OWNED_MASK
    ora f:SIO_SAVED_MASK
    sta f:SD_OLD_MASK
    lda f:SIO_SAVED_CRITIC
    sta f:SD_OLD_CRITIC
    lda f:$0232
    sta f:SD_OLD_SKCTL
    lda f:$d303
    and #$38
    sta f:SD_OLD_PBCTL
    ; Establish the platform's silent baseline. No reads of write-only aliases.
    lda #0
    ldx #8
:
    sta f:SD_SHADOW,x
    sta f:SD_SAVED_AUDIO,x
    sta f:$d200,x
    dex
    bpl :-
    lda #3
    sta f:$0232
    sta f:$d20f
    rep #$20
    lda #sio_emu_rx
    sta f:$020a
    lda #sio_emu_tx
    sta f:$020c
    lda #sio_emu_complete
    sta f:$020e
    lda #sio_emu_alarm
    sta f:$0210
    lda #sio_emu_watchdog
    sta f:$0212
    php
    sei
    sep #$20
    lda f:$0010
    and #($ff-SIO_OWNED_MASK)
    jsr sio_mask
    lda #1
    sta f:SD_OWNED
    lda #0
    sta f:SD_PHASE
    lda f:SD_OLD_CRITIC
    sta f:$0042
    rep #$20
    plp
    lda #1
    jmp sio_leave
sio_init_busy:
    lda #0
    jmp sio_leave
sio_init_end:

sio_start:
    signal_stack_check 19
    jsr sio_enter
    lda f:SD_OWNED
    and #$ff
    bne :+
    jmp sio_start_busy
:
    lda f:SD_PHASE
    and #$ff
    beq :+
    jmp sio_start_busy
:
    lda f:SD_OFFLINE
    and #$ff
    beq :+
    jmp sio_start_busy
:
    ; Fully initialized inactive descriptor; pending IRQs cannot consume it.
    lda #0
    sta f:SD_ACTUAL
    sta f:SD_CHECKSUM
    lda f:SD_CLOCK
    clc
    adc f:SD_TIMEOUT
    sta f:SD_DEADLINE
    lda f:SD_GENERATION
    inc a
    sta f:SD_GENERATION
    sep #$20
    lda #0
    sta f:SD_ERROR
    sta f:SD_SAFE
    sta f:SD_STARTED
    sta f:SD_RECOVERY
    lda f:SD_CANCEL
    beq :+
    php
    sei
    lda #1
    sta f:SD_PHASE
    lda #$fe
    jsr sio_fail
    plp
    rep #$20
    lda #1
    jmp sio_leave
:
    .a8
    ; A retired safe frame leaves the serial engine idle. Resetting SKCTL to
    ; zero here also resets keyboard scan/debounce and reissues a held key.
    ; Keep scanning enabled; STIMER below establishes the transaction phase.
    lda #7
    sta f:SD_SHADOW
    sta f:$d200
    lda #$ff
    sta f:SD_SHADOW+2
    sta f:$d202
    lda f:SD_DIVISOR
    sta f:SD_SHADOW+4
    sta f:$d204
    lda #0
    sta f:SD_SHADOW+6
    sta f:$d206
    lda #$28
    sta f:SD_SHADOW+8
    sta f:$d208
    lda #$23
    sta f:$0232
    sta f:$d20f
    .if INPUT_NATIVE
        jsr input_before_reset
    .elseif SIGNAL_IRQ_PROBE = 10
        jsr console_probe_errors
    .endif
    sta f:$d20a
    php
    sei
    ; Private RX can latch offline while task-side configuration permits IRQ.
    ; Recheck at publication, before asserting COMMAND or exposing the cursor.
    lda f:SD_OFFLINE
    beq :+
    plp
    rep #$20
    lda #0
    jmp sio_leave
:
    .a8
    lda #1
    sta f:$0042
    sta f:SD_PHASE
    sta f:SD_STARTED
    lda f:$d303
    and #$c7
    ora #$30
    sta f:$d303
    ; Begin the deadline at COMMAND assertion. Reset once before enabling
    ; any source, while no serial bits are being shifted. Never reset for
    ; a later phase; no old free-running watchdog edge can enter this arm.
    sta f:$d209
    lda f:$0010
    and #($ff-SIO_OWNED_MASK)
    ora #2
    jsr sio_mask
    lda #8
    jsr sio_arm
    lda f:SD_CANCEL
    beq :+
    lda #$fe
    jsr sio_fail
:
    plp
    rep #$20
    lda #1
    jmp sio_leave
sio_start_busy:
    lda #0
    jmp sio_leave
sio_start_end:

sio_cancel:
    signal_stack_check 3
    jsr io_context
    sep #$20
    lda #1
    sta f:SD_CANCEL
    rep #$20
    rtl
sio_cancel_end:

sio_retire:
    signal_stack_check 19
    jsr sio_enter
    lda f:SD_PHASE
    and #$ff
    cmp #SIO_TERMINAL
    bne sio_retire_busy
    ; IRQ has cleared every caller pointer and disabled/acknowledged sources.
    ; Descriptor remains terminal until after this worker has consumed the post.
    sep #$20
    lda f:$d20d             ; discard any old hardware latch
    lda #15
    sta f:SD_PHASE
    lda #0
    sta f:SD_CANCEL
    lda f:SD_OLD_CRITIC
    sta f:$0042
    rep #$20
    lda #1
    jmp sio_leave
sio_retire_busy:
    lda #0
    jmp sio_leave
sio_retire_end:

; Clean completion may retire immediately; errors retain the worker's quiet
; interval. A late byte or uncertain outcome permanently owns the bus offline.
sio_recovered:
    signal_stack_check 19
    jsr sio_enter
    lda f:SD_PHASE
    and #$ff
    cmp #15
    bne sio_recovered_busy
    lda f:SD_OFFLINE
    and #$ff
    bne sio_recovered_busy
    sep #$20
    lda #0
    sta f:SD_PHASE
    rep #$20
    lda #1
    jmp sio_leave
sio_recovered_busy:
    lda #0
    jmp sio_leave
sio_recovered_end:

sio_shutdown:
    signal_stack_check 19
    jsr sio_enter
    lda f:SD_OFFLINE
    and #$ff
    beq :+
    lda #$ff93
    jml finish
:
    jsl sio_shutdown_unchecked
    lda #0
    jmp sio_leave
sio_shutdown_end:
sio_shutdown_unchecked:
    php
    sei
    rep #$30
    lda f:SD_OWNED
    and #$ff
    bne :+
    jmp sio_shutdown_done
:
    sep #$20
    lda f:$0010
    and #($ff-SIO_OWNED_MASK)
    jsr sio_mask
    lda #0
    sta f:SD_OWNED
    sta f:SD_PHASE
    sta f:SD_CURSOR+2
    sta f:SD_DATA+2
    rep #$20
    lda #0
    sta f:SD_CURSOR
    sta f:SD_DATA
    ldx #0
:
    lda f:SD_VECTORS,x
    sta f:$020a,x
    inx
    inx
    cpx #10
    bcc :-
    sep #$20
    ldx #8
:
    lda f:SD_SAVED_AUDIO,x
    sta f:SD_SHADOW,x
    sta f:$d200,x
    dex
    bpl :-
    .if INPUT_NATIVE
        lda f:CI_ACTIVE
        beq :+
        lda f:SD_OLD_SKCTL
        ora #3
        bra :++
:
        lda f:SD_OLD_SKCTL
:
    .else
        lda f:SD_OLD_SKCTL
    .endif
    sta f:$0232
    sta f:$d20f
    sta f:$d209
    lda f:$d303
    and #$c7
    ora f:SD_OLD_PBCTL
    sta f:$d303
    lda f:$0010
    and #($ff-SIO_OWNED_MASK)
    ora f:SD_OLD_MASK
    jsr sio_mask
    lda f:SD_OLD_CRITIC
    sta f:$0042
sio_shutdown_done:
    rep #$30
    plp
    rtl

; Native IRQ entry has already saved all registers, D/DBR and hidden halves.
; One bounded pass, serial first. Return C clear for simultaneous unowned IRQ.
.a8
.i16
sio_route:
    lda f:SD_PHASE
    beq sio_route_private
    cmp #SIO_TERMINAL
    beq sio_route_private
    cmp #15
    bne sio_route_active
sio_route_private:
    lda f:$d20e
    eor #$ff
    and f:$0010
    and #$20
    beq sio_route_private_done
    lda f:$0010
    and #$df
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    jsr sio_discard
sio_route_private_done:
    jmp sio_route_exit
sio_route_active:
    lda f:SD_CANCEL
    beq :+
    lda #$fe
    jsr sio_fail
    jmp sio_route_exit
:
    .repeat 5,source
        .if source=0
            bitmask .set $20
        .elseif source=1
            bitmask .set $10
        .elseif source=2
            bitmask .set $08
        .elseif source=3
            bitmask .set $02
        .else
            bitmask .set $01
        .endif
        ; Disabled sources cannot need service. Avoid their slow POKEY reads
        ; during RX; scanline DMA can otherwise delay a newly asserted timer
        ; until a second IRQ pass. Re-read the enable shadow after each handler
        ; because a terminal byte can disable the remaining owned sources.
        .if source>0
            lda f:$0010
            and #bitmask
            beq .ident(.sprintf("sio_source_done_%d", source))
        .endif
        lda f:$d20e
        eor #$ff
        .if source=0
            and f:$0010
        .endif
        and #bitmask
        beq .ident(.sprintf("sio_source_done_%d", source))
        lda f:$0010
        and #($ff-bitmask)
        sta f:$d20e
        lda f:$0010
        sta f:$d20e
        .if source=0
            jsr sio_rx
        .elseif source=1
            jsr sio_tx
        .elseif source=2
            jsr sio_complete
        .elseif source=4
            jsr sio_alarm
            ; Starting COMMAND/write sends its first byte from the alarm
            ; handler. TX-ready can assert during the subsequent prefetch;
            ; scanline DMA can make a full return/re-entry miss that first
            ; refill deadline. Service it once here, after the timer phase
            ; transition, with the current enable shadow. No loop or new state.
            lda f:$0010
            and #$10
            beq sio_source_done_4
            lda f:$d20e
            eor #$ff
            and #$10
            beq sio_source_done_4
            lda f:$0010
            and #$ef
            sta f:$d20e
            lda f:$0010
            sta f:$d20e
            jsr sio_tx
        .else
            ; Enforce the absolute deadline before an expired fine alarm can
            ; start another phase. Serial bytes still have first priority.
            jsr sio_watchdog
            ; A byte can arrive after the first serial check while servicing
            ; the watchdog. Recheck once before paying another IRQ entry and
            ; return; this bounded second check avoids a scanline-DMA deadline
            ; miss. Terminal commit has already disabled these bits.
            lda f:$d20e
            eor #$ff
            and f:$0010
            and #$20
            beq sio_watchdog_rx_done
            lda f:$0010
            and #$df
            sta f:$d20e
            lda f:$0010
            sta f:$d20e
            jsr sio_rx
sio_watchdog_rx_done:
            lda f:$d20e
            eor #$ff
            and f:$0010
            and #$10
            beq sio_source_done_3
            lda f:$0010
            and #$ef
            sta f:$d20e
            lda f:$0010
            sta f:$d20e
            jsr sio_tx
        .endif
.ident(.sprintf("sio_source_done_%d", source)):
    .endrepeat
sio_route_exit:
    lda f:$d20e
    eor #$ff
    and f:$0010
    and #($ff-SIO_OWNED_MASK)
    .if INPUT_NATIVE .or SIGNAL_IRQ_PROBE = 10
        bit #$c0
        beq :+
        ; An edge may have arrived since the serial scan. Do not carry it
        ; through keyboard status reads, route publication and the wake post.
        jsr sio_console_service
        .if INPUT_NATIVE
            jsl input_route
        .else
            jsl console_probe_route
        .endif
        ; A keyboard post can span a serial byte or either timer edge. Give
        ; them a bounded service opportunity before restore/re-entry and
        ; another slow POKEY read under display DMA.
        jsr sio_console_service
        lda f:$d20e
        eor #$ff
        and f:$0010
        and #($ff-SIO_OWNED_MASK)
:
    .endif
    bne :+
    sec
    rtl
:
    clc
    rtl

.if INPUT_NATIVE .or SIGNAL_IRQ_PROBE = 10
; At most three RX checks, one watchdog, phase alarm and TX refill per call. The console
; calls this between raw publication and its potentially queued wake post;
; the route calls it again before exit. A timer asserted after the route's
; initial scan must not wait through two RX checks and a full IRQ re-entry.
sio_console_service:
    lda f:SD_OWNED
    beq sio_console_inactive
    lda f:SD_PHASE
    beq sio_console_inactive
    cmp #SIO_TERMINAL
    beq sio_console_inactive
    cmp #15
    bne sio_console_active
sio_console_inactive:
    rts
sio_console_active:
    lda f:$d20e
    eor #$ff
    and f:$0010
    and #$20
    beq sio_console_watchdog
    lda f:$0010
    and #$df
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    jsr sio_rx
sio_console_watchdog:
    ; RX may have completed the request and disabled the watchdog. Check the
    ; current enable shadow before reading/acknowledging its pending bit.
    lda f:$0010
    and #$02
    beq sio_console_alarm
    lda f:$d20e
    eor #$ff
    and #$02
    beq sio_console_alarm
    lda f:$0010
    and #$fd
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    jsr sio_watchdog
    ; A byte can arrive after the first RX check while acknowledging the
    ; timer. Retire it before the keyboard wake post and IRQ restoration.
    lda f:$d20e
    eor #$ff
    and f:$0010
    and #$20
    beq sio_console_alarm
    lda f:$0010
    and #$df
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    jsr sio_rx
sio_console_alarm:
    ; A fine alarm can assert during keyboard capture after the route's timer
    ; scan. Service it here instead of paying another IRQ return/entry and
    ; display-DMA-delayed POKEY read. The watchdog keeps first-cause priority.
    lda f:$0010
    and #$01
    beq sio_console_tx
    lda f:$d20e
    eor #$ff
    and #$01
    beq sio_console_tx
    lda f:$0010
    and #$fe
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    jsr sio_alarm
sio_console_tx:
    ; The alarm may have started COMMAND/write and prefetched its next byte.
    ; Refill once with the current enable shadow, including on the second
    ; console-service call after the wake post. No unbounded IRQ loop.
    lda f:$0010
    and #$10
    beq sio_console_service_done
    lda f:$d20e
    eor #$ff
    and #$10
    beq sio_console_service_done
    lda f:$0010
    and #$ef
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    jsr sio_tx
sio_console_service_done:
    ; POKEY status reads can stall behind display DMA. A receive edge just
    ; after the earlier RX check must not wait through the remaining timer/TX
    ; checks and an IRQ return/re-entry. This final bounded check also runs
    ; when no timer asserted. Use the current enables after a terminal byte.
    lda f:$0010
    and #$20
    beq sio_console_return
    lda f:$d20e
    eor #$ff
    and #$20
    beq sio_console_return
    lda f:$0010
    and #$df
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    lda f:SD_PHASE
    cmp #SIO_TERMINAL
    beq sio_console_discard
    jmp sio_rx
sio_console_discard:
    ; The first RX check may have completed a healthy frame. A trailing byte
    ; now belongs to recovery, and must retain the existing offline policy.
    jmp sio_discard
sio_console_return:
    rts
.endif

sio_mask:
    sta f:$0010
    sta f:$d20e
    rts
sio_arm:
    sta f:SD_ALARM
    lda f:$0010
    and #$fe
    sta f:$d20e
    ora #1
    jmp sio_mask

sio_alarm:
    rep #$20
    lda f:SD_ALARMS
    inc a
    sta f:SD_ALARMS
    sep #$20
    lda f:SD_ALARM
    beq sio_alarm_done
    dec a
    sta f:SD_ALARM
    bne sio_alarm_done
    lda f:$0010
    and #$fe
    jsr sio_mask
    lda f:SD_PHASE
    cmp #1
    beq sio_command_begin
    cmp #4
    beq sio_command_end
    cmp #6
    beq sio_write_begin
    jmp sio_protocol
sio_alarm_done:
    rts
sio_command_begin:
    rep #$20
    lda #.loword(SD_COMMAND)
    sta f:SD_CURSOR
    lda #5
    sta f:SD_REMAIN
    sep #$20
    lda #^SD_COMMAND
    sta f:SD_CURSOR+2
    lda #2
    sta f:SD_PHASE
    lda f:$0010
    ora #$10
    jsr sio_mask
    jsr sio_read_byte
    jmp sio_tx
sio_command_end:
    lda #$13
    sta f:$0232
    sta f:$d20f
    lda #5
    sta f:SD_PHASE
    lda f:$0010
    ora #$20
    jsr sio_mask
    lda f:$d303
    ora #$38
    sta f:$d303
    rts
sio_write_begin:
    jsr sio_payload_cursor
    lda #$23
    sta f:$0232
    sta f:$d20f
    lda #7
    sta f:SD_PHASE
    lda f:$0010
    and #$df
    ora #$10
    jsr sio_mask
    jsr sio_read_byte
    jmp sio_tx
sio_payload_cursor:
    rep #$20
    lda f:SD_DATA
    sta f:SD_CURSOR
    lda f:SD_LENGTH
    sta f:SD_REMAIN
    sep #$20
    lda f:SD_DATA+2
    sta f:SD_CURSOR+2
    lda #0
    sta f:SD_CHECKSUM
    rts

; Long-indirect cursor uses four activation-local bytes, never a shared DP.
; Entry M8, X16. Restores D and S. No caller buffer access after terminal commit.
sio_read_byte:
    rep #$20
    phd
    lda f:SD_CURSOR+2
    and #$ff
    pha
    lda f:SD_CURSOR
    pha
    tsc
    tcd
    sep #$20
    lda [1]
    sta f:SD_VALUE
    rep #$20
    pla
    pla
    pld
    sep #$20
    lda f:SD_VALUE
    rts
sio_write_byte:
    rep #$20
    phd
    lda f:SD_CURSOR+2
    and #$ff
    pha
    lda f:SD_CURSOR
    pha
    tsc
    tcd
    sep #$20
    lda f:SD_VALUE
    sta [1]
    rep #$20
    pla
    pla
    pld
    sep #$20
    rts
sio_advance:
    rep #$20
    lda f:SD_CURSOR
    inc a
    sta f:SD_CURSOR
    bne :+
    sep #$20
    lda f:SD_CURSOR+2
    inc a
    sta f:SD_CURSOR+2
    rep #$20
:
    lda f:SD_REMAIN
    dec a
    sta f:SD_REMAIN
    sep #$20
    rts
sio_tx:
    rep #$20
    lda f:SD_REMAIN
    sep #$20
    bne sio_tx_byte
    lda f:SD_PHASE
    cmp #7
    bne sio_tx_drain
    ; One checksum byte follows the payload; io_Actual excludes it.
    lda f:SD_CHECKSUM
    sta f:$d20d
    lda #14
    sta f:SD_PHASE
    rts
sio_tx_drain:
    lda f:SD_PHASE
    cmp #14
    bne :+
    lda #7
:
    inc a
    sta f:SD_PHASE
    lda f:$0010
    and #$ef
    ora #8
    jmp sio_mask
sio_tx_byte:
    ; The next byte was prefetched after the previous SEROUT refill. Keep
    ; the long-indirect cursor/stack work out of the next refill deadline.
    ; RX and TX payload phases are mutually exclusive owners of SD_VALUE.
    lda f:SD_VALUE
    sta f:$d20d
    lda f:SD_PHASE
    cmp #7
    bne :+
    lda f:SD_VALUE
    clc
    adc f:SD_CHECKSUM
    adc #0
    sta f:SD_CHECKSUM
    rep #$20
    lda f:SD_ACTUAL
    inc a
    sta f:SD_ACTUAL
    sep #$20
:
    jsr sio_advance
    beq :+                  ; advance leaves Z set only at the payload end
    jmp sio_read_byte        ; never prefetch beyond the admitted extent
:
    rts
sio_complete:
    lda f:$0010
    and #$f7
    jsr sio_mask
    lda f:SD_PHASE
    cmp #3
    bne :+
    lda #4
    sta f:SD_PHASE
    lda #6
    jmp sio_arm
:
    cmp #8
    beq :+
    jmp sio_protocol
:
    lda #$13
    sta f:$0232
    sta f:$d20f
    lda #9
    sta f:SD_PHASE
    lda f:$0010
    ora #$20
    jmp sio_mask

sio_rx:
    lda f:$d20d
    sta f:SD_VALUE
    ; Sample shared SKSTAT once. POKEY reads run at the peripheral clock;
    ; a second read here delayed an already pending watchdog behind RX.
    lda f:$d20f
    and #$a0
    cmp #$a0
    beq sio_rx_clean
    and #$20
    bne :+
    lda #5
    jmp sio_fail
:
    lda #6
    jmp sio_fail
sio_rx_clean:
    lda f:SD_PHASE
    cmp #11
    bne :+
    jmp sio_data
:
    cmp #5
    beq sio_ack
    cmp #9
    beq sio_ack
    cmp #10
    beq sio_result
    cmp #12
    bne sio_protocol
    lda #1
    sta f:SD_SAFE
    lda f:SD_VALUE
    cmp f:SD_CHECKSUM
    bne :+
    jmp sio_terminal
:
    lda #4
    jmp sio_fail
sio_protocol:
    lda #7
    jmp sio_fail
sio_ack:
    lda f:SD_VALUE
    cmp #$4e
    bne :+
    lda #1
    sta f:SD_SAFE
    lda #2
    jmp sio_fail
:
    cmp #$41
    bne sio_protocol
    lda f:SD_PHASE
    cmp #9
    beq sio_to_result
    lda f:SD_DIRECTION
    cmp #2
    bne sio_to_result
    lda #6
    sta f:SD_PHASE
    lda #10
    jmp sio_arm
sio_to_result:
    lda #10
    sta f:SD_PHASE
    rts
sio_result:
    lda f:SD_VALUE
    cmp #$43
    beq :+
    cmp #$45
    bne sio_protocol
    lda #3
    sta f:SD_ERROR
:
    lda f:SD_DIRECTION
    cmp #1
    beq :+
    lda #1
    sta f:SD_SAFE
    jmp sio_terminal
:
    jsr sio_payload_cursor
    lda #11
    sta f:SD_PHASE
    rts
sio_data:
    jsr sio_write_byte
    lda f:SD_VALUE
    clc
    adc f:SD_CHECKSUM
    adc #0
    sta f:SD_CHECKSUM
    rep #$20
    lda f:SD_ACTUAL
    inc a
    sta f:SD_ACTUAL
    sep #$20
    jsr sio_advance
    bne :+
    lda #12
    sta f:SD_PHASE
:
    rts
sio_watchdog:
    rep #$20
    lda f:SD_WATCHDOGS
    inc a
    sta f:SD_WATCHDOGS
    lda f:SD_CLOCK
    inc a
    sta f:SD_CLOCK
    sec
    sbc f:SD_DEADLINE
    sep #$20
    bmi :+
    lda #1
    jmp sio_fail
:
    rts
sio_fail:
    ; First cause wins, including a device Error while draining its data.
    pha
    lda f:SD_ERROR
    bne :+
    pla
    sta f:SD_ERROR
    bra sio_terminal
:
    pla
sio_terminal:
    lda f:SD_PHASE
    cmp #SIO_TERMINAL
    beq sio_terminal_done
    lda f:SD_SAFE
    bne :+
    lda f:SD_STARTED
    beq :+
    lda #1
    sta f:SD_OFFLINE
:
    lda f:$0010
    and #($ff-SIO_OWNED_MASK)
    ora #$20
    jsr sio_mask
    lda #$13
    sta f:$0232
    sta f:$d20f
    lda f:$d303
    ora #$38
    sta f:$d303
    lda #0
    sta f:SD_CURSOR+2
    sta f:SD_DATA+2
    rep #$20
    lda #0
    sta f:SD_CURSOR
    sta f:SD_DATA
    lda f:SD_POSTS
    inc a
    sta f:SD_POSTS
    sep #$20
    lda #SIO_TERMINAL
    sta f:SD_PHASE
    jsr signal_post
sio_terminal_done:
    rts

; No caller pointers are used here, including while a terminal reply awaits
; collection. Keep private RX enabled until shutdown or the next valid arm.
sio_discard:
    lda f:$d20d
    lda #1
    sta f:SD_RECOVERY
    lda f:SD_OFFLINE
    bne :+
    lda #1
    sta f:SD_OFFLINE
    jsr signal_post
:
    rts

; ROM acknowledges each source before the callback. No task switch here.
sio_emulation:
    rep #$30
    pha
    phx
    phy
    phd
    phb
    and #$ff
    tax
    lda f:SD_EMULATIONS
    inc a
    sta f:SD_EMULATIONS
    sep #$20
    lda f:SD_PHASE
    beq sio_emulation_private
    cmp #SIO_TERMINAL
    beq sio_emulation_private
    cmp #15
    bne sio_emulation_active
sio_emulation_private:
    cpx #0
    bne :+
    jsr sio_discard
:
    jmp sio_emulation_done
sio_emulation_active:
    lda f:SD_CANCEL
    beq :+
    lda #$fe
    jsr sio_fail
    bra sio_emulation_done
:
    cpx #0
    bne :+
    jsr sio_rx
    bra sio_emulation_done
:
    cpx #1
    bne :+
    jsr sio_tx
    bra sio_emulation_done
:
    cpx #2
    bne :+
    jsr sio_complete
    bra sio_emulation_done
:
    cpx #3
    bne :+
    jsr sio_alarm
    bra sio_emulation_done
:
    jsr sio_watchdog
sio_emulation_done:
    rep #$30
    plb
    pld
    ply
    plx
    pla
    sep #$30
    rtl

; Only ROM's 16-bit vector bridges require bank zero (34 active bytes).
.segment "IRQ"
.a8
.i8
sio_emu_rx:
    lda #0
    bra sio_emu_common
sio_emu_tx:
    lda #1
    bra sio_emu_common
sio_emu_complete:
    lda #2
    bra sio_emu_common
sio_emu_alarm:
    lda #3
    bra sio_emu_common
sio_emu_watchdog:
    lda #4
sio_emu_common:
    clc
    xce
    php
    jsl sio_emulation
    plp
    xce
    pla
    rti
.segment "SIGNAL_CODE"
.a16
.i16

; Opt-in test entry: keep a live emulation-mode OS activation through three
; real fine-alarm callbacks, before command transmission starts. Its import is
; rejected outside I/O fixture builds. The ordinary driver never calls this.
.export sio_probe_emulation,sio_probe_emulation_end
sio_probe_emulation:
    signal_stack_check 19
    jsr sio_enter
    php
    sei
    pha
    phx
    phy
    phd
    phb
    tsc
    sta f:SIO_STATE+100
    lda #0
    tcd
    sep #$20
    pha
    plb
    lda #1
    sta f:OS_BUSY
    rep #$20
    lda #OS_STACK_TOP
    tcs
    jml sio_probe_os
sio_probe_os_return:
    rep #$30
    lda f:SIO_STATE+100
    tcs
    sep #$20
    lda #0
    sta f:OS_BUSY
    rep #$20
    plb
    pld
    ply
    plx
    pla
    plp
    lda #0
    jmp sio_leave
sio_probe_emulation_end:
.segment "FAULT"
.a8
.i8
sio_probe_os:
    sep #$30
    sec
    xce
    ldx #3
    cli
:
    wai
    dex
    bne :-
    sei
    clc
    xce
    rep #$30
    jml sio_probe_os_return
.segment "SIGNAL_CODE"
.a16
.i16

; Test-only imports; neither entry can be bound by an ordinary build.
.a16
.i16
.export sio_probe_stall,sio_probe_stall_end,sio_probe_stale,sio_probe_stale_end
sio_probe_stall:
    signal_stack_check 19
    jsr sio_enter
    php
    sei
    ldx #2000
:
    dex
    bne :-
    plp
    lda #0
    jmp sio_leave
sio_probe_stall_end:
sio_probe_stale:
    signal_stack_check 31
    jsr sio_enter
    lda #3
    jsl sio_emulation
    rep #$30
    lda #4
    jsl sio_emulation
    rep #$30
    lda #0
    jmp sio_leave
sio_probe_stale_end:
