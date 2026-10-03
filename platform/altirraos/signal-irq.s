; Fixed producer wake publication and serial activation. Only bounded assembly
; executes in IRQ context; keyboard uses the same signal_post_binding path.
; All state except two bytes in the existing STATE arena lives in upper RAM.
; Publish a stable binding while inactive; Claim atomically activates it.
; Release quiesces serial sources before Task/context removal is permitted.
.ifndef INPUT_NATIVE
INPUT_NATIVE = 0
.endif
SIO_ACTIVE = T_SERIAL_BINDING+T_BINDING_ACTIVE
SIO_SAVED_MASK = T_SERIAL_STATE
SIO_SAVED_CRITIC = T_SERIAL_STATE+1
SIO_SAVED_SEROR = T_SERIAL_STATE+2
SIO_OS_BUSY = OS_BUSY
SIO_EMULATION_ENTRY = signal_emulation_entry
.include "serial-irq.inc"
.include "sio-state.inc"
.include "platform-timer.inc"

.macro signal_stack_check bytes
.local check_floor, overflow, stack_ok
    .if STACK_CHECKS
    tsc
    tax
    cmp A816_DP_STACK_CEILING_OFFSET
    bcc check_floor
    beq check_floor
    bra overflow
check_floor:
    sec
    sbc #bytes
    bcc overflow
    cmp A816_DP_STACK_FLOOR_OFFSET
    bcs stack_ok
overflow:
    lda #bytes
    jml stack_overflow
stack_ok:
    .endif
.endmacro

; Probe builds stop after every multi-byte mask/link/flag publication and wait
; for a real VBI. Never extend a live emulation/OS activation across a VBI.
; Save flags and A so the injected wait does not change transaction decisions.
.macro signal_irq_checkpoint wide
    .if SIGNAL_IRQ_PROBE = 1
        php
        rep #$20
        pha
        jsr signal_irq_wait_tick
        pla
        plp
        .if wide
            .a16
        .else
            .a8
        .endif
    .endif
.endmacro

.segment "SIGNAL_CODE"
.if SIGNAL_IRQ_PROBE = 1
; Share test-only waits so instrumented console images fit the same reservation.
; The extra two-byte JSR frame is included in observed probe stack usage.
.a16
signal_irq_wait_tick:
    tsc
    cmp #$0200
    bcc signal_irq_wait_done
    lda f:E816_VBI_COUNT
    pha
signal_irq_wait_loop:
    wai
    lda f:E816_VBI_COUNT
    cmp 1,s
    beq signal_irq_wait_loop
    pla
    lda f:E816_PROBE1
    inc a
    sta f:E816_PROBE1
signal_irq_wait_done:
    rts
.endif
.export signal_route, signal_claim, signal_claim_end, signal_release, signal_release_end
.export signal_post, signal_post_end, signal_post_return
.a8
.i16
signal_route:
    jsr blitter_irq_service
    php
    jsl signal_route_other
    bcs signal_route_owned
    lda f:$d20e
    eor #$ff
    and f:$0010
    bne signal_route_chain
    plp
    rtl
signal_route_chain:
    plp
    clc
    rtl
signal_route_owned:
    plp
    sec
    rtl
signal_route_other:
    lda f:SD_OWNED
    beq :+
    jml sio_route
:
    lda f:TM_USERS
    beq :+
    jsr timer_poll
    .if INPUT_NATIVE
        jsl input_route
    .endif
    lda f:$d20e
    eor #$ff
    and f:$0010
    ; A new timer edge may arrive during keyboard capture. Timer 1 is still
    ; ours: leave it latched for the next native entry, never chain the ROM
    ; while the fixed sampling owner retains its emulation vector.
    and #$fe
    bne signal_unowned
    sec
    rtl
:
    .if INPUT_NATIVE
        jml input_route
    .elseif SIGNAL_IRQ_PROBE = 10
        jml console_probe_route
    .endif
    .if SIGNAL_IRQ_PROBE >= 2 .and SIGNAL_IRQ_PROBE <= 3
        serial_irq_route signal_probe_burst, signal_unowned, signal_handled
    .elseif SIGNAL_IRQ_PROBE = 8
        serial_irq_route signal_pump, signal_unowned, signal_handled
    .else
        serial_irq_route signal_post, signal_unowned, signal_handled
    .endif
signal_unowned:
    clc
    rtl
signal_handled:
    sec
    rtl

; Native kernel imports: E=0, M=X=0, kernel transition guard asserted.
; Ownership changes mask IRQs locally and preserve the incoming I bit.
.a16
signal_claim:
    signal_stack_check 3
    php
    sei
    sep #$20
    jsr signal_claim_inner
    rep #$20
    lda #0
    bcs :+
    inc a
:
    plp
    rtl
signal_claim_end:
signal_release:
    signal_stack_check 3
signal_release_unchecked:
    php
    sei
    sep #$20
    lda f:SIO_ACTIVE
    beq signal_release_done
    ; Stop owned sources before removing the registration/vector.
    lda f:$0010
    and #($ff-SIO_IRQ_BITS)
    sta f:$0010
    sta f:$d20e
    jsr signal_release_inner
signal_release_done:
    rep #$20
    plp
    rtl
signal_release_end:
.export signal_release_shutdown
signal_release_shutdown:
    jsl blitter_release_unchecked
    jsl sio_shutdown_unchecked
    .if INPUT_NATIVE
        jsl pointer_release_unchecked
    .endif
    rep #$20
    ; finish may arrive with M=1 or an invalid compiler domain after a fault.
    ; It owns shutdown, has masked IRQ/NMI, and supplies the small return frame.
    rep #$30
    jmp signal_release_unchecked
.a8
serial_ownership_routines signal_claim_inner, signal_release_inner

; Full native context is already saved by the adapter. Preserve D and stack;
; A/X/Y may change. Scratch consists of 12 activation-local bytes below S.
; [1] Task, [5] node, [9] predecessor. Context is a generated-bank X offset.
; NMI may record ticks here, but cannot enter policy from an IRQ activation.
signal_post:
    ldx #T_SERIAL_BINDING-T_BASE
signal_post_binding:
    rep #$20
    phd
    tsc
    sec
    sbc #12
    tcs
    tcd
    .if SIGNAL_IRQ_PROBE = 9
        ; A rejected IRQ-context COP must leave the interrupted policy's DP
        ; scratch intact. Save live values, plant sentinels, and restore them
        ; even on failure. The enclosing native IRQ preserves all registers.
        lda f:E816_SWITCHING
        and #$00ff
        beq cop_scratch_done
        lda f:E816_KERNEL_DP+A816_DP_SCRATCH_OFFSET
        pha
        lda f:E816_KERNEL_DP+A816_DP_SCRATCH_OFFSET+2
        pha
        lda #$a55a
        sta f:E816_KERNEL_DP+A816_DP_SCRATCH_OFFSET
        lda #$3cc3
        sta f:E816_KERNEL_DP+A816_DP_SCRATCH_OFFSET+2
        lda #E816_SERVICE_POLL
        cop E816_COP
        cmp #E816_ERROR_CONTEXT
        bne cop_scratch_failed
        lda f:E816_KERNEL_DP+A816_DP_SCRATCH_OFFSET
        cmp #$a55a
        bne cop_scratch_failed
        lda f:E816_KERNEL_DP+A816_DP_SCRATCH_OFFSET+2
        cmp #$3cc3
        bne cop_scratch_failed
        lda f:E816_SWITCHING
        and #$00ff
        cmp #1
        bne cop_scratch_failed
        bra cop_scratch_result
cop_scratch_failed:
        lda #$ffff
cop_scratch_result:
        sta f:E816_PROBE1
        pla
        sta f:E816_KERNEL_DP+A816_DP_SCRATCH_OFFSET+2
        pla
        sta f:E816_KERNEL_DP+A816_DP_SCRATCH_OFFSET
cop_scratch_done:
    .endif
    lda f:T_BASE+T_BINDING_TASK,x
    sta 1
    sep #$20
    lda f:T_BASE+T_BINDING_TASK+2,x
    sta 3
    rep #$20
    lda f:T_BASE+T_BINDING_MASK,x
    ldy #T_TASK_TC_SIGRECVD
    ora [1],y
    sta [1],y
    signal_irq_checkpoint 1
    lda f:T_BASE+T_BINDING_MASK+2,x
    iny
    iny
    ora [1],y
    sta [1],y
    signal_irq_checkpoint 1
    lda f:T_BASE+T_BINDING_CONTEXT,x
    sec
    sbc #.loword(T_BASE)
    tax
    sep #$20
    lda f:T_BASE+T_TCB_STATE,x
    cmp #T_STATE_SIGNAL_WAIT
    beq :+
    brl signal_post_done
:
    lda f:T_BASE+T_TCB_WAITREASON,x
    cmp #T_WAIT_SIGNAL
    beq :+
    brl signal_post_done
:
    lda f:T_BASE+T_TCB_QUEUED,x
    beq :+
    brl signal_post_done
:
    rep #$20
    ldy #T_TASK_TC_SIGRECVD
    lda [1],y
    ldy #T_TASK_TC_SIGWAIT
    and [1],y
    bne signal_enqueue
    ldy #T_TASK_TC_SIGRECVD+2
    lda [1],y
    ldy #T_TASK_TC_SIGWAIT+2
    and [1],y
    bne :+
    brl signal_post_done
:
signal_enqueue:
    ; Node is in this context; the old predecessor may be the far header.
    txa
    clc
    adc #.loword(T_BASE+T_TCB_WAKENODE)
    sta 5
    lda f:T_WAKE+6
    sta 9
    lda #.loword(T_WAKE+3)
    sta f:T_BASE+T_TCB_WAKENODE,x
    signal_irq_checkpoint 1
    lda 9
    sta f:T_BASE+T_TCB_WAKENODE+3,x
    signal_irq_checkpoint 1
    sep #$20
    lda #^T_BASE
    sta 7
    lda #^(T_WAKE+3)
    sta f:T_BASE+T_TCB_WAKENODE+2,x
    signal_irq_checkpoint 0
    lda f:T_WAKE+8
    sta 11
    sta f:T_BASE+T_TCB_WAKENODE+5,x
    signal_irq_checkpoint 0
    rep #$20
    lda 5
    sta [9]
    signal_irq_checkpoint 1
    sta f:T_WAKE+6
    signal_irq_checkpoint 1
    sep #$20
    lda 7
    ldy #2
    sta [9],y
    signal_irq_checkpoint 0
    sta f:T_WAKE+8
    signal_irq_checkpoint 0
    lda #1
    sta f:T_BASE+T_TCB_QUEUED,x
    signal_irq_checkpoint 0
    sta f:T_WAKE_PENDING
    signal_irq_checkpoint 0
signal_post_done:
    rep #$20
    tsc
    clc
    adc #12
    tcs
    pld
    sep #$20
signal_post_return:
    rts
signal_post_end:

; Native post callable by the tiny emulation bridge. There is a live OS
; activation below this frame, so this path can never schedule.
signal_emulation_post:
    .if SIGNAL_IRQ_PROBE = 8
        jsr signal_pump
    .else
        jsr signal_post
    .endif
    rtl

; ROM serial dispatcher saved A and acknowledged the source. Stay on its OS
; stack, preserving the hidden B accumulator as well as X/Y/D/DBR and flags.
.segment "IRQ"
.export signal_emulation_entry
.a8
.i8
signal_emulation_entry:
    php
    clc
    xce
    rep #$30
    pha
    phx
    phy
    phd
    phb
    lda f:IRQ_COUNT
    inc a
    sta f:IRQ_COUNT
    sep #$20
    jsl signal_emulation_post
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
.export signal_irq_window, signal_irq_window_end
.a16
.i16
signal_irq_window:
    ; Kernel S/D remain active, SWITCHING remains asserted. IRQ/NMI can only
    ; post/record and return; they cannot borrow policy scratch or switch tasks.
    signal_stack_check 1+4*(SIGNAL_IRQ_PROBE = 3)
    php
    sei
    lda f:T_IRQ_ALLOW
    and #$00ff
    beq :+
    .if SIGNAL_IRQ_PROBE = 3
        jsr signal_probe_window
    .endif
    cli
    nop
    nop
:
    plp
    rtl
signal_irq_window_end:

; Diagnostic device: all public Task/context bindings were admitted before
; arming. One real source fans out to this fixed registered set, in slot order.
; It exists only in explicit probe builds; production posts one known binding.
.if SIGNAL_IRQ_PROBE >= 2 .and SIGNAL_IRQ_PROBE <= 3
.segment "SIGNAL_CODE"
.a8
.i16
signal_probe_burst:
    lda f:E816_PROBE1
    beq :+
    jmp signal_probe_again
:
    lda f:$0010
    and #$ef
    sta f:$0010
    sta f:$d20e
    .repeat T_CAPACITY, slot
        rep #$20
        lda f:T_BASE+slot*T_SIZE+T_TCB_ITEM
        sta f:T_SERIAL_BINDING+T_BINDING_TASK
        lda #.loword(T_BASE+slot*T_SIZE)
        sta f:T_SERIAL_BINDING+T_BINDING_CONTEXT
        sep #$20
        lda f:T_BASE+slot*T_SIZE+T_TCB_ITEM+2
        sta f:T_SERIAL_BINDING+T_BINDING_TASK+2
        lda #^T_BASE
        sta f:T_SERIAL_BINDING+T_BINDING_CONTEXT+2
        jsr signal_post
        ; Snapshot each actual queued flag, not just the requested count.
        lda f:T_BASE+slot*T_SIZE+T_TCB_QUEUED
        sta f:T_SERIAL_STATE+5+slot
    .endrepeat
    ; Restore the producer's root binding before any policy can run/reuse it.
    rep #$20
    lda f:T_BASE+T_TCB_ITEM
    sta f:T_SERIAL_BINDING+T_BINDING_TASK
    lda #.loword(T_BASE)
    sta f:T_SERIAL_BINDING+T_BINDING_CONTEXT
    sep #$20
    lda f:T_BASE+T_TCB_ITEM+2
    sta f:T_SERIAL_BINDING+T_BINDING_TASK+2
    lda #1
    sta f:E816_PROBE1
    rts
signal_probe_again:
    lda f:$0010
    and #$ef
    sta f:$0010
    sta f:$d20e
    jmp signal_post
.endif

.if SIGNAL_IRQ_PROBE = 3
.a16
.i16
signal_probe_window:
    lda f:E816_PROBE1
    and #$00ff
    beq probe_window_done
    lda f:T_BASE+T_TCB_QUEUED
    and #$00ff
    bne probe_window_done
    lda f:E816_PROBE0
    bne probe_window_done
    inc a
    sta f:E816_PROBE0
    ; Keep the original stable target and add an unrelated pending signal.
    lda #2
    sta f:T_SERIAL_BINDING+T_BINDING_MASK
    lda #0
    sta f:T_SERIAL_BINDING+T_BINDING_MASK+2
    lda f:IRQ_COUNT
    pha
    sep #$20
    lda f:$0010
    ora #$10
    sta f:$0010
    sta f:$d20e
    lda #$a5
    sta f:$d20d
probe_asserted:
    lda f:$d20e
    and #$10
    bne probe_asserted
    rep #$20
    lda f:IRQ_COUNT
    cmp 1,s
    bne :+
    lda #2
    sta f:E816_PROBE0
:
    pla
probe_window_done:
    rts
.endif

; A device transfer with no ready peer and no timed sleeper needs no tick-only
; policy entry. Clock ticks remain recorded. Check only after all transition,
; OS/IRQ and frame guards: no partial ready-list state can be inspected here.
.segment "SIGNAL_CODE"
.export signal_tick_needed, signal_pump_start, signal_pump_start_end
.a16
.i16
signal_tick_needed:
    lda f:T_SERIAL_BINDING+T_BINDING_ACTIVE
    and #$00ff
    beq tick_needed
    lda f:T_WAKE_PENDING
    and #$00ff
    bne tick_needed
    lda f:T_SLEEPERS
    and #$00ff
    bne tick_needed
    lda f:T_READY
    cmp #.loword(T_READY+3)
    bne tick_needed
    lda f:T_READY+2
    and #$00ff
    cmp #^(T_READY+3)
    bne tick_needed
    clc
    rtl
tick_needed:
    sec
    rtl

; Diagnostic buffered transmitter. The fixture calls Start only after the
; bound worker has blocked. The stable producer posts once at block completion.
; Production builds contain no byte pump and reject its diagnostic entry.
signal_pump_start:
    .if SIGNAL_IRQ_PROBE = 8
        php
        sei
        sep #$20
        lda #0
        sta f:$d20f
        sta f:$d204
        sta f:$d205
        sta f:$d206
        sta f:$d207
        lda #$28
        sta f:$d208
        lda #$23
        sta f:$0232
        sta f:$d20f
        sta f:$d20a
        sta f:$d209
        lda f:$0010
        ora #$10
        sta f:$0010
        sta f:$d20e
        rep #$20
        lda #1
        sta f:E816_PROBE0
        sep #$20
        lda #0
        sta f:$d20d
        rep #$20
        plp
        rtl
    .else
        lda #FAULT_CONTEXT
        jml finish
    .endif
signal_pump_start_end:
.if SIGNAL_IRQ_PROBE = 8
.a8
.i16
signal_pump:
    rep #$20
    lda f:E816_PROBE0
    cmp #PUMP_COUNT
    beq pump_complete
    sep #$20
    sta f:$d20d
    rep #$20
    lda f:E816_PROBE0
    inc a
    sta f:E816_PROBE0
    sep #$20
    rts
pump_complete:
    sep #$20
    jmp signal_post
.endif

.segment "SIGNAL_CODE"
.export signal_context, signal_context_end, signal_context_woke
.a16
.i16
signal_context:
.if SIGNAL_IRQ_PROBE >= 4 .and SIGNAL_IRQ_PROBE <= 7
    php
    phb
    phd
    tsc
    sta f:E816_PROBE0+10
    lda #$beef
    sta $20
    sep #$20
    lda f:$0010
    ora #$10
    sta f:$0010
    sta f:$d20e
    lda #$5a
    sta f:$d20d
    lda #$12
    pha
    plb
    lda #($c9+(SIGNAL_IRQ_PROBE-4)*$10)
    pha
    rep #$30
    lda #$abcd
    ldx #$1234
    ldy #$5678
    plp
    wai
signal_context_woke:
    php
    save_full
    cld
    pea 0
    plb
    plb
    tsc
    tax
    .repeat 5,offset
        lda f:1+offset*2,x
        sta f:E816_PROBE0+offset*2
    .endrepeat
    txa
    clc
    adc #10
    sta f:E816_PROBE0+12
    tcs
    phk
    sep #$20
    pla
    sta f:E816_PROBE0+14
    rep #$20
    lda $20
    sta f:E816_PROBE0+16
    pld
    plb
    plp
    rtl
.else
signal_context_woke:
    lda #FAULT_CONTEXT
    jml finish
.endif
signal_context_end:
