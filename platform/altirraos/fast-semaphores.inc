; Task-only semaphore state under SWITCHING. Shared fast frame:
; 1=current Task, 4=saved frame, 6=context offset, 8=selector, 10=semaphore.
; IRQ/NMI neither traverse the object nor borrow this activation's scratch.
.export sem_policy
fast_semaphore_validate:
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
    and #$ff00
    cmp #T_PROFILE_TAG
    beq :+
    jml context_fault
:
    jmp fast_setup

fast_semaphore_call:
    .if PROBE_NMI = 200
        lda #1
        sta f:E816_PROBE0+4
    .endif
    ldx 4
    lda f:T_FRAME_X,x
    sta 10
    lda f:T_FRAME_Y,x
    and #$ff
    sta 12
    ldy #SEM_OWNER
    lda [10],y
    cmp 1
    bne sem_other
    ldy #SEM_OWNER+2
    lda [10],y
    and #$ff
    sta 16
    lda 3
    and #$ff
    cmp 16
    bne sem_other
    ldy #SEM_DEPTH
    lda [10],y
    ldx 8
    cpx #SEM_SERVICE_RELEASE_SEMAPHORE
    bne :+
    jmp sem_release
:
    cmp #$ffff
    bne :+
    jml context_fault
:
    inc a
    sta [10],y
    semaphore_checkpoint 46
    jmp sem_success

sem_other:
    ldx 8
    cpx #SEM_SERVICE_RELEASE_SEMAPHORE
    bne :+
    jml context_fault
:
    ldy #SEM_OWNER
    lda [10],y
    sta 16
    ldy #SEM_OWNER+2
    lda [10],y
    and #$ff
    ora 16
    bne sem_busy
    ldx 6
    lda f:T_BASE+T_TCB_SEMAPHOREOWNED,x
    cmp #$ffff
    bne :+
    jml context_fault
:
    inc a
    sta f:T_BASE+T_TCB_SEMAPHOREOWNED,x
    ldy #SEM_OWNER
    lda 1
    sta [10],y
    ldy #SEM_OWNER+2
    lda 3
    and #$ff
    sta [10],y
    ldy #SEM_DEPTH
    lda #1
    sta [10],y
sem_success:
    semaphore_checkpoint 40
    ldx 8
    cpx #SEM_SERVICE_OBTAIN_SEMAPHORE
    bne :+
    jmp fast_complete
:
    lda #1
    bra sem_result
sem_busy:
    ldx 8
    cpx #SEM_SERVICE_OBTAIN_SEMAPHORE
    bne :+
    jmp sem_policy
:
    lda #0
sem_result:
    ldx 4
    sta f:T_FRAME_A_FULL,x
    lda #0
    sta f:T_FRAME_X,x
    jmp fast_complete

sem_release:
    cmp #0
    bne :+
    jml context_fault
:
    cmp #1
    beq sem_final
    dec a
    sta [10],y
    semaphore_checkpoint 48
    jmp fast_complete
sem_final:
    ; Classify a queued release before mutating depth or ownership counts.
    ldy #SEM_HEAD
    lda [10],y
    sta 16
    ldy #SEM_HEAD+2
    lda [10],y
    and #$ff
    ora 16
    bne sem_policy
    ldx 6
    lda f:T_BASE+T_TCB_SEMAPHOREOWNED,x
    dec a
    sta f:T_BASE+T_TCB_SEMAPHOREOWNED,x
    lda #0
    ldy #SEM_DEPTH
    sta [10],y
    ldy #SEM_OWNER
    sta [10],y
    ldy #SEM_OWNER+2
    sta [10],y
    semaphore_checkpoint 47
    jmp fast_complete

; Retire native scratch and continue this admitted request, without a COP.
sem_policy:
    semaphore_checkpoint 41
    ldy 8
    ldx 4
    txa
    tcs
    lda #E816_KERNEL_DP
    tcd
    semaphore_checkpoint 42
    jml dispatch_frame

.if PROBE_NMI = 200
semaphore_checkpoint_native:
    pha
    lda f:E816_PROBE0+4
    beq sem_checkpoint_done
    pla
    cmp f:E816_PROBE0
    bne sem_checkpoint_return
    lda #$100
    sta f:E816_PROBE0
    lda f:E816_NMI_COUNT
    sta f:E816_PROBE0+2
sem_checkpoint_wait:
    lda f:E816_NMI_COUNT
    cmp f:E816_PROBE0+2
    beq sem_checkpoint_wait
    rtl
sem_checkpoint_done:
    pla
sem_checkpoint_return:
    rtl

.export semaphore_checkpoint_call, semaphore_checkpoint_call_end
semaphore_checkpoint_call:
    lda 4,s
    cmp #43
    bne :+
    semaphore_checkpoint 43
:
    cmp #44
    bne :+
    semaphore_checkpoint 44
:
    cmp #45
    bne :+
    semaphore_checkpoint 45
:
    rtl
semaphore_checkpoint_call_end:
.endif

.include "semaphore-gateway.inc"
