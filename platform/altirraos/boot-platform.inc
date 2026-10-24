; Boot-only emulation-mode preparation for the pinned 64K AltirraOS816 XL.
; Disable internal BASIC before borrowing high RAM. A BASIC/cart cold start
; leaves the mode-0 screen at $9C40; reopen E: through CIO so the ROM moves
; its real display list/screen to $BC20/$BC40 and derives MEMTOP itself.
; Do not raise arbitrary memory limits or turn off an unknown cartridge.
; Caller owns bank zero and A8/X8; registers are scratch, P and IOCB0 survive.
.export boot_platform_prepare
boot_platform_prepare:
    php
    cld
    lda $d301
    ora #2
    sta $d301
    lda #2
    sta $03f8                    ; BASICF follows PORTB's disabled bit
    lda $d013
    sta $03fa                    ; GINTLK follows the actual cartridge line
    bne @done                    ; TRIG3 high means an external cart is mapped
    lda $6a
    cmp #$a0
    bne @done
    lda $02e6
    cmp #$9c
    bne @done
    lda $02e5
    cmp #$1f
    bne @done
    ldx #15
@save:
    lda $0340,x
    pha
    dex
    bpl @save
    lda #12
    sta $0342
    ldx #0
    jsr $e456
    lda #$c0
    sta $6a
    sta $02e4
    lda #3
    sta $0342
    lda #<platform_editor
    sta $0344
    lda #>platform_editor
    sta $0345
    lda #12
    sta $034a
    lda #0
    sta $034b
    ldx #0
    jsr $e456
    ldx #0
@restore:
    pla
    sta $0340,x
    inx
    cpx #16
    bne @restore
@done:
    plp
    rts
platform_editor: .byte "E:",0
