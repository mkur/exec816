; ROM loads three 128-byte sectors to $3000. SDFS header/locator are host-patched.
; Jump to the second stage before OF816 borrows this first-stage storage.
.setcpu "65816"
.include "boot-atr.inc"
.segment "CODE"
.a8
.i8
.export first_start,first_failed,first_park,first_details
first_image:
    .res $80,0
first_start:
    cld
    ldx #11
@dcb:
    lda dcb,x
    sta $0300,x
    dex
    bpl @dcb
    lda BOOT_ADDRESS+LOCATOR_OFFSET+LOC_FIRST_SECTOR
    sta $030a
    lda BOOT_ADDRESS+LOCATOR_OFFSET+LOC_FIRST_SECTOR+1
    sta $030b
    lda #READER_BYTES/SECTOR_BYTES
    sta remaining
@sector:
    lda #$40
    sta $0303
    jsr $e459
    bmi first_failed
    inc $0305
    inc $030a
    bne :+
    inc $030b
:
    dec remaining
    bne @sector
    ldx #GUARD_BYTES-1
@guard:
    lda READER_ADDRESS,x
    cmp #$a5
    bne first_bad_guard
    lda READER_ADDRESS+READER_BYTES-GUARD_BYTES,x
    cmp #$a5
    bne first_bad_guard
    dex
    bpl @guard
    ; No live reference or return into the first stage survives this jump.
    jmp READER_ENTRY
first_bad_guard:
    ldy #$c7
first_failed:
    tya
    ldx #0
    jsr first_hex
    lda $030b
    ldx #3
    jsr first_hex
    lda $030a
    ldx #5
    jsr first_hex
    lda #$ff
    sta $11
    lda #11
    sta $0342
    lda #<message
    sta $0344
    lda #>message
    sta $0345
    lda #message_end-message
    sta $0348
    lda #0
    sta $0349
    ldx #0
    jsr $e456
first_park:
    jmp first_park
first_hex:
    pha
    lsr
    lsr
    lsr
    lsr
    jsr first_digit
    pla
    and #15
first_digit:
    tay
    lda hex,y
    sta first_details,x
    inx
    rts
hex: .byte "0123456789ABCDEF"
dcb:
    .byte $31,1,$52,$40
    .word READER_ADDRESS
    .byte 3,0
    .word SECTOR_BYTES
    .word 0
remaining: .byte 0
message: .byte $9b,"Exec boot 1: "
first_details: .byte "00 0000; cold reset",$9b
message_end:
.assert * <= BOOT_ADDRESS+BOOT_BYTES,error,"First-stage boot code exceeds three sectors"
    .res BOOT_BYTES-(*-first_image),0
