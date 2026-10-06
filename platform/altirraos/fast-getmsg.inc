; Included in fast-services.s after its completion/return paths. Uses the same
; local frame: 1=port/previous, 4=saved S, 6=context offset, 8=service,
; 10=item, 13=following, 16=previous. Far accesses carry across bank boundaries.
fast_getmsg:
    ldx 4
    lda f:T_FRAME_X,x
    ldx 6
    cmp f:T_BASE+T_TCB_STACKFLOOR,x
    bcs :+
    jml context_fault
:
    sta 1
    clc
    adc #2
    bcc :+
    jml context_fault
:
    cmp f:T_BASE+T_TCB_STACKTOP,x
    bcc :+
    beq :+
    jml context_fault
:
    ; The exact public port tag has a zero low byte, hence a bank-zero packet.
    sep #$20
    lda #0
    sta 3
    rep #$20
    lda [1]
    sta 10
    ldy #2
    sep #$20
    lda [1],y
    sta 12
    sta 3
    rep #$20
    lda 10
    sta 1
    lda 12
    and #$ff
    ora 1
    bne :+
    jml context_fault
:
    lda 1
    clc
    adc #P_MSGPORT_BYTES-1
    bcc :+
    lda 3
    and #$ff
    cmp #$ff
    bne :+
    jml context_fault
:
    ldy #P_MSGPORT_MP_NODE+6
    lda [1],y
    and #$ff
    cmp #P_NT_MSGPORT
    beq :+
    jml context_fault
:
    ldy #P_MSGPORT_MP_FLAGS
    lda [1],y
    and #$ff
    cmp #P_PA_SIGNAL
    beq :+
    cmp #P_PA_IGNORE
    beq :+
    jml context_fault
:
    ; Pass the validated port to the common atomic dequeue. Its native local
    ; frame preserves this gateway's D. No compiler-domain header is borrowed.
    sep #$20
    lda 3
    pha
    rep #$20
    lda 1
    pha
    jsl ports_take_fast
    sta 10
    stx 12
    tsc
    clc
    adc #3
    tcs
    ldx 4
    lda 10
    sta f:T_FRAME_A_FULL,x
    lda 12
    and #$ff
    sta f:T_FRAME_X,x
    checkpoint 24
    jmp fast_complete
