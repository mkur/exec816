.export take_descriptor,take_selected,take_return,take_bounds,take_bad
; Early ordinary-XEX INIT. Only the generated descriptor locates the stream.
    php
    cld
    pha
    phx
    phy
    phb
    phd
    pea 0
    pld
    phk
    plb
    jsr boot_platform_prepare
    stz take_selected
    ldx #11
@save_dcb:
    lda $0300,x
    sta take_dcb,x
    dex
    bpl @save_dcb
    lda $d013
    jne take_return              ; the mapped cartridge owns this XEX stream
    ldx #3
@magic:
    lda take_descriptor,x
    cmp take_magic,x
    jne take_bad
    dex
    bpl @magic
    lda take_descriptor+BS_DESC_UNIT
    cmp #1
    jne take_bad
    lda take_descriptor+BS_DESC_POLICY
    cmp #2
    jcs take_bad
    lda take_descriptor+BS_DESC_NATIVE_DIVISOR
    cmp #8
    beq :+
    cmp #40
    jne take_bad
:
    lda take_descriptor+BS_DESC_VERSION
    cmp #BS_VERSION
    jne take_bad
    ; The generated descriptor must name its actual position in this prefix.
.repeat 3,I
    lda take_descriptor+BS_DESC_DESCRIPTOR_OFFSET+I
    cmp #<((BS_PREFIX_READER_OFFSET+take_descriptor-READER_ADDRESS) >> (I*8))
    jne take_bad
    lda take_descriptor+BS_DESC_PAYLOAD_OFFSET+I
    cmp #<(BS_PREFIX_BYTES >> (I*8))
    jne take_bad
.endrepeat
    lda take_descriptor+BS_DESC_PAYLOAD_SIZE
    ora take_descriptor+BS_DESC_PAYLOAD_SIZE+1
    ora take_descriptor+BS_DESC_PAYLOAD_SIZE+2
    jeq take_bad
    lda $02e8
    cmp #$0a
    bcc @top
    jne take_bounds
    lda $02e7
    jne take_bounds
@top:
    lda $02e6
    cmp #$bc
    jcc take_bounds
    ; Probe is read-only and bounded. No matching source means external load.
    lda #$53
    sta dcb+2
    lda #4
    sta dcb+8
    stz dcb+9
    jsr read_sector_status
    tya
    jmi take_return
    lda sector_buffer
    and #$20
    jeq take_return
    lda #$52
    sta dcb+2
    stz dcb+8
    lda #1
    sta dcb+9
    lda #$69
    sta reader_sector
    lda #1
    sta reader_sector+1
    jsr read_sector_status
    tya
    jmi take_return
    lda sector_buffer
    cmp #$46
    jne take_return
    ldx #10
@name:
    lda sector_buffer+5,x
    cmp take_name,x
    jne take_return
    dex
    bpl @name
    lda sector_buffer+3
    sta take_first
    sta file_map
    lda sector_buffer+4
    sta take_first+1
    sta file_map+1
    clc
.repeat 3,I
    lda take_descriptor+BS_DESC_PAYLOAD_OFFSET+I
    adc take_descriptor+BS_DESC_PAYLOAD_SIZE+I
    sta file_left+I
.endrepeat
    jcs take_bad
    stz file_offset
    stz file_offset+1
    stz file_offset+2
    stz buffer_valid
@seek:
    ldx #2
@at:
    lda file_offset,x
    cmp take_descriptor+BS_DESC_DESCRIPTOR_OFFSET,x
    bne @skip
    dex
    bpl @at
    bra @compare_start
@skip:
    jsr get_byte
    bra @seek
@compare_start:
    stz take_cursor
@compare:
    jsr get_byte
    ldx take_cursor
    cmp take_descriptor,x
    jne take_return
    inc take_cursor
    lda take_cursor
    cmp #BS_DESC_SIZE
    bne @compare
    lda #1
    sta take_selected
    jsr boot_select_speed
@payload:
    ldx #2
@pos:
    lda file_offset,x
    cmp take_descriptor+BS_DESC_PAYLOAD_OFFSET,x
    bne @next
    dex
    bpl @pos
    bra @found
@next:
    jsr get_byte
    bra @payload
@found:
    ldx #2
@size:
    lda take_descriptor+BS_DESC_PAYLOAD_SIZE,x
    sta file_left,x
    stz file_offset,x
    dex
    bpl @size
    jmp xex_start

take_bounds:
    lda #$c9
    bra take_error
take_bad:
    lda #$ca
take_error:
    ldx #1
    stx take_selected
    jmp reader_failed
take_return:
    ldx #11
@restore_dcb:
    lda take_dcb,x
    sta $0300,x
    dex
    bpl @restore_dcb
    pld
    plb
    ply
    plx
    pla
    plp
    rts

take_magic: .byte "BSI1"
take_first: .word 0
take_name: .byte "AUTORUN    "
take_cursor: .byte 0
take_selected: .byte 0
take_dcb: .res 12,0
take_descriptor: .res BS_DESC_SIZE,0

; Reopen only the descriptor after Forth. Use the DOS backend's otherwise
; unused map page, leaving the partially consumed XEX sector/cursors untouched.
take_verify_source:
    lda reader_sector
    pha
    lda reader_sector+1
    pha
    lda take_first
    sta take_verify_next
    lda take_first+1
    sta take_verify_next+1
    lda take_descriptor+BS_DESC_DESCRIPTOR_OFFSET
    sta take_skip
    lda take_descriptor+BS_DESC_DESCRIPTOR_OFFSET+1
    sta take_skip+1
    stz take_hops
    jsr take_verify_read
@seek:
    lda take_skip+1
    bne @advance
    lda take_skip
    cmp take_limit
    bcc @found
@advance:
    sec
    lda take_skip
    sbc take_limit
    sta take_skip
    lda take_skip+1
    sbc #0
    sta take_skip+1
    jsr take_verify_read
    bra @seek
@found:
    lda take_skip
    sta take_verify_cursor
    stz take_verify_index
@compare:
    lda take_verify_cursor
    cmp take_limit
    bne :+
    jsr take_verify_read
:
    ldx take_verify_cursor
    lda map_buffer,x
    ldx take_verify_index
    cmp take_descriptor,x
    bne take_changed
    inc take_verify_cursor
    inc take_verify_index
    lda take_verify_index
    cmp #BS_DESC_SIZE
    bne @compare
    pla
    sta reader_sector+1
    pla
    sta reader_sector
    lda #<sector_buffer
    sta dcb+4
    lda #>sector_buffer
    sta dcb+5
    rts
take_verify_read:
    inc take_hops
    lda take_hops
    cmp #34
    bcs take_changed
    lda take_verify_next
    ora take_verify_next+1
    beq take_changed
    lda take_verify_next
    sta reader_sector
    lda take_verify_next+1
    sta reader_sector+1
    lda #<map_buffer
    sta dcb+4
    lda #>map_buffer
    sta dcb+5
    jsr read_sector_status
    tya
    bmi take_changed
    lda map_buffer+255
    beq take_changed
    cmp #254
    bcs take_changed
    sta take_limit
    lda map_buffer+254
    sta take_verify_next
    lda map_buffer+253
    sta take_verify_next+1
    stz take_verify_cursor
    rts
take_changed:
    lda #$cd
    jmp reader_failed
take_verify_next: .word 0
take_skip: .word 0
take_limit: .byte 0
take_verify_cursor: .byte 0
take_verify_index: .byte 0
take_hops: .byte 0
