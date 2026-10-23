.ifndef BOOT_NMI_POINT
BOOT_NMI_POINT=0
.endif
.export bo_transfer,bo_error,bo_phase,bo_sum,bo_left,bo_done,bo_clock,bo_divisor
.export bo_waittype,bo_txindex
.export bo_new_vectors,bo_tx,bo_rx,bo_complete,bo_cleanup,bo_store,bo_command,bo_value,bo_ready
; Boot-only E=1/A8/X8 serial engine. ROM IRQ pushes A; vectors finish PLA/RTI.
; NMI uses the ROM VBI throughout. CRITIC suppresses deferred OS callbacks while
; descriptors/vectors are private; only six-byte vector publication masks IRQ.
; Input: ordinary read DCB, bo_divisor (40 or 8). Output: Y=status (1=success).
bo_transfer:
    php
    sei
    lda $10
    sta bo_old_mask
    and #$c7
    sta $10
    sta $d20e
    lda $42
    sta bo_old_critic
.if BOOT_NMI_POINT=1
    jsr bo_nmi_checkpoint
.endif
    lda #1
    sta $42
    lda $0232
    sta bo_old_skctl
    lda $d303
    sta bo_old_pbctl
    ldx #5
@save:
    lda $020a,x
    sta bo_vectors,x
    lda bo_new_vectors,x
    sta $020a,x
.if BOOT_NMI_POINT=2
    jsr bo_nmi_checkpoint
.endif
    dex
    bpl @save
    stz bo_error
    stz bo_done
    stz bo_phase
    stz bo_sum
    lda $0304
    sta bo_store+1
    lda $0305
    sta bo_store+2
    lda $0308
    sta bo_left
    lda $0309
    sta bo_left+1
    stz $d20f                    ; reset serializer before changing its clock
    lda bo_divisor
    sta $d204
    stz $d206
    lda #$a0
    sta $d205
    sta $d207
    lda #$28
    sta $d208
    lda #$23
    sta $0232
    sta $d20f
    sta $d20a
    sta $d209
    lda $14
    sta bo_clock
    lda $0300
    clc
    adc $0301
    sec
    sbc #1
    sta bo_command
    lda $0302
    sta bo_command+1
    lda $030a
    sta bo_command+2
    lda $030b
    sta bo_command+3
    ldx #3
    lda #0
@sum:
    clc
    adc bo_command,x
    adc #0
    dex
    bpl @sum
    sta bo_command+4
    cli
    lda #3
    jsr bo_delay                 ; finish prior stop bit before COMMAND edge
    lda bo_old_pbctl
    and #$c7
    ora #$30
    sta $d303
    cli
    lda #3
    jsr bo_delay
    stz bo_ready
    stz bo_txindex
    lda #1
    sta bo_waittype
    sei
    lda $10
    ora #$10
    jsr bo_mask
    jsr bo_send_next
    cli
@drain:
    lda #2
    sta bo_waittype
    jsr bo_deadline
    lda bo_done
    bne bo_cleanup
    lda bo_ready
    beq @drain
    lda #8
    jsr bo_delay
    ; Receive is armed before COMMAND rises.
    lda #$13
    sta $0232
    sta $d20f
    lda $10
    ora #$20
    jsr bo_mask
    lda bo_old_pbctl
    and #$c7
    ora #$38
    sta $d303
@wait:
    lda #3
    sta bo_waittype
    jsr bo_deadline
    lda bo_done
    beq @wait
bo_cleanup:
    sei
    lda $10
    and #$c7
    jsr bo_mask
    lda bo_old_pbctl
    sta $d303
    ldx #5
@restore:
    lda bo_vectors,x
    sta $020a,x
.if BOOT_NMI_POINT=3
    jsr bo_nmi_checkpoint
.endif
    dex
    bpl @restore
    lda #40
    sta $d204
    stz $d206
    lda #$28
    sta $d208
    lda bo_old_skctl
    sta $0232
    sta $d20f
    lda bo_old_critic
    sta $42
.if BOOT_NMI_POINT=4
    jsr bo_nmi_checkpoint
.endif
    lda bo_old_mask
    jsr bo_mask
    plp
    ldy bo_error
    bne :+
    ldy #1
:
    rts
bo_mask:
    sta $10
    sta $d20e
    rts
bo_delay:
    sta bo_ticks
    lda $d40b
@line:
    cmp $d40b
    beq @line
    lda $d40b
    dec bo_ticks
    bne @line
    rts
bo_deadline:
    lda $11
    bne :+
    lda #$80
    jmp bo_fail
:
    lda $14
    sec
    sbc bo_clock
    cmp #BS_DEADLINE_FRAMES
    bcc :+
    lda bo_error
    jne bo_fail
    lda #$8a
    jmp bo_fail
:
    rts
bo_send_next:
    ldx bo_txindex
    cpx #5
    beq @sent
    lda bo_command,x
    sta $d20d
    inc bo_txindex
    rts
@sent:
    lda $10
    and #$ef
    ora #8
    jmp bo_mask
bo_tx:
    phx
    jsr bo_send_next
    plx
    pla
    rti
bo_complete:
    lda $10
    and #$f7
    jsr bo_mask
    inc bo_ready
    pla
    rti
bo_rx:
    lda $d20d
    sta bo_value
    lda $d20f
    and #$a0
    cmp #$a0
    bne bo_framing
    lda bo_phase
    beq bo_ack
    cmp #1
    beq bo_result
    cmp #2
    beq bo_data
    lda bo_value
    cmp bo_sum
    beq bo_finish
    lda #$8f
    bra bo_fail_irq
bo_ack:
    lda bo_value
    cmp #$4e
    beq bo_nak
    cmp #$41
    bne bo_protocol
    inc bo_phase
    bra bo_irq_return
bo_result:
    lda bo_value
    cmp #$43
    beq :+
    cmp #$45
    bne bo_protocol
    lda #$90
    sta bo_error               ; bounded drain for ERROR-with-payload
:
    inc bo_phase
    bra bo_irq_return
bo_data:
    lda bo_value
bo_store:
    sta a:$ffff
    clc
    adc bo_sum
    adc #0
    sta bo_sum
    inc bo_store+1
    bne :+
    inc bo_store+2
:
    lda bo_left
    bne :+
    dec bo_left+1
:
    dec bo_left
    lda bo_left
    ora bo_left+1
    bne bo_irq_return
    inc bo_phase
bo_irq_return:
    pla
    rti
bo_nak:
    lda #$8b
    bra bo_fail_irq
bo_protocol:
    lda #$8e
    bra bo_fail_irq
bo_framing:
    lda #$8c
bo_fail_irq:
    sta bo_error
bo_finish:
    lda $10
    and #$df
    jsr bo_mask
    lda #1
    sta bo_done
    pla
    rti
bo_fail:
    sta bo_error
    lda #1
    sta bo_done
    rts
bo_new_vectors: .word bo_rx,bo_tx,bo_complete
bo_vectors: .res 6,0
bo_divisor: .byte 40
bo_error: .byte 0
bo_done: .byte 0
bo_phase: .byte 0
bo_sum: .byte 0
bo_left: .word 0
bo_value: .byte 0
bo_ready: .byte 0
bo_clock: .byte 0
bo_ticks: .byte 0
bo_old_mask: .byte 0
bo_old_critic: .byte 0
bo_old_skctl: .byte 0
bo_old_pbctl: .byte 0
bo_command: .res 5,0

bo_waittype: .byte 0
bo_txindex: .byte 0

.if BOOT_NMI_POINT
; Test-only publication delay. No frame is active at these four points.
; The actual ROM VBI runs with the production IRQ mask, stack and vectors.
.export bo_nmi_done
bo_nmi_checkpoint:
    php
    pha
    lda bo_nmi_done
    bne @done
    lda $14
@wait:
    cmp $14
    beq @wait
    inc bo_nmi_done
@done:
    pla
    plp
    rts
bo_nmi_done: .byte 0
.endif
