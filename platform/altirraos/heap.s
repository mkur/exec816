; Current EXEC memory ABI. Metadata uses COP; clearing uses caller-owned
; invocation storage and DP scratch, with IRQs and scheduling left unchanged.
.include "heap.inc"
.segment "SIGNAL_CODE"
.a16
.i16

.macro heap_context
    .local ok
    lda f:E816_IRQ_DEPTH
    bne :+
    lda f:E816_SWITCHING
    and #$00ff
    bne :+
    lda f:OS_BUSY
    and #$00ff
    bne :+
    lda A816_DP_DOMAIN_KIND_OFFSET
    and #$00ff
    bne :+
    lda f:E816_CURRENT
    and #$00ff
    cmp #T_CAPACITY
    bcs :+
    .repeat T_SHIFT
        asl a
    .endrepeat
    tax
    tdc
    cmp f:T_BASE+T_TCB_DP,x
    beq ok
:
    lda #FAULT_CONTEXT
    jml finish
ok:
.endmacro

.macro heap_packet name, selector
    .export name, .ident(.sprintf("%s_end",.string(name)))
name:
    heap_context
    tsc
    clc
    adc #4
    tax
    ldy #T_PROFILE_TAG
    lda #selector
    cop E816_COP
    rtl
.ident(.sprintf("%s_end",.string(name))):
.endmacro

heap_packet heap_free_mem, H_SERVICE_FREE_MEM
heap_packet heap_free_vec, H_SERVICE_FREE_VEC
heap_packet heap_avail_mem, H_SERVICE_AVAIL_MEM
heap_packet heap_type_of_mem, H_SERVICE_TYPE_OF_MEM

.export heap_allocate, heap_allocate_end, heap_deallocate, heap_deallocate_end
heap_allocate:
    heap_context
    jml HEAP_ALLOCATE
heap_allocate_end:
heap_deallocate:
    heap_context
    jml HEAP_DEALLOCATE
heap_deallocate_end:

.export heap_alloc_mem, heap_alloc_mem_end, heap_alloc_vec, heap_alloc_vec_end
heap_alloc_mem:
    ldy #H_SERVICE_ALLOC_MEM
    brl heap_allocate_entry
heap_alloc_mem_end:
heap_alloc_vec:
    ldy #H_SERVICE_ALLOC_VEC
    brl heap_allocate_entry
heap_alloc_vec_end:

; Twelve private bytes: cursor 1..3, result 4..6, service 7, count 8..11,
; padding 12. The native call's original arguments remain read-only at 16..23.
heap_allocate_entry:
    heap_context
    tsc
    .if STACK_CHECKS
    cmp A816_DP_STACK_CEILING_OFFSET
    bcc :+
    beq :+
    bra heap_overflow
:
    sec
    sbc #12
    bcc heap_overflow
    cmp A816_DP_STACK_FLOOR_OFFSET
    bcs :+
heap_overflow:
    lda #12
    jml stack_overflow
:
    .else
    sec
    sbc #12
    .endif
    tcs
    tya
    sta 7,s
    tsc
    clc
    adc #16
    tax
    ldy #T_PROFILE_TAG
    lda 7,s
    and #$00ff
    cop E816_COP
    ; A/X are restored to this activation even if COP resumed another task.
    sta 1,s
    sta 4,s
    txa
    sep #$20
    sta 3,s
    sta 6,s
    rep #$20
    and #$00ff
    ora 1,s
    bne :+
    brl heap_allocation_return
:
    lda 1,s
    sta A816_DP_POINTER0_OFFSET
    sep #$20
    lda 3,s
    sta A816_DP_POINTER0_OFFSET+2
    rep #$20
    ; The selector belongs to this invocation, in slot 7.
    lda 7,s
    and #$00ff
    cmp #H_SERVICE_ALLOC_VEC
    bne heap_payload_ready
    lda 16,s
    clc
    adc #15
    and #$fff8
    sta [A816_DP_POINTER0_OFFSET]
    lda 18,s
    adc #0
    ldy #2
    sta [A816_DP_POINTER0_OFFSET],y
    lda 16,s
    ldy #4
    sta [A816_DP_POINTER0_OFFSET],y
    lda 18,s
    ldy #6
    sta [A816_DP_POINTER0_OFFSET],y
    lda A816_DP_POINTER0_OFFSET
    clc
    adc #8
    sta A816_DP_POINTER0_OFFSET
    bcc :+
    sep #$20
    inc A816_DP_POINTER0_OFFSET+2
    rep #$20
:
    lda A816_DP_POINTER0_OFFSET
    sta 4,s
    sep #$20
    lda A816_DP_POINTER0_OFFSET+2
    sta 6,s
    rep #$20
heap_payload_ready:
    lda 22,s                 ; CLEAR is bit zero of the high flags word
    and #1
    beq heap_allocation_return
    lda 16,s
    sta 8,s
    lda 18,s
    sta 10,s
.export heap_clear_begin, heap_clear_end
heap_clear_begin:
    ; Long indirect indexed stores propagate bank carries. Full 64 KiB
    ; chunks wrap Y and advance the cursor's bank, never a shared cursor.
    lda 10,s
    beq heap_clear_tail
    ldy #0
    ldx #$8000
    lda #0
heap_clear_bank_loop:
    sta [A816_DP_POINTER0_OFFSET],y
    iny
    iny
    dex
    bne heap_clear_bank_loop
    sep #$20
    inc A816_DP_POINTER0_OFFSET+2
    rep #$20
    lda 10,s
    dec a
    sta 10,s
    bra heap_clear_begin
heap_clear_tail:
    ldy #0
    lda 8,s
    lsr a
    tax
    beq heap_clear_odd
    lda #0
heap_clear_tail_loop:
    sta [A816_DP_POINTER0_OFFSET],y
    iny
    iny
    dex
    bne heap_clear_tail_loop
heap_clear_odd:
    lda 8,s
    and #1
    beq heap_clear_end
    sep #$20
    lda #0
    sta [A816_DP_POINTER0_OFFSET],y
    rep #$20
heap_clear_end:
heap_allocation_return:
    lda 4,s
    sta A816_DP_POINTER0_OFFSET
    lda 6,s
    and #$00ff
    tax
    tsc
    clc
    adc #12
    tcs
    lda A816_DP_POINTER0_OFFSET
    rtl
