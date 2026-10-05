; Original SpartaDOS X CIO reader for the matched HELLO timing experiment.
; The host swaps from a separate startup disk to the unchanged demo disk at
; start. All five reads match PROGRAMFILE.Load's 512-byte request boundaries.
.setcpu "6502"
.segment "CODE"
.export start, done, failed, result, ticks, buffer
CIO = $e456
IOCB = $350
buffer = $8000

start:
    cld
    ldx #0
    jsr stamp
    lda #<name
    sta IOCB+4
    lda #>name
    sta IOCB+5
    lda #3
    sta IOCB+2
    lda #4
    sta IOCB+10
    lda #0
    sta IOCB+11
    jsr call
    ldx #3
    jsr stamp
    lda #<buffer
    sta IOCB+4
    lda #>buffer
    sta IOCB+5
    lda #0
    sta IOCB+8
    lda #2
    sta IOCB+9
    lda #4
    sta blocks
read_full:
    lda #7
    sta IOCB+2
    jsr call
    inc IOCB+5
    inc IOCB+5
    dec blocks
    bne read_full
    lda #<(2359-2048)
    sta IOCB+8
    lda #>(2359-2048)
    sta IOCB+9
    lda #7
    sta IOCB+2
    jsr call
    ldx #6
    jsr stamp
    lda #12
    sta IOCB+2
    jsr call
    ldx #9
    jsr stamp
    lda #1
    sta result
done:
    jmp done
call:
    ldx #$10
    jsr CIO
    tya
    bmi failed
    rts
failed:
    sty result
    jmp failed
; Copy the 24-bit OS VBI clock, retrying across its low-byte rollover.
stamp:
    lda $14
    sta ticks+2,x
    lda $13
    sta ticks+1,x
    lda $12
    sta ticks,x
    lda $14
    cmp ticks+2,x
    bne stamp
    rts
name: .byte "D1:C>HELLO",0
blocks: .byte 0
result: .byte 0
ticks: .res 12
