; Runs under original SpartaDOS, using only documented Atari CIO.
; Each table row: name pointer, 24-bit byte length, pattern seed, zero flag.
.setcpu "6502"
.segment "CODE"
.export start,done,failed,result,job_index,sparse_status
CIO=$e456
IOCB=$350
entry=$80
start:
    cld
    lda #<table
    sta entry
    lda #>table
    sta entry+1
    lda #0
    sta job_index
    sta result
next_job:
    ldy #6
copy_job:
    lda (entry),y
    sta job,y
    dey
    bpl copy_job
    lda job
    ora job+1
    bne :+
    jmp complete
:
    lda job
    sta IOCB+4
    lda job+1
    sta IOCB+5
    lda #3
    sta IOCB+2
    lda #4
    sta IOCB+10
    lda #0
    sta IOCB+11
    sta position
    jsr call
read_loop:
    lda job+2
    ora job+3
    ora job+4
    beq close
    lda #0
    sta IOCB+4
    sta IOCB+8
    sta length
    lda #$90
    sta IOCB+5
    lda #1
    sta IOCB+9
    lda job+3
    ora job+4
    bne request
    lda job+2
    sta IOCB+8
    sta length
    lda #0
    sta IOCB+9
request:
    lda #7
    sta IOCB+2
    ldx #$10
    jsr CIO
    tya
    bpl read_ok
    ; SDX documents sparse gaps as unreadable (135). Exec and Altirra's host
    ; reader deliberately expose zeros instead; retain evidence of the gap.
    ldx job+6
    beq failed
    cpy #135
    bne failed
    sty sparse_status
    jmp close
read_ok:
    ldy #0
verify:
    tya
    eor job+5
    ldx job+6
    beq compare
    lda #0
compare:
    cmp $9000,y
    bne mismatch
    iny
    cpy length
    bne verify
    lda length
    bne tail_done
    lda job+3
    bne :+
    dec job+4
:
    dec job+3
    jmp read_loop
tail_done:
    lda #0
    sta job+2
close:
    lda #12
    sta IOCB+2
    jsr call
    inc job_index
    clc
    lda entry
    adc #7
    sta entry
    bcs :+
    jmp next_job
:
    inc entry+1
    jmp next_job
complete:
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
mismatch:
    ldy #$ff
failed:
    sty result
    jmp failed
job: .res 7
position: .byte 0
length: .byte 0
value: .byte 0
result: .byte 0
job_index: .byte 0
sparse_status: .byte 0
.include "verify-jobs.inc"
