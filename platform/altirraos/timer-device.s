; VBI clock and bounded timer expiry. Driver policy and Task serialization live
; in TIMERDRIVER; this code never enters compiled policy from an interrupt.
.segment "NATIVE_WORK"
.a16
.i16
.export timer_device_init
.export timer_device_enter, timer_device_enter_end
.export timer_device_leave, timer_device_leave_end
.export timer_device_enable, timer_device_enable_end
.export timer_device_snapshot, timer_device_snapshot_end
.export native_vbi_clock, native_timer_work

timer_device_init:
    lda f:$0062                  ; pinned ROM PALNTS: zero NTSC, one PAL
    and #$ff
    beq :+
    lda #50
    bra timer_rate_ready
:
    lda #60
timer_rate_ready:
    sta f:TI_RATE
    lda #$ff
    sta f:TI_HEAD
    lda #$6974
    sta f:TI_NAME
    lda #$656d
    sta f:TI_NAME+2
    lda #$2e72
    sta f:TI_NAME+4
    lda #$6564
    sta f:TI_NAME+6
    lda #$6976
    sta f:TI_NAME+8
    lda #$6563
    sta f:TI_NAME+10
    rtl

timer_device_enter:
    php
    sei
    sep #$20
    lda f:TI_EDIT
    jne port_native_fault
    lda #1
    sta f:TI_EDIT
    sta f:NI_BLOCKED+NI_SOURCE_TIMER
    plp
    rtl
timer_device_enter_end:

.a16
timer_device_leave:
    php
    sei
    sep #$20
    ; The first enqueue can become due before ARMED lets raw VBI hint it.
    ; Publish that hint before releasing the source; never erase a VBI hint.
    lda f:TI_ARMED
    beq :+
    lda #1
    sta f:NI_PENDING+NI_SOURCE_TIMER
:
    lda #0
    sta f:TI_EDIT
    sta f:NI_BLOCKED+NI_SOURCE_TIMER
    ; Every resident callback returns to IOCORE's Permit. Its native return
    ; services pending work even when an outer Forbid still excludes switching.
    plp
    rtl
timer_device_leave_end:

.a16
timer_device_enable:
    php
    sei
    lda 5,s
    and #$ff
    sep #$20
    sta f:NI_ENABLED+NI_SOURCE_TIMER
    lda #0
    sta f:NI_PENDING+NI_SOURCE_TIMER
    plp
    rtl
timer_device_enable_end:

; Snapshot(destination *) writes high32, low32 and rate32. Forbid excludes a
; Task switch while the versioned twelve-byte copy is in flight. NMI remains
; enabled; it cannot wait on an interrupted reader. Two copies bound retries.
.a16
timer_device_snapshot:
    signal_stack_check 13
    phd
    tsc
    sec
    sbc #6
    tcs
    tcd
    lda 12
    sta 1
    lda 14
    and #$ff
    sta 3
    jsr timer_snapshot_copy
    tay
    tsc
    clc
    adc #6
    tcs
    pld
    tya
    rtl
timer_device_snapshot_end:

; D owns destination pointer 1..3 and version/retry bytes 4..5.
timer_snapshot_copy:
    sep #$20
    lda #2
    sta 5
timer_snapshot_retry:
    lda f:TI_VERSION
    sta 4
    and #1
    bne timer_snapshot_again
    rep #$20
    ldy #0
    lda f:TI_CLOCK_HI
    sta [1],y
    iny
    iny
    lda f:TI_CLOCK_HI+2
    sta [1],y
    iny
    iny
    lda f:TI_CLOCK_LO
    sta [1],y
    iny
    iny
    lda f:TI_CLOCK_LO+2
    sta [1],y
    iny
    iny
    lda f:TI_RATE
    sta [1],y
    iny
    iny
    lda #0
    sta [1],y
    sep #$20
    lda f:TI_VERSION
    cmp 4
    beq timer_snapshot_read
timer_snapshot_again:
    dec 5
    bne timer_snapshot_retry
    lda #TI_TIMERERR_CLOCK
    bra timer_snapshot_result
timer_snapshot_read:
    lda f:TI_FAULT
    beq timer_snapshot_result
    lda #TI_TIMERERR_CLOCK
timer_snapshot_result:
    rep #$20
    and #$ff
    rts

; Raw VBI: E=1, M=X=1, D=DBR=0, preserved X/Y and hidden B. Only the
; versioned clock and a coalescing source hint are touched; no queue accesses.
.a8
.i8
native_vbi_clock:
    lda f:TI_FAULT
    jne timer_vbi_notify
    lda f:TI_VERSION
    inc a
    sta f:TI_VERSION
    clc
    .repeat 8, byte
        .if byte < 4
            lda f:TI_CLOCK_LO+byte
        .else
            lda f:TI_CLOCK_HI+byte-4
        .endif
        .if byte = 0
            adc #1
        .else
            adc #0
        .endif
        .if byte < 4
            sta f:TI_CLOCK_LO+byte
        .else
            sta f:TI_CLOCK_HI+byte-4
        .endif
        jcc timer_clock_written
    .endrepeat
    ; Overflow is a fault, never an observable wrap to zero.
    lda #$ff
    .repeat 8, byte
        sta f:TI_CLOCK_HI+byte
    .endrepeat
    lda #1
    sta f:TI_FAULT
timer_clock_written:
    lda f:TI_VERSION
    inc a
    sta f:TI_VERSION
timer_vbi_notify:
    lda f:TI_ARMED
    beq timer_vbi_done
    lda f:NI_ENABLED+NI_SOURCE_TIMER
    beq timer_vbi_done
    lda #1
    sta f:NI_PENDING+NI_SOURCE_TIMER
timer_vbi_done:
    rtl

; At most four terminal commits. NI_ACTIVE excludes recursive continuations;
; Task editors publish TI_EDIT before touching the deadline queue. Each reply
; releases all driver references before transfer, then gives IRQs a turn.
.a8
.i16
native_timer_work:
    lda f:TI_EDIT
    beq :+
    lda #2
    rtl
:
    rep #$20
    phd
    tsc
    sec
    sbc #26
    tcs
    tcd
    ; Snapshot scratch 1..5, coherent high/low/rate 6..17, budget 18,
    ; terminal error 19, request 20..22, slot offset 23..24, command 25.
    clc
    adc #6
    sta 1
    stz 3
    jsr timer_snapshot_copy
    sep #$20
    sta 19
    lda #TI_COMPLETION_BUDGET
    sta 18
timer_expiry_next:
    lda f:TI_HEAD
    cmp #$ff
    jeq timer_expiry_done
    rep #$20
    and #$ff
    asl a
    asl a
    asl a
    asl a
    tax
    stx 23
    lda 19
    and #$ff
    bne timer_expiry_due
    lda f:TI_PENDING+6,x
    cmp 8
    bcc timer_expiry_due
    jne timer_expiry_done
    lda f:TI_PENDING+4,x
    cmp 6
    bcc timer_expiry_due
    jne timer_expiry_done
    lda f:TI_PENDING+10,x
    cmp 12
    bcc timer_expiry_due
    jne timer_expiry_done
    lda f:TI_PENDING+8,x
    cmp 10
    bcc timer_expiry_due
    jne timer_expiry_done
timer_expiry_due:
    lda f:TI_PENDING,x
    sta 20
    sep #$20
    lda f:TI_PENDING+2,x
    sta 22
    lda f:TI_PENDING+13,x
    sta 25
    lda f:TI_PENDING+3,x
    sta f:TI_HEAD
    lda #0
    sta f:TI_PENDING+14,x
    sta f:TI_PENDING,x
    sta f:TI_PENDING+1,x
    sta f:TI_PENDING+2,x
    lda f:TI_COUNT
    dec a
    sta f:TI_COUNT
    bne :+
    sta f:TI_ARMED
:
    lda 19
    ldy #25
    sta [20],y
    bne timer_expiry_reply
    lda 25
    cmp #TI_TR_ADDREQUEST
    bne timer_expiry_reply
    rep #$20
    lda #0
    ldy #26
    sta [20],y
    iny
    iny
    sta [20],y
    iny
    iny
    sta [20],y
    iny
    iny
    sta [20],y
timer_expiry_reply:
    rep #$20
    lda 22
    and #$ff
    tax
    lda 20
    ; All driver references are detached. Split preparation from the bounded
    ; public reply transaction; NI_ACTIVE still excludes recursive NMI work.
    cli
    nop
    sei
    jsl exec_reply_msg_native
    cli
    nop
    sei
    sep #$20
    dec 18
    jne timer_expiry_next
    lda f:TI_ARMED
    bra timer_expiry_return
timer_expiry_done:
    sep #$20
    lda #0
timer_expiry_return:
    rep #$20
    and #$ff
    tay
    tsc
    clc
    adc #26
    tcs
    pld
    tya
    sep #$20
    rtl
