; Emitted boot-only checks against real AltirraOS CIO and VBI.
.setcpu "65816"
.export start,done,failed,before_prepare,after_prepare,result,saved_iocb
.segment "CODE"
.a8
.i8
start:
    cld
    ; Reproduce the BASIC/cart screen allocation through the actual ROM.
    lda #$a0
    sta $6a
    sta $02e4
    jsr open_editor
    lda $02e6
    cmp #$9c
    bne failed
    lda $d301
    and #$fd
    sta $d301
    lda #0
    sta $03f8
    ldx #15
@save:
    lda $0340,x
    sta saved_iocb,x
    dex
    bpl @save
before_prepare:
    jsr boot_platform_prepare
after_prepare:
    lda $d301
    and #2
    beq failed
    lda $6a
    cmp #$c0
    bne failed
    lda $02e6
    cmp #$bc
    bne failed
    lda $02e5
    cmp #$1f
    bne failed
    lda $58
    cmp #$40
    bne failed
    lda $59
    cmp #$bc
    bne failed
    ldx #15
@compare:
    lda $0340,x
    cmp saved_iocb,x
    bne failed
    dex
    bpl @compare
    ; An unrelated inadequate bound must still fail native admission.
    lda #$ff
    sta $02e5
    lda #$bb
    sta $02e6
    jsr boot_platform_prepare
    lda $02e6
    cmp #$bb
    bne failed
    lda $02e5
    cmp #$ff
    bne failed
    lda #1
    sta result
done:
    jmp done
failed:
    lda #$ff
    sta result
    jmp failed
open_editor:
    lda #12
    sta $0342
    ldx #0
    jsr $e456
    lda #3
    sta $0342
    lda #<editor
    sta $0344
    lda #>editor
    sta $0345
    lda #12
    sta $034a
    lda #0
    sta $034b
    ldx #0
    jmp $e456
editor: .byte "E:",0
result: .byte 0
saved_iocb: .res 16,0
.include "boot-platform.inc"
