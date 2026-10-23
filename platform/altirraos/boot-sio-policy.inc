.export boot_query_done,boot_reply
.export boot_index_seen,boot_fast_fail,boot_query_error
; Queries use a distinct buffer: a partially consumed XEX sector stays live.
boot_query:
    sta dcb+2
    stx dcb+8
    stz dcb+9
    lda #<boot_reply
    sta dcb+4
    lda #>boot_reply
    sta dcb+5
    jsr read_sector_status
boot_query_done:
    sty boot_status
    lda #$52
    sta dcb+2
    stz dcb+8
    lda #1
    sta dcb+9
    lda #<sector_buffer
    sta dcb+4
    lda #>sector_buffer
    sta dcb+5
    ldy boot_status
    rts
boot_status_read:
    lda #$53
    ldx #4
    jmp boot_query
boot_sync_standard:
    lda #40
    sta bo_divisor
    lda #BS_RESYNC_ATTEMPTS
    sta boot_retries
@attempt:
    jsr boot_status_read
    tya
    cmp #$80
    jeq cancelled
    tya
    bpl @ok
    dec boot_retries
    bne @attempt
    lda #$cb
    jmp reader_failed
@ok:
    rts
boot_select_speed:
.if BOOT_BACKEND=1
    lda take_descriptor+BS_DESC_POLICY
.else
    lda #BOOT_POLICY
.endif
    bne boot_select_fast
    lda #40
    sta bo_divisor
    rts
boot_select_fast:
    lda #$3f
    ldx #1
    jsr boot_query
    tya
    bmi boot_sync_standard
    sty boot_query_error
    lda boot_reply
    sta boot_index_seen
    cmp #8
    bne boot_sync_standard
    sta bo_divisor
    jsr boot_status_read
    sty boot_fast_fail
    tya
    bmi boot_sync_standard
    rts
boot_suspend:
    lda bo_divisor
    cmp #8
    bne boot_sync_standard
    lda #$3f
    ldx #1
    jsr boot_query
    jmp boot_sync_standard
boot_resume:
    jsr boot_sync_standard
.if BOOT_BACKEND=1
    jsr take_verify_source
.endif
    jmp boot_select_speed
boot_before_callback:
    stz boot_suspended
    ldx #0
@local:
.if BOOT_BACKEND=1
    lda take_descriptor+BS_DESC_LOCAL_CALLBACKS,x
.else
    lda boot_locals,x
.endif
    cmp callback+1
    bne @next
.if BOOT_BACKEND=1
    lda take_descriptor+BS_DESC_LOCAL_CALLBACKS+1,x
.else
    lda boot_locals+1,x
.endif
    cmp callback+2
    beq @done
@next:
    inx
    inx
    cpx #6
    bne @local
    jsr boot_suspend
    inc boot_suspended
@done:
    rts
boot_after_callback:
    lda boot_suspended
    beq :+
    jsr boot_resume
:
    rts
boot_handoff:
.if BOOT_BACKEND=1
    lda take_descriptor+BS_DESC_NATIVE_DIVISOR
.else
    lda #BOOT_NATIVE_DIVISOR
.endif
    cmp bo_divisor
    beq @done
    cmp #40
    beq boot_suspend
    jsr boot_select_fast
    lda bo_divisor
    cmp #8
    beq @done
    lda #$cc
    jmp reader_failed
@done:
    rts
boot_locals: .word BOOT_LOCAL0,BOOT_LOCAL1,BOOT_LOCAL2
boot_retries: .byte 0
boot_status: .byte 0
boot_suspended: .byte 0
boot_reply: .res 4,0

boot_index_seen: .byte 0
boot_fast_fail: .byte 0
boot_query_error: .byte 0
