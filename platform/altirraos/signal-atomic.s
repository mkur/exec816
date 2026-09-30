; Native atomic mechanisms for the interruptible Task policy. The policy
; validates Task/context ownership and owns the ready list. IRQ code touches
; only received masks, published wait state and the separate wake MinList.
; Every operation preserves the incoming I bit; NMI sees SWITCHING throughout.
; Twelve stack-local bytes plus saved D/P: no shared DP scratch or new storage.
.segment "SIGNAL_CODE"
.a16
.i16

ATOMIC_LOCAL = 12
ATOMIC_ARG = ATOMIC_LOCAL+6       ; entry +4, after saved D and local storage
ATOMIC_PEAK = ATOMIC_LOCAL+3+8*(SIGNAL_PROBE <> 0)

.macro atomic_enter
.local check_floor, overflow, stack_ok
    ; Assembly imports own their reservation check. IRQ/NMI headroom is the
    ; existing domain reserve below the compiler's normal stack floor.
    .if STACK_CHECKS
    tsc
    tax
    cmp A816_DP_STACK_CEILING_OFFSET
    bcc check_floor
    beq check_floor
    bra overflow
check_floor:
    sec
    sbc #ATOMIC_PEAK
    bcc overflow
    cmp A816_DP_STACK_FLOOR_OFFSET
    bcs stack_ok
overflow:
    lda #ATOMIC_PEAK
    jml stack_overflow
stack_ok:
    .endif
    phd
    tsc
    sec
    sbc #ATOMIC_LOCAL
    tcs
    tcd
.endmacro

.macro atomic_task_argument
    lda ATOMIC_ARG
    sta 1
    sep #$20
    lda ATOMIC_ARG+2
    sta 3
    rep #$20
.endmacro

.macro atomic_context_argument
    lda ATOMIC_ARG
    sec
    sbc #.loword(T_BASE)
    tax
.endmacro

.macro atomic_context_task
    lda f:T_BASE+T_TCB_ITEM,x
    sta 1
    sep #$20
    lda f:T_BASE+T_TCB_ITEM+2,x
    sta 3
    rep #$20
.endmacro

; Results in local words 5/7. Unmask before cleanup: IRQ saves/restores the
; entire native context, including this activation-local D and result registers.
.macro atomic_return
    plp
    ldy 5
    ldx 7
    tsc
    clc
    adc #ATOMIC_LOCAL
    tcs
    pld
    tya
    rtl
.endmacro

.macro atomic_checkpoint number
    .if SIGNAL_PROBE = number
        php
        pha
        jsl signal_nmi_checkpoint
        pla
        plp
    .endif
.endmacro

.macro atomic_consume
    ldy #T_TASK_TC_SIGRECVD
    lda [1],y
    eor 5                       ; result is a subset of the received mask
    sta [1],y
    iny
    iny
    lda [1],y
    eor 7
    sta [1],y
.endmacro

; SignalChange(Task *, bits32, mask32) -> old32. Also supplies atomic snapshots,
; bit posting and allocation's pending-bit clear. The native argument packet
; aligns each LONGCARD to two bytes: pointer 0, bits 4, mask 8 (13 outgoing).
.export signal_change, signal_change_end
signal_change:
    atomic_enter
    atomic_task_argument
    php
    sei
    atomic_checkpoint 6
    ldy #T_TASK_TC_SIGRECVD
    lda [1],y
    sta 5
    eor ATOMIC_ARG+4
    and ATOMIC_ARG+8
    eor 5
    sta [1],y
    atomic_checkpoint 1
    atomic_checkpoint 6
    iny
    iny
    lda [1],y
    sta 7
    eor ATOMIC_ARG+6
    and ATOMIC_ARG+10
    eor 7
    sta [1],y
    atomic_return
signal_change_end:

; WaitBegin(context *, mask32) -> consumed32, or zero with the wait published.
; Mask test/consume and SIGNAL_WAIT publication are one atomic transaction.
.export signal_wait_begin, signal_wait_begin_end
signal_wait_begin:
    atomic_enter
    atomic_context_argument
    atomic_context_task
    php
    sei
    ldy #T_TASK_TC_SIGRECVD
    lda [1],y
    and ATOMIC_ARG+4
    sta 5
    iny
    iny
    lda [1],y
    and ATOMIC_ARG+6
    sta 7
    ora 5
    bne wait_begin_consume
    ldy #T_TASK_TC_SIGWAIT
    lda ATOMIC_ARG+4
    sta [1],y
    atomic_checkpoint 2
    iny
    iny
    lda ATOMIC_ARG+6
    sta [1],y
    sep #$20
    lda #T_WAIT_SIGNAL
    sta f:T_BASE+T_TCB_WAITREASON,x
    lda #0
    sta f:T_BASE+T_TCB_PENDING,x
    lda #T_STATE_SIGNAL_WAIT
    sta f:T_BASE+T_TCB_STATE,x
    ldy #T_TASK_TC_STATE
    lda #T_TS_WAIT
    sta [1],y
    rep #$20
    atomic_checkpoint 3
    bra wait_begin_return
wait_begin_consume:
    atomic_consume
    atomic_checkpoint 5
wait_begin_return:
    atomic_return
signal_wait_begin_end:

; WaitComplete(context *) -> consumed32. The context is selected from READY;
; posts after this transaction stay pending for the next Wait.
.export signal_wait_complete, signal_wait_complete_end
signal_wait_complete:
    atomic_enter
    atomic_context_argument
    atomic_context_task
    php
    sei
    ldy #T_TASK_TC_SIGRECVD
    lda [1],y
    ldy #T_TASK_TC_SIGWAIT
    and [1],y
    sta 5
    ldy #T_TASK_TC_SIGRECVD+2
    lda [1],y
    ldy #T_TASK_TC_SIGWAIT+2
    and [1],y
    sta 7
    atomic_consume
    lda #0
    ldy #T_TASK_TC_SIGWAIT
    sta [1],y
    iny
    iny
    sta [1],y
    atomic_checkpoint 4
    sep #$20
    sta f:T_BASE+T_TCB_WAITREASON,x
    rep #$20
    atomic_return
signal_wait_complete_end:

; WakeMatch(context *) -> bool. Publish private READY before clearing a drain
; claim. A post while claimed still ORs tc_SigRecvd, so this final atomic check
; sees it. A post after READY cannot enqueue the context again. Public state and
; scheduler links are completed by the guarded, IRQ-permitting Action policy.
.export signal_wake_match, signal_wake_match_end
signal_wake_match:
    atomic_enter
    atomic_context_argument
    atomic_context_task
    lda #0
    sta 5
    sta 7
    php
    sei
    sep #$20
    lda f:T_BASE+T_TCB_STATE,x
    cmp #T_STATE_SIGNAL_WAIT
    bne wake_match_done
    lda f:T_BASE+T_TCB_WAITREASON,x
    cmp #T_WAIT_SIGNAL
    bne wake_match_done
    rep #$20
    ldy #T_TASK_TC_SIGRECVD
    lda [1],y
    ldy #T_TASK_TC_SIGWAIT
    and [1],y
    bne wake_match_ready
    ldy #T_TASK_TC_SIGRECVD+2
    lda [1],y
    ldy #T_TASK_TC_SIGWAIT+2
    and [1],y
    beq wake_match_done
wake_match_ready:
    inc 5
    sep #$20
    lda #T_STATE_READY
    sta f:T_BASE+T_TCB_STATE,x
wake_match_done:
    sep #$20
    lda f:T_BASE+T_TCB_QUEUED,x
    cmp #T_WAKE_CLAIMED
    bne :+
    lda #0
    sta f:T_BASE+T_TCB_QUEUED,x
:
    rep #$20
    atomic_return
signal_wake_match_end:

.macro wake_clear_links
    lda #0
    sta f:T_BASE+T_TCB_WAKENODE,x
    sta f:T_BASE+T_TCB_WAKENODE+2,x
    sta f:T_BASE+T_TCB_WAKENODE+4,x
.endmacro

.macro wake_update_pending
.local nonempty, done
    lda f:T_WAKE
    cmp #.loword(T_WAKE+3)
    bne nonempty
    sep #$20
    lda #0
    bra done
nonempty:
    sep #$20
    lda #1
done:
    sta f:T_WAKE_PENDING
    rep #$20
.endmacro

; TakeWake() -> claimed context *, zero when empty, $FFFFFF on a corrupt head.
; Only the kernel removes heads, while an IRQ may append. Head validation and
; all link writes are atomic. The CLAIMED flag prevents re-enqueue while the
; Action policy validates reciprocal Task ownership and prepares readiness.
.export signal_wake_take, signal_wake_take_end
signal_wake_take:
    atomic_enter
    lda #0
    sta 5
    sta 7
    php
    sei
    lda f:T_WAKE+2
    and #$00ff
    cmp #^T_BASE
    beq :+
    brl wake_take_fault
:
    lda f:T_WAKE
    cmp #.loword(T_WAKE+3)
    bne :+
    brl wake_take_empty
:
    sec
    sbc #.loword(T_BASE+T_TCB_WAKENODE)
    bcs :+
    brl wake_take_fault
:
    cmp #T_PUBLIC_CONTEXT_BYTES
    bcc :+
    brl wake_take_fault
:
    tax
    and #T_SIZE-1
    beq :+
    brl wake_take_fault
:
    lda f:T_BASE+T_TCB_QUEUED,x
    and #$00ff
    cmp #T_WAKE_LINKED
    beq :+
    brl wake_take_fault
:
    txa
    clc
    adc #.loword(T_BASE)
    sta 5
    lda #^T_BASE
    sta 7
    lda f:T_BASE+T_TCB_WAKENODE,x
    sta 1
    sta f:T_WAKE
    sep #$20
    lda f:T_BASE+T_TCB_WAKENODE+2,x
    sta 3
    sta f:T_WAKE+2
    rep #$20
    lda #.loword(T_WAKE)
    ldy #3
    sta [1],y
    sep #$20
    lda #^T_WAKE
    ldy #5
    sta [1],y
    lda #T_WAKE_CLAIMED
    sta f:T_BASE+T_TCB_QUEUED,x
    rep #$20
    wake_clear_links
    wake_update_pending
    bra wake_take_return
wake_take_empty:
    sep #$20
    lda #0
    sta f:T_WAKE_PENDING
    rep #$20
    bra wake_take_return
wake_take_fault:
    lda #$ffff
    sta 5
    lda #$00ff
    sta 7
wake_take_return:
    atomic_return
signal_wake_take_end:

; CancelWakeNode(context *). The caller has either published non-waiting state
; or quiesced every producer for a removed task. IRQ tail appends cannot race
; this known-node unlink. READY uses the separate public tc_Node list.
.export signal_wake_cancel, signal_wake_cancel_end
signal_wake_cancel:
    atomic_enter
    atomic_context_argument
    php
    sei
    lda f:T_BASE+T_TCB_QUEUED,x
    and #$00ff
    beq wake_cancel_return
    cmp #T_WAKE_LINKED
    bne wake_cancel_clear
    lda f:T_BASE+T_TCB_WAKENODE,x
    sta 1
    lda f:T_BASE+T_TCB_WAKENODE+3,x
    sta 5
    sep #$20
    lda f:T_BASE+T_TCB_WAKENODE+2,x
    sta 3
    lda f:T_BASE+T_TCB_WAKENODE+5,x
    sta 7
    rep #$20
    lda 1
    sta [5]
    lda 5
    ldy #3
    sta [1],y
    sep #$20
    lda 3
    ldy #2
    sta [5],y
    lda 7
    ldy #5
    sta [1],y
    rep #$20
wake_cancel_clear:
    wake_clear_links
    sep #$20
    sta f:T_BASE+T_TCB_QUEUED,x
    rep #$20
    wake_update_pending
wake_cancel_return:
    atomic_return
signal_wake_cancel_end:

; Qualification only: post a second, distinct bit while an unlinked head is
; CLAIMED. It must remain claimed and must not schedule out of this activation.
.if SIGNAL_IRQ_PROBE = 9
.export signal_claim_checkpoint, signal_claim_checkpoint_end
signal_claim_checkpoint:
    atomic_enter
    atomic_context_argument
    php
    sei
    lda f:E816_PROBE0
    beq :+
    brl claim_checkpoint_return
:
    lda #1
    sta f:E816_PROBE0
    lda f:T_BASE+T_TCB_QUEUED,x
    and #$00ff
    cmp #T_WAKE_CLAIMED
    beq :+
    brl claim_checkpoint_return
:
    lda #3
    sta f:E816_PROBE0
    lda f:T_WAKE_PENDING
    and #$00ff
    beq :+
    brl claim_checkpoint_return
:
    lda #7
    sta f:E816_PROBE0
    lda f:E816_CURRENT
    and #$00ff
    sta 9
    lda f:IRQ_COUNT
    sta 5
    lda #0
    sta f:T_SERIAL_BINDING+T_BINDING_MASK
    lda #$8000
    sta f:T_SERIAL_BINDING+T_BINDING_MASK+2
    sep #$20
    lda #$a5
    sta f:$d20d
    rep #$20
    cli
claim_checkpoint_wait:
    lda f:IRQ_COUNT
    cmp 5
    beq claim_checkpoint_wait
    sei
    lda f:T_BASE+T_TCB_QUEUED,x
    and #$00ff
    cmp #T_WAKE_CLAIMED
    bne claim_checkpoint_return
    lda #15
    sta f:E816_PROBE0
    lda f:E816_CURRENT
    and #$00ff
    cmp 9
    bne claim_checkpoint_return
    lda #31
    sta f:E816_PROBE0
    lda f:E816_SWITCHING
    and #$00ff
    cmp #1
    bne claim_checkpoint_return
    lda #63
    sta f:E816_PROBE0
    lda f:T_WAKE_PENDING
    and #$00ff
    bne claim_checkpoint_return
    lda #127
    sta f:E816_PROBE0
claim_checkpoint_return:
    atomic_return
signal_claim_checkpoint_end:
.endif
