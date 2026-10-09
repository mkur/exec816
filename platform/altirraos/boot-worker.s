; Console admission already blocks ROM calls, but its display/input claim has
; not begun. Append the worker milestone directly to the ROM text screen, and
; update the cursor that Claim/Adopt will consume. No gateway-policy exception.
; boot_report owns IRQ masking, the private text buffer [$80], and its length
; at $84. This bounded copy masks NMI across screen/cursor updates; normal boot
; has enabled VBI ($40). No Task switch, allocation or ROM service is involved.
.segment "SIGNAL_CODE"
.a16
.i16
boot_worker_line:
    lda f:E816_BOOT_SCREEN
    cmp #$9000
    jcc @done
    cmp #$bc41
    jcs @done
    sta $8e
    lda f:$0054
    and #$ff
    cmp #24
    jcs @done
    ; Derive the current row, rather than trusting the OS cursor column.
    asl a
    asl a
    asl a
    sta $90
    asl a
    asl a
    clc
    adc $90
    adc $8e
    sta $86
    sep #$20
    stz $88
    lda #0
    sta f:NMIEN
    rep #$20
    lda f:$005e
    cmp $8e
    bcc @copy
    sec
    sbc $8e
    cmp #960
    bcs @copy
    lda f:$005e
    sta $8a
    sep #$20
    stz $8c
    lda f:$005d
    sta [$8a]
    rep #$20
@copy:
    ldy #0
    sep #$20
@letter:
    lda [$80],y
    cmp #96
    bcs :+
    sec
    sbc #32
:
    sta [$86],y
    iny
    cpy $84
    bcc @letter
    lda f:$0054
    cmp #23
    beq @scroll
    inc a
    sta f:$0054
    rep #$20
    lda $86
    clc
    adc #40
    bra @cursor
@scroll:
    rep #$20
    lda $8e
    sta $86
    clc
    adc #40
    sta $8a
    sep #$20
    stz $8c
    ldy #0
@row:
    lda [$8a],y
    sta [$86],y
    iny
    cpy #920
    bcc @row
    lda #0
@blank:
    sta [$86],y
    iny
    cpy #960
    bcc @blank
    rep #$20
    lda $8e
    clc
    adc #920
@cursor:
    sta f:$005e
    sta $86
    lda #0
    sta f:$0055
    sep #$20
    lda [$86]
    sta f:$005d
    lda f:$02f0
    bne :+
    lda [$86]
    eor #$80
    sta [$86]
:
    lda #$40
    sta f:NMIEN
@done:
    rep #$30
    rtl

; An ordinary successful root return is not a kernel startup failure.
; This terminal transfer still uses no stack until prepare establishes it.
boot_finish_check:
    lda f:STATUS
    bne @prepare
    lda f:E816_BOOT_PHASE
    and #$ff
    cmp #DIAG_PHASE_ACTIVE
    bne @prepare
    sep #$20
    lda #0
    sta f:E816_BOOT_PHASE
    rep #$20
@prepare:
    jml boot_finish_prepare
