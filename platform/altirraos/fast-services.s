; Public COP services that complete without borrowing the Action! kernel stack
; or compiler workspace. Enter only after common frame validation, SWITCHING=1.
; X = saved frame, Y = service. All unhandled selectors retain the general path.
.segment "SIGNAL_CODE"
.a16
.i16
.export fast_entry, fast_complete, fast_general, fast_return

FAST_LOCAL = 20                 ; Task/port pointer, frame, context, selector, links

fast_entry:
    cpy #P_SERVICE_GET_MSG
    beq fast_exclusion
    cpy #T_SERVICE_FORBID
    beq fast_exclusion
    cpy #T_SERVICE_PERMIT
    beq fast_exclusion
    jml dispatch_frame

fast_exclusion:
    ; Same width, A and high-byte tag checks as RequestValid. The low byte of
    ; Y is unused by these two services and remains accepted as before.
    lda f:T_FRAME_P,x
    and #$30
    beq :+
    jml context_fault
:
    lda f:T_FRAME_A_FULL,x
    and #$ff00
    beq :+
    jml context_fault
:
    lda f:T_FRAME_Y,x
    cpy #P_SERVICE_GET_MSG
    beq fast_tag
    and #$ff00
fast_tag:
    cmp #T_PROFILE_TAG
    beq :+
    jml context_fault
:
    ; Save scratch below the already validated full frame. The normal Task
    ; floor leaves 256 bytes of interrupt reserve; this adds twenty bytes to its
    ; 13-byte COP frame. No nested native subroutine frame is retained.
    txa
    sec
    sbc #FAST_LOCAL
    tcs
    tcd
    stx 4
    sty 8
    lda f:E816_CURRENT
    and #$ff
    cmp #T_CAPACITY
    bcc :+
    jml context_fault
:
    .repeat T_SHIFT
        asl a
    .endrepeat
    tax
    stx 6
    lda f:T_BASE+T_TCB_ITEM,x
    sta 1
    sep #$20
    lda f:T_BASE+T_TCB_ITEM+2,x
    sta 3
    rep #$20
    lda 4
    sta f:T_BASE+T_TCB_SAVEDS,x
    ldy #T_TASK_TC_SPREG
    sta [1],y
    sep #$20
    lda #0
    iny
    iny
    sta [1],y
    rep #$20
    ldy 8
    cpy #P_SERVICE_GET_MSG
    bne :+
    jmp fast_getmsg
:
    lda f:T_BASE+T_TCB_LOCKDEPTH,x
    ldy 8
    cpy #T_SERVICE_FORBID
    bne fast_permit
    cmp #128
    bcc :+
    jml context_fault
:
    inc a
    bra fast_depth
fast_permit:
    cmp #0
    bne :+
    jml context_fault
:
    dec a
fast_depth:
    sta f:T_BASE+T_TCB_LOCKDEPTH,x
    checkpoint 19
    dec a
    ldy #T_TASK_TC_TDNESTCNT
    sep #$20
    sta [1],y
    rep #$20
    checkpoint 20
fast_complete:
    ; IRQ publication is excluded from the last check through RTI. NMI can
    ; still set a tick after the check; that hint remains pending, matching
    ; the general return protocol. Never consume hints in this shortcut.
    sei
    checkpoint 21
    lda f:E816_TICK_PENDING
    and #$ff
    bne fast_general
    lda f:T_TIMER_PENDING
    and #$ff
    bne fast_general
    lda f:T_WAKE_PENDING
    and #$ff
    bne fast_general
    ldx 6
    lda f:T_BASE+T_TCB_PENDING,x
    and #$ff
    beq fast_return
    lda f:T_BASE+T_TCB_LOCKDEPTH,x
    bne fast_return
    ldx 4
    lda f:T_FRAME_P,x
    and #4
    bne fast_return
    lda f:OS_BUSY
    and #$ff
    bne fast_return
fast_general:
    ; The operation has already committed. Poll preserves its result frame
    ; and drains wakes/timers; dispatching the original service would repeat it.
    ldx 4
    txa
    tcs
    lda #E816_KERNEL_DP
    tcd
    ldy #E816_SERVICE_POLL
    jml dispatch_frame
fast_return:
    checkpoint 22
    ldx 4
    txa
    tcs
    lda #E816_KERNEL_DP
    tcd
    jml restore_selected

.include "fast-getmsg.inc"
