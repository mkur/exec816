; Boot-only, read-only SDFS/256 and XEX transport. No Exec or DOS is live yet.
; Private absolute storage survives INITAD, including OF816's nested OS calls.
.setcpu "65816"
.macpack longbranch
.include "boot-atr.inc"
.include "boot-sio-defs.inc"
.ifndef BOOT_BACKEND
BOOT_BACKEND=0
.endif
.ifndef BOOT_FAST
BOOT_FAST=0
.endif
.ifndef BOOT_POLICY
BOOT_POLICY=0
.endif
.ifndef BOOT_NATIVE_DIVISOR
BOOT_NATIVE_DIVISOR=40
.endif
.ifndef BOOT_LOCAL0
BOOT_LOCAL0=0
BOOT_LOCAL1=0
BOOT_LOCAL2=0
.endif
.segment "CODE"
.a8
.i8
.export reader_start,reader_failed,reader_run,reader_callback,reader_error,reader_park
.export reader_phase,reader_sector,file_offset,reader_callbacks,reader_reads
.export reader_guard_low,reader_guard_high,reader_end
reader_guard_low: .res GUARD_BYTES,$a5
reader_start:
.if BOOT_BACKEND=0
    cld
.if BOOT_FAST
    jsr boot_select_speed
.endif
    lda #1
    sta reader_phase
    lda #1
    sta reader_sector
    stz reader_sector+1
    jsr read_sector
    lda sector_buffer+1
    cmp #3
    jne bad_header
    lda sector_buffer+32
    cmp #$21
    jne bad_header
    lda sector_buffer+31
    ora sector_buffer+33
    ora sector_buffer+36
    jne bad_header
    lda sector_buffer+34
    cmp #1
    jne bad_header
    lda sector_buffer+35
    cmp #126
    jne bad_header
    lda sector_buffer+37
    cmp #1
    jne bad_header
    lda sector_buffer+11
    cmp #<SECTORS
    jne bad_header
    lda sector_buffer+12
    cmp #>SECTORS
    jne bad_header
    lda sector_buffer+9
    sta file_map
    lda sector_buffer+10
    sta file_map+1
    ; Read record zero to obtain the directory's authoritative 24-bit length.
    lda #$ff
    sta file_left
    sta file_left+1
    sta file_left+2
    lda #2
    sta reader_phase
    jsr open_map
    jsr read_row
    sec
    lda row+3
    sbc #23
    sta file_left
    lda row+4
    sbc #0
    sta file_left+1
    lda row+5
    sbc #0
    sta file_left+2
    jcc bad_chain
find_file:
    lda file_left
    ora file_left+1
    ora file_left+2
    jeq missing_file
    jsr read_row
    lda row
    jeq missing_file
    and #$b8
    cmp #8
    bne find_file
    ldx #10
@name:
    lda row+6,x
    cmp kernel_name,x
    bne find_file
    dex
    bpl @name
    lda row+1
    sta file_map
    lda row+2
    sta file_map+1
    ldx #2
@length:
    lda row+3,x
    sta file_left,x
    dex
    bpl @length
    jsr open_map
.else
.include "boot-takeover.inc"
.endif
.include "boot-xex.inc"

; Sequential SDFS stream. A zero map cursor advances the map, with backlink
; validation and a sector-count bound. The buffered byte cursor survives calls.
open_map:
    stz file_offset
    stz file_offset+1
    stz file_offset+2
    stz map_previous
    stz map_previous+1
    stz buffer_valid
    stz map_hops
    stz map_hops+1
load_map:
    lda file_map
    sta reader_sector
    lda file_map+1
    sta reader_sector+1
    jsr check_sector
    jsr read_sector
    lda sector_buffer+2
    cmp map_previous
    jne bad_chain
    lda sector_buffer+3
    cmp map_previous+1
    jne bad_chain
    ldx #0
@copy:
    lda sector_buffer,x
    sta map_buffer,x
    inx
    bne @copy
    inc map_hops
    bne :+
    inc map_hops+1
:
    lda map_hops+1
    cmp #>SECTORS
    jcs bad_chain
    lda #4
    sta map_cursor
    rts
read_row:
    stz row_cursor
@byte:
    jsr get_byte
    ldx row_cursor
    sta row,x
    inc row_cursor
    lda row_cursor
    cmp #23
    bne @byte
    rts
read_word:
    jsr get_byte
    sta word
    jsr get_byte
    sta word+1
    rts
get_byte:
    lda file_left
    ora file_left+1
    ora file_left+2
    jeq truncated
    lda buffer_valid
    bne @buffered
.if BOOT_BACKEND=1
    lda file_map
    ora file_map+1
    jeq truncated
    lda file_map
    sta reader_sector
    lda file_map+1
    sta reader_sector+1
    jsr check_sector
    jsr read_sector
    lda sector_buffer+255
    jeq bad_chain
    cmp #254
    jcs bad_chain
    sta buffer_limit
    lda sector_buffer+254
    sta file_map
    lda sector_buffer+253
    sta file_map+1
    cmp reader_sector+1
    bne :+
    lda file_map
    cmp reader_sector
    jeq bad_chain
:
    stz buffer_cursor
    lda #1
    sta buffer_valid
    bra @buffered
.else
    lda map_cursor
    bne @pointer
    lda file_map
    sta map_previous
    lda file_map+1
    sta map_previous+1
    lda map_buffer
    sta file_map
    lda map_buffer+1
    sta file_map+1
    jsr load_map
@pointer:
    ldx map_cursor
    lda map_buffer,x
    sta reader_sector
    lda map_buffer+1,x
    sta reader_sector+1
    jsr check_sector
    jsr read_sector
    inc map_cursor
    inc map_cursor
    stz buffer_cursor
    lda #1
    sta buffer_valid
.endif
@buffered:
    lda file_left
    bne :+
    lda file_left+1
    bne @borrow
    dec file_left+2
@borrow:
    dec file_left+1
:
    dec file_left
    inc file_offset
    bne :+
    inc file_offset+1
    bne :+
    inc file_offset+2
:
    ldx buffer_cursor
    lda sector_buffer,x
    inc buffer_cursor
.if BOOT_BACKEND=1
    ldx buffer_cursor
    cpx buffer_limit
    bne :+
.else
    bne :+
.endif
    stz buffer_valid
:
    rts
check_sector:
.if BOOT_BACKEND=1
    lda reader_sector+1
    bne @ok
    lda reader_sector
    cmp #4
    jcc bad_chain
@ok:
    rts
.else
    lda reader_sector+1
    cmp #>SECTORS
    bcc @lower
    jne bad_chain
    lda reader_sector
    jne bad_chain
    rts
@lower:
    cmp #0
    bne @ok
    lda reader_sector
    cmp #4
    jcc bad_chain
@ok:
    rts
.endif
read_sector:
    lda $11
    jeq cancelled
    jsr read_sector_status
    tya
    cmp #$80
    jeq cancelled
    tya
    jmi reader_failed
    inc reader_reads
    bne :+
    inc reader_reads+1
:
    rts
read_sector_status:
    ldx #11
@dcb:
    lda dcb,x
    sta $0300,x
    dex
    bpl @dcb
    lda reader_sector
    sta $030a
    lda reader_sector+1
    sta $030b
    lda dcb+2
    cmp #$52
    bne @transfer
    lda reader_sector+1
    cmp #0
    bne :+
    lda reader_sector
    cmp #4
    bcs :+
    lda #128
    sta $0308
    stz $0309
:
@transfer:
.if BOOT_FAST
    jsr bo_transfer
.else
    jsr $e459
.endif
    rts
.if BOOT_FAST
.include "boot-sio.inc"
.include "boot-sio-policy.inc"
.endif
.if !BOOT_FAST
boot_select_speed:
    rts
.endif
check_guards:
    ldx #GUARD_BYTES-1
@guard:
    lda reader_guard_low,x
    cmp #$a5
    jne bad_guard
    lda reader_guard_high,x
    cmp #$a5
    jne bad_guard
    dex
    bpl @guard
    rts
bad_header:  lda #$c1
    bra reader_failed
bad_chain:   lda #$c2
    bra reader_failed
missing_file: lda #$c3
    bra reader_failed
truncated:   lda #$c4
    bra reader_failed
bad_segment: lda #$c5
    bra reader_failed
bad_guard:   lda #$c7
    bra reader_failed
cancelled:   lda #$c8
reader_failed:
.if BOOT_BACKEND=1
    ldx take_selected
    bne :+
    jmp take_return
:
.endif
    sta reader_error
    lda #$ff
    sta $11                   ; report a canceled boot through E: after BREAK
    lda reader_error
    ldx #0
    jsr hex_byte
    lda reader_phase
    ldx #3
    jsr hex_byte
    lda reader_sector+1
    ldx #6
    jsr hex_byte
    lda reader_sector
    ldx #8
    jsr hex_byte
    lda file_offset+2
    ldx #11
    jsr hex_byte
    lda file_offset+1
    ldx #13
    jsr hex_byte
    lda file_offset
    ldx #15
    jsr hex_byte
    lda #11
    sta $0342
    lda #<message
    sta $0344
    lda #>message
    sta $0345
    lda #message_end-message
    sta $0348
    stz $0349
    ldx #0
    jsr $e456
reader_park:
    jmp reader_park
hex_byte:
    pha
    lsr
    lsr
    lsr
    lsr
    jsr hex_digit
    pla
    and #15
hex_digit:
    tay
    lda hex,y
    sta details,x
    inx
    rts
dcb:
    .byte $31,1,$52,$40
    .word sector_buffer
    .byte 3,0
    .word SECTOR_BYTES
    .word 0
kernel_name: .byte "EXEC816 XEX"
hex: .byte "0123456789ABCDEF"
message: .byte $9b,"Exec disk boot failed: "
details: .byte "00 00 0000 000000",$9b,"error phase sector offset; cold reset",$9b
message_end:
reader_error: .byte 0
reader_phase: .byte 0
reader_sector: .word 0
reader_callbacks: .word 0
reader_reads: .word 0
file_offset: .res 3,0
file_left: .res 3,0
file_map: .word 0
map_previous: .word 0
map_hops: .word 0
map_cursor: .byte 0
buffer_valid: .byte 0
buffer_cursor: .byte 0
buffer_limit: .byte 0
row_cursor: .byte 0
row: .res 23,0
word: .word 0
segment_left: .word 0
    .align 256
map_buffer: .res 256,0
sector_buffer: .res 256,0
reader_end:
.assert * <= READER_ADDRESS+READER_BYTES-GUARD_BYTES,error,"Boot reader exceeds borrowed arena"
    .res READER_BYTES-GUARD_BYTES-(*-reader_guard_low),0
reader_guard_high: .res GUARD_BYTES,$a5
