; Shared bounded XEX interpreter; get_byte supplies one verified stream byte.
.export xex_start
xex_start:
    lda #3
    sta reader_phase
    stz $02e0
    stz $02e1
    stz $02e2
    stz $02e3
    jsr read_word
    lda word
    and word+1
    cmp #$ff
    jne bad_header
segment:
    lda file_left
    ora file_left+1
    ora file_left+2
    jeq reader_run
    jsr read_word
    lda word
    and word+1
    cmp #$ff
    beq segment
    lda word
    sta store_byte+1
    lda word+1
    sta store_byte+2
    lda $02e0
    ora $02e1
    bne :+
    lda word
    sta $02e0
    lda word+1
    sta $02e1
:
    jsr read_word
    ; Admit vector writes or bank-zero boot spans outside live reader/OS RAM.
    lda store_byte+2
    cmp #2
    bne @ordinary
    lda store_byte+1
    cmp #$e0
    jcc bad_segment
    lda word+1
    cmp #2
    jne bad_segment
    lda word
    cmp #$e4
    jcs bad_segment
    bra @length
@ordinary:
    lda store_byte+2
    cmp #$0a
    jcc bad_segment
    cmp #$40
    bcc @below_reader
    cmp #$60
    jcc bad_segment
    lda word+1
    cmp #$80
    jcs bad_segment
    bra @length
@below_reader:
    lda word+1
    cmp #$40
    jcs bad_segment
@length:
    sec
    lda word
    sbc store_byte+1
    sta segment_left
    lda word+1
    sbc store_byte+2
    sta segment_left+1
    jcc bad_segment
    inc segment_left
    bne :+
    inc segment_left+1
:
copy_segment:
    jsr get_byte
store_byte:
    sta a:$ffff
    inc store_byte+1
    bne :+
    inc store_byte+2
:
    lda segment_left
    bne :+
    dec segment_left+1
:
    dec segment_left
    lda segment_left
    ora segment_left+1
    bne copy_segment
    lda $02e2
    ora $02e3
    jeq segment
    lda $02e2
    sta callback+1
    lda $02e3
    sta callback+2
    stz $02e2
    stz $02e3
    lda callback+2
    jsr admit_entry
    jsr check_guards
reader_callback:
    inc reader_callbacks
    bne :+
    inc reader_callbacks+1
:
.if BOOT_FAST
    jsr boot_before_callback
.endif
    jsr callback
.if BOOT_FAST
    jsr boot_after_callback
.endif
    jsr check_guards
    jmp segment
callback:
    jmp a:$ffff
reader_run:
.if BOOT_BACKEND=1
    lda file_map
    ora file_map+1
    jne bad_chain
    lda buffer_cursor
    cmp buffer_limit
    jne bad_chain
.endif
    lda $02e0
    ora $02e1
    jeq bad_segment
    lda $02e1
    jsr admit_entry
    jsr check_guards
    lda #4
    sta reader_phase
    ; Firmware transfer and callback frames are complete. Native entry never
    ; returns; it is free to initialize this arena as ordinary worker stacks.
.if BOOT_FAST
    jsr boot_handoff
.endif
    jmp ($02e0)
admit_entry:
    cmp #$0a
    jcc bad_segment
    cmp #$40
    bcc @ok
    cmp #$60
    jcc bad_segment
    cmp #$80
    jcs bad_segment
@ok:
    rts
