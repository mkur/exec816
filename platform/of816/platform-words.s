.include "boot-config.inc"

; Requested capacity in 128-byte blocks; Exec allocates after the handoff.
dword CACHE_BLOCKS_FETCH,"CACHE-BLOCKS@"
    lda f:B_ADDRESS+B_FIELD_CACHE_BLOCKS
    tay
    lda #0
    PUSHNEXT
eword

; Validate the full unsigned Forth cell before changing the boot record.
dword CACHE_BLOCKS_STORE,"CACHE-BLOCKS!"
    jsr _popay
    cmp #0
    bne invalid
    tya
    beq store
    cmp #B_MIN_BLOCKS
    bcc invalid
    cmp #B_MAX_BLOCKS+1
    bcs invalid
    ; Y holds n, so n & (n-1) admits exactly powers of two.
    dec a
    pha
    tya
    and 1,s
    beq valid
    pla
    bra invalid
valid:
    pla
    tya
store:
    sta f:B_ADDRESS+B_FIELD_CACHE_BLOCKS
    NEXT
invalid:
    lda #.hiword(-24)
    ldy #.loword(-24)
    jmp _throway
eword

; Requested system drive, independent of whether media has mounted yet.
dword SYSTEM_DRIVE_FETCH,"SYSTEM-DRIVE@"
    lda f:B_ADDRESS+B_FIELD_SYSTEM_DRIVE
    and #$00ff
    tay
    lda #0
    PUSHNEXT
eword

; A full-cell range check precedes the generated unit/alias conflict mask.
dword SYSTEM_DRIVE_STORE,"SYSTEM-DRIVE!"
    jsr _popay
    cmp #0
    bne invalid
    tya
    beq invalid
    cmp #9
    bcs invalid
    phy
    lda #B_ALLOWED_DRIVES
shift:
    lsr a
    dey
    bne shift
    ply
    bcc invalid
    tya
    sep #$20
    sta f:B_ADDRESS+B_FIELD_SYSTEM_DRIVE
    rep #$20
    NEXT
invalid:
    lda #.hiword(-24)
    ldy #.loword(-24)
    jmp _throway
eword

; Retire the monitor and resume the paused XEX/cartridge reader with RTS.
dword EXEC816_BOOT,"EXEC816"
    jml of_handoff
eword
