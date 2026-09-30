; Original SDX: one 8192-byte CIO Get Bytes, with passive call/return markers.
; Host swaps to the common benchmark disk at start, before Open.
.setcpu "6502"
.segment "CODE"
.export start, done, failed, result, buffer, read_begin, read_end
CIO = $e456
IOCB = $350
buffer = $8000

start:
    cld
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
    lda #<buffer
    sta IOCB+4
    lda #>buffer
    sta IOCB+5
    lda #0
    sta IOCB+8
    lda #$20
    sta IOCB+9
    lda #7
    sta IOCB+2
    ldx #$10
read_begin:
    jsr CIO
read_end:
    tya
    bmi failed
    lda #12
    sta IOCB+2
    jsr call
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
name: .byte "D1:READ8K.BIN",0
result: .byte 0
