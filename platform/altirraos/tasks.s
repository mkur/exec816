; Classic Task API. Public pointers never encode a private execution slot.
.export tasks_add_task, tasks_add_task_end, tasks_rem_task, tasks_rem_task_end
.export tasks_find_task, tasks_find_task_end, tasks_set_task_pri, tasks_set_task_pri_end
.export tasks_forbid, tasks_forbid_end, tasks_permit, tasks_permit_end
.export idle_start, general_task_start, general_finalizer_start, tasks_sleep, tasks_sleep_end
.export general_domains, general_domains_done
.segment "COOP_BOOT"
.a16
.i16
general_domains:
    .if INPUT_NATIVE
        ; Fault cleanup must be safe even before ConsoleInit has run.
        sep #$20
        lda #0
        sta f:CI_ACTIVE
        sta f:CI_BINDING+IN_BINDING_ACTIVE
        rep #$20
    .endif
    .if CONSOLE_NATIVE
        sep #$20
        lda #0
        sta f:CS_BASE+CON_SERVICE_STATE
        sta f:CS_PRESENTATION+CON_PRESENTATION_CLAIMED
        rep #$20
    .endif
    lda #$a5a5
    ldx #$061e
:
    sta E816_KERNEL_STACK_BASE-$10,x
    dex
    dex
    bpl :-
    lda #0
    ldx #$00fe
:
    sta E816_KERNEL_DP,x
    dex
    dex
    bpl :-
    ldx #T_ENTRY_COUNT-T_BASE-2
:
        sta f:T_BASE,x
    dex
    dex
    bpl :-
    lda #E816_KERNEL_OWNER
    sta E816_KERNEL_DP+A816_DP_OWNER_POINTER_OFFSET
    lda #E816_KERNEL_STACK_FLOOR
    sta E816_KERNEL_DP+A816_DP_STACK_FLOOR_OFFSET
    lda #E816_KERNEL_STACK_CEILING
    sta E816_KERNEL_DP+A816_DP_STACK_CEILING_OFFSET
    sep #$20
    lda #A816_DOMAIN_IRQ
    sta E816_KERNEL_DP+A816_DP_DOMAIN_KIND_OFFSET
    rep #$20
general_domains_done:
    jsl timer_device_init
    rts

.segment "STUBS"
.a16
.i16
tasks_add_task:
    tsc
    clc
    adc #4
    tax
        ldy #T_PROFILE_TAG
    lda #T_SERVICE_ADD_TASK
    cop E816_COP
    rtl
tasks_add_task_end:
.macro pointer_stub label, end_label, selector
label:
    lda 4,s
    tax
    sep #$20
    lda 6,s
    rep #$20
    and #$00ff
        ora #T_PROFILE_TAG
    tay
    lda #selector
    cop E816_COP
    rtl
end_label:
.endmacro
pointer_stub tasks_rem_task, tasks_rem_task_end, T_SERVICE_REM_TASK
pointer_stub tasks_find_task, tasks_find_task_end, T_SERVICE_FIND_TASK
tasks_set_task_pri:
    lda 4,s
    tax
    sep #$20
    lda 6,s
    rep #$20
    and #$00ff
        ora #T_PROFILE_TAG
    tay
    lda 6,s
    and #$ff00
    ora #T_SERVICE_SET_TASK_PRI
    cop E816_COP
    rtl
tasks_set_task_pri_end:
service_stub tasks_forbid, tasks_forbid_end, T_SERVICE_FORBID
service_stub tasks_permit, tasks_permit_end, T_SERVICE_PERMIT
tasks_sleep:
    lda 4,s
    tax
    lda #T_SERVICE_SLEEP
    cop E816_COP
    rtl
tasks_sleep_end:
idle_start:
        sei
        lda f:T_LIVE
        and #$00ff
        beq idle_poll
        lda f:T_WAKE_PENDING
        and #$00ff
        bne idle_poll
        ; WAI with I=1 wakes for a pending maskable IRQ without taking it.
        ; An arrival between the check and WAI therefore cannot be lost.
        wai
idle_poll:
        cli
    lda #E816_SERVICE_POLL
    cop E816_COP
    bra idle_start

general_task_start:
    .if PROBE_FLAGS <> $100
        jsr raw_context_probe
    .endif
    lda f:E816_CURRENT
    and #$00ff
    .repeat T_SHIFT
        asl a
    .endrepeat
    tax
    sep #$20
    lda f:T_BASE+T_TCB_ENTRY+2,x
    pha
    rep #$20
    lda f:T_BASE+T_TCB_ENTRY,x
    dec a
    pha
    rtl

general_finalizer_start:
    lda f:E816_CURRENT
    and #$00ff
    .repeat T_SHIFT
        asl a
    .endrepeat
    tax
    sep #$20
    lda f:T_BASE+T_TCB_FINALPC+2,x
    pha
    rep #$20
    lda f:T_BASE+T_TCB_FINALPC,x
    dec a
    pha
    rtl

    .segment "SIGNAL_CODE"
    .include "signal-gateway.inc"
    .include "signal-irq.s"
    .include "signal-atomic.s"
    .include "heap.s"
    .include "ports.s"
.include "ports-atomic.s"
.include "interrupt-work.s"
.include "timer-device.s"
    .include "fast-services.s"
    .include "memory.s"
    .include "io.s"
    .include "dos.s"
    .include "sio.s"
    .include "platform-timer.s"
    .include "display.s"
    .include "blitter.s"
    .if SIGNAL_IRQ_PROBE = 10
        .include "console-probe.s"
    .endif
    .if INPUT_NATIVE
        .include "input.s"
        .include "pointer.s"
    .endif
    .if CONSOLE_NATIVE
        .include "console.s"
    .endif
    .if HEAP_PROBE
        .include "heap-probe.s"
    .endif
    .segment "SIGNAL_CODE"
.export signal_bind, signal_bind_end, signal_unbind, signal_unbind_end, signal_drain, signal_drain_end
.a16
.i16
signal_bind:
    ; Canonicalize the native packet's alignment byte before admission.
    sep #$20
    lda #0
    sta 9,s
    rep #$20
    tsc
    clc
    adc #4
    tax
    ldy #T_PROFILE_TAG
    lda #T_SERVICE_BIND_PRODUCER
    cop E816_COP
    rtl
signal_bind_end:
.macro producer_signal_stub label, end_label, service
label:
    tsc
    clc
    adc #4
    tax
    ldy #T_PROFILE_TAG
    lda #service
    cop E816_COP
    rtl
end_label:
.endmacro
producer_signal_stub signal_unbind, signal_unbind_end, T_SERVICE_RELEASE_PRODUCER
producer_signal_stub signal_drain, signal_drain_end, T_SERVICE_DRAIN_PRODUCER

.if SIGNAL_PROBE <> 0
.export signal_nmi_checkpoint, signal_nmi_checkpoint_end
.a16
.i16
signal_nmi_checkpoint:
    ; Qualification only. Wait for a real VBI with the kernel guard asserted.
    lda f:E816_VBI_COUNT
    pha
:
    wai
    lda f:E816_VBI_COUNT
    cmp 1,s
    beq :-
    pla
    lda f:E816_PROBE0
    inc a
    sta f:E816_PROBE0
    rtl
signal_nmi_checkpoint_end:
.endif
