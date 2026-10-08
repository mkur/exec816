; Streaming raw LZ4, E=1/A8/I8 throughout. No DP, OS stack transition, IRQ/NMI
; masking or upper scratch bank. Input resumes across ordinary staging records.
; Each forward indexed copy is at most 256 bytes; overlapping matches work
; because later reads observe the bytes just written. Lengths are admitted
; against the current descriptor before copying. State is boot-only loader data.
.export lz4_record, lz4_decode, lz4_yield, lz4_active
.export lz4_decode_begin, lz4_decode_end

lz4_record:
    lda M_STAGE+M_RECORD_KIND
    cmp #1
    jeq bad_record
    lda M_STAGE+M_RECORD_ENCODING
    cmp #M_ENCODING_LZ4_BEGIN
    jne lz4_continue
    lda lz4_active
    jne bad_record
    lda M_STAGE+M_RECORD_COUNT+1
    bne @header
    lda M_STAGE+M_RECORD_COUNT
    cmp #M_LZ4_HEADER_BYTES+1
    jcc bad_record
@header:
    lda M_PAYLOAD+M_LZ4_HEADER_OUTPUT
    sta lz4_output_size
    sta lz4_output_left
    lda M_PAYLOAD+M_LZ4_HEADER_OUTPUT+1
    sta lz4_output_size+1
    sta lz4_output_left+1
    cmp #>M_LZ4_BLOCK_BYTES
    jcc @size
    jne bad_record
    lda lz4_output_size
    jne bad_record
@size:
    lda lz4_output_size
    ora lz4_output_size+1
    jeq bad_record
    clc
    lda M_OFFSET
    adc lz4_output_size
    sta M_WORK+2
    lda M_OFFSET+1
    adc lz4_output_size+1
    sta M_WORK+3
    jcs bad_record
    ldx #5
    jsr descriptor
    cmp M_WORK+3
    jcc bad_record
    bne @end
    dex
    jsr descriptor
    cmp M_WORK+2
    jcc bad_record
@end:
    lda M_PAYLOAD+M_LZ4_HEADER_INPUT
    sta lz4_input_left
    lda M_PAYLOAD+M_LZ4_HEADER_INPUT+1
    sta lz4_input_left+1
    lda lz4_input_left
    ora lz4_input_left+1
    jeq bad_record
    ; Stored blocks must be smaller than their expanded output.
    lda lz4_input_left+1
    cmp lz4_output_size+1
    bcc @input
    jne bad_record
    lda lz4_input_left
    cmp lz4_output_size
    jcs bad_record
@input:
    jsr prepare_destination
    lda #<(M_PAYLOAD+M_LZ4_HEADER_BYTES)
    sta lz4_get_read+1
    lda #>(M_PAYLOAD+M_LZ4_HEADER_BYTES)
    sta lz4_get_read+2
    sec
    lda M_STAGE+M_RECORD_COUNT
    sbc #M_LZ4_HEADER_BYTES
    sta lz4_stage_left
    lda M_STAGE+M_RECORD_COUNT+1
    sbc #0
    sta lz4_stage_left+1
    stz lz4_state
    lda #1
    sta lz4_active
    bra lz4_admit
lz4_continue:
    lda lz4_active
    jeq bad_record
    lda #<M_PAYLOAD
    sta lz4_get_read+1
    lda #>M_PAYLOAD
    sta lz4_get_read+2
    lda M_STAGE+M_RECORD_COUNT
    sta lz4_stage_left
    lda M_STAGE+M_RECORD_COUNT+1
    sta lz4_stage_left+1
lz4_admit:
    lda lz4_input_left+1
    cmp lz4_stage_left+1
    jcc bad_record
    bne @decode
    lda lz4_input_left
    cmp lz4_stage_left
    jcc bad_record
@decode:
lz4_decode_begin:
    jsr lz4_decode
lz4_decode_end:
    lda loader_error
    bne lz4_return
    lda lz4_active
    jne record_pending
    jmp record_committed
lz4_return:
    rts

; States: token, literal length extension, literals, offset low/high,
; match length extension, match copy. Only input exhaustion yields a callback.
lz4_decode:
    lda lz4_state
    beq lz4_token_next
    cmp #1
    jeq lz4_literal_length
    cmp #2
    jeq lz4_literals
    cmp #3
    jeq lz4_offset_low
    cmp #4
    jeq lz4_offset_high
    cmp #5
    jeq lz4_match_length
    jmp lz4_matches
lz4_token_next:
    jsr lz4_get
    jcc lz4_yield
    sta lz4_token
    lsr a
    lsr a
    lsr a
    lsr a
    sta lz4_length
    stz lz4_length+1
    cmp #15
    beq @extend
    jmp lz4_literal_ready
@extend:
    inc lz4_state
lz4_literal_length:
    jsr lz4_extend
    jcc lz4_yield
    jmp lz4_literal_ready
lz4_literal_ready:
    ; Literal input must fit the remaining compressed stream as well as output.
    lda lz4_input_left+1
    cmp lz4_length+1
    jcc bad_record
    bne @output
    lda lz4_input_left
    cmp lz4_length
    jcc bad_record
@output:
    jsr lz4_admit_output
    lda loader_error
    jne lz4_yield
    lda #2
    sta lz4_state
lz4_literals:
    lda lz4_length
    ora lz4_length+1
    beq @done
    lda lz4_stage_left
    ora lz4_stage_left+1
    jeq lz4_yield
    jsr lz4_chunk_size
    ; Restrict the copy to this input record, then debit the complete chunk.
    lda lz4_stage_left+1
    cmp lz4_chunk+1
    bcc @short
    bne @ready
    lda lz4_stage_left
    cmp lz4_chunk
    bcs @ready
@short:
    lda lz4_stage_left
    sta lz4_chunk
    lda lz4_stage_left+1
    sta lz4_chunk+1
@ready:
    sec
    lda lz4_stage_left
    sbc lz4_chunk
    sta lz4_stage_left
    lda lz4_stage_left+1
    sbc lz4_chunk+1
    sta lz4_stage_left+1
    sec
    lda lz4_input_left
    sbc lz4_chunk
    sta lz4_input_left
    lda lz4_input_left+1
    sbc lz4_chunk+1
    sta lz4_input_left+1
    lda lz4_get_read+1
    sta lz4_copy_read+1
    lda lz4_get_read+2
    sta lz4_copy_read+2
    stz lz4_copy_read+3
    jsr lz4_copy
    clc
    lda lz4_get_read+1
    adc lz4_chunk
    sta lz4_get_read+1
    lda lz4_get_read+2
    adc lz4_chunk+1
    sta lz4_get_read+2
    jmp lz4_literals
@done:
    inc lz4_state
lz4_offset_low:
    lda lz4_input_left
    ora lz4_input_left+1
    bne @offset
    lda lz4_output_left
    ora lz4_output_left+1
    jne bad_record
    stz lz4_active
    rts
@offset:
    jsr lz4_get
    jcc lz4_yield
    sta lz4_offset
    inc lz4_state
lz4_offset_high:
    jsr lz4_get
    jcc lz4_yield
    sta lz4_offset+1
    ora lz4_offset
    jeq bad_record
    ; A match cannot refer before this block's first output byte.
    sec
    lda lz4_output_size
    sbc lz4_output_left
    sta lz4_chunk
    lda lz4_output_size+1
    sbc lz4_output_left+1
    cmp lz4_offset+1
    jcc bad_record
    bne @length
    lda lz4_chunk
    cmp lz4_offset
    jcc bad_record
@length:
    lda lz4_token
    and #15
    clc
    adc #4
    sta lz4_length
    stz lz4_length+1
    cmp #19
    beq @extend
    jmp lz4_match_ready
@extend:
    inc lz4_state
lz4_match_length:
    jsr lz4_extend
    jcc lz4_yield
lz4_match_ready:
    jsr lz4_admit_output
    lda loader_error
    jne lz4_yield
    lda #6
    sta lz4_state
lz4_matches:
    lda lz4_length
    ora lz4_length+1
    beq @done
    jsr lz4_chunk_size
    sec
    lda destination+1
    sbc lz4_offset
    sta lz4_copy_read+1
    lda destination+2
    sbc lz4_offset+1
    sta lz4_copy_read+2
    lda destination+3
    sta lz4_copy_read+3
    jsr lz4_copy
    bra lz4_matches
@done:
    stz lz4_state
    jmp lz4_decode
lz4_yield:
    ; An exhausted stream in any state other than final literals is malformed.
    lda lz4_input_left
    ora lz4_input_left+1
    jeq bad_record
    rts

lz4_admit_output:
    sec
    lda lz4_output_left
    sbc lz4_length
    sta lz4_output_left
    lda lz4_output_left+1
    sbc lz4_length+1
    sta lz4_output_left+1
    jcc bad_record
    rts

lz4_extend:
    jsr lz4_get
    bcc @yield
    tax
    clc
    adc lz4_length
    sta lz4_length
    lda lz4_length+1
    adc #0
    sta lz4_length+1
    bcs @overflow
    txa
    cmp #255
    beq lz4_extend
    sec
@yield:
    rts
@overflow:
    jsr bad_record
    clc
    rts

lz4_get:
    lda lz4_stage_left
    bne @available
    lda lz4_stage_left+1
    beq lz4_get_empty
    dec lz4_stage_left+1
@available:
    dec lz4_stage_left
    ; Every record was bounded by input_left on admission.
    lda lz4_input_left
    bne :+
    dec lz4_input_left+1
:
    dec lz4_input_left
lz4_get_read:
    lda f:M_PAYLOAD
    tay
    inc lz4_get_read+1
    bne :+
    inc lz4_get_read+2
:
    tya
    sec
    rts
lz4_get_empty:
    clc
    rts

lz4_chunk_size:
    ; X is eight bits; count zero in the copy loop means 256 bytes.
    lda lz4_length+1
    beq @short
    stz lz4_chunk
    lda #1
    sta lz4_chunk+1
    rts
@short:
    lda lz4_length
    sta lz4_chunk
    stz lz4_chunk+1
    rts

lz4_copy:
    lda destination+1
    sta lz4_copy_write+1
    lda destination+2
    sta lz4_copy_write+2
    lda destination+3
    sta lz4_copy_write+3
    ldx #0
lz4_copy_loop:
lz4_copy_read:
    lda f:$000000,x
lz4_copy_write:
    sta f:$000000,x
    inx
    cpx lz4_chunk
    bne lz4_copy_loop
    clc
    lda destination+1
    adc lz4_chunk
    sta destination+1
    lda destination+2
    adc lz4_chunk+1
    sta destination+2
    sec
    lda lz4_length
    sbc lz4_chunk
    sta lz4_length
    lda lz4_length+1
    sbc lz4_chunk+1
    sta lz4_length+1
    rts

lz4_active: .byte 0
lz4_state: .byte 0
lz4_token: .byte 0
lz4_input_left: .word 0
lz4_output_left: .word 0
lz4_output_size: .word 0
lz4_length: .word 0
lz4_stage_left: .word 0
lz4_offset: .word 0
lz4_chunk: .word 0
