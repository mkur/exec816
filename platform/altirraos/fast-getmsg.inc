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
    ldy #P_MSGPORT_MP_MSGLIST
    lda [1],y
    sta 10
    iny
    iny
    sep #$20
    lda [1],y
    sta 12
    rep #$20
    ; RemHead tests the first node's successor, including the tail sentinel.
    lda [10]
    sta 13
    ldy #2
    sep #$20
    lda [10],y
    sta 15
    rep #$20
    and #$ff
    ora 13
    bne fast_get_remove
    stz 10
    sep #$20
    lda #0
    sta 12
    rep #$20
    bra fast_get_result
fast_get_remove:
    ldy #3
    lda [10],y
    sta 16
    sta 1
    ldy #5
    sep #$20
    lda [10],y
    sta 18
    sta 3
    rep #$20
    lda 13
    sta [1]
    ldy #2
    sep #$20
    lda 15
    sta [1],y
    rep #$20
    .if HEAP_PROBE
        ; Test-only four-byte patch point for a preserving native IRQ/NMI probe.
        .export fast_dequeue_probe
fast_dequeue_probe:
        nop
        nop
        nop
        nop
    .endif
    checkpoint 23
    ldy #3
    lda 16
    sta [13],y
    ldy #5
    sep #$20
    lda 18
    sta [13],y
    rep #$20
fast_get_result:
    ldx 4
    lda 10
    sta f:T_FRAME_A_FULL,x
    lda 12
    and #$ff
    sta f:T_FRAME_X,x
    checkpoint 24
    jmp fast_complete
