; Boot-only OS-screen tracing. Reuse the reserved upper blitter code arena.
; No new bank-zero state. CIO uses a private 24-byte native-stack text buffer;
; OS_BUSY suppresses switching throughout the page-one ROM activation.
.include "boot-config.inc"
.segment "BLITTER_CODE"
.export boot_report,boot_report_end,boot_record,boot_record_end
.export boot_display_report,boot_display_report_end
.a16
.i16
boot_record:
    lda 6,s
    tax
    lda 4,s
    jsl boot_report
    rtl
boot_record_end:

boot_display_report:
    lda 4,s
    tax
    lda 8,s
    jsl boot_report
    rtl
boot_display_report_end:

; Read-only boot inventory, including kernels using the standard console.
; Task initialization has cleared the driver's mailbox before this entry.
boot_vbxe_probe:
    jsl blitter_base
    tax
    lda #DIAG_VBXE_BASE
    jsl boot_report
    cpx #0
    beq @done
    txa
    sec
    sbc #$d600
    tax
    phx
    lda f:$d640,x
    xba
    tax
    lda #DIAG_VBXE_CORE
    jsl boot_report
    plx
    sep #$20
    lda f:$d641,x
    rep #$20
    and #$ff
    tax
    lda #DIAG_VBXE_REVISION
    jsl boot_report
@done:
    rtl

; Register entry: A=event, X=value. Preserve the complete native context.
boot_report:
    php
    sei
    save_full
    cmp #DIAG_FAILURE_FIRST
    bcs @enabled
    cmp #DIAG_ADOPT
    beq @stage
    cmp #DIAG_TASK_INIT
    bne @verbosity
@stage:
    cpx #0
    bne @enabled             ; a failed stage remains visible in quiet mode
@verbosity:
    sep #$20
    lda f:B_ADDRESS+B_FIELD_FLAGS
    and #B_FLAG_VERBOSE
    rep #$20
    bne @enabled
    jmp @restore
@enabled:
    tsc
    sec
    sbc #24
    tcs
    inc a
    sta $80
    sep #$20
    stz $82
    rep #$20
    lda 32,s                 ; saved event, above the private buffer
    asl a
    asl a
    asl a
    asl a
    tax
    ldy #0
    sep #$20
@label:
    lda f:boot_labels,x
    beq @value
    sta [$80],y
    iny
    inx
    bra @label
@value:
    rep #$20
    lda 30,s                 ; saved X=value
    sta $84
    lda 32,s
    cmp #DIAG_HALTED
    bne :+
    jmp @newline
:
    cmp #DIAG_ADOPT
    beq @status
    cmp #DIAG_TASK_INIT
    beq @status
    cmp #DIAG_VBXE_REVISION
    beq @revision
    sep #$20
    lda #'$'
    sta [$80],y
    iny
    rep #$20
    ldx #4
    bra @digits
@revision:
    lda $84
    and #$7f
    xba
    sta $84
    ldx #2
@digits:
    lda $84
    xba
    lsr a
    lsr a
    lsr a
    lsr a
    and #$f
    phx
    tax
    sep #$20
    lda f:boot_hex,x
    sta [$80],y
    iny
    rep #$20
    plx
    asl $84
    asl $84
    asl $84
    asl $84
    dex
    bne @digits
    lda 32,s
    cmp #DIAG_VBXE_REVISION
    bne @newline
    lda 30,s
    and #$80
    sep #$20
    beq @a
    lda #'r'
    bra @suffix
@a:
    lda #'a'
@suffix:
    sta [$80],y
    iny
    bra @newline
@status:
    ldx #0
    lda 30,s
    beq @status_copy
    ldx #3                  ; skip the zero-terminated OK string
@status_copy:
    sep #$20
    lda f:boot_status,x
    beq @newline
    sta [$80],y
    iny
    inx
    bra @status_copy
@newline:
    sep #$20
    lda #$9b
    sta [$80],y
    iny
    rep #$20
    ; Preserve the IOCB0 command/status, buffer and length, including on error.
    lda f:$0342
    pha
    lda f:$0344
    pha
    lda f:$0348
    pha
    tya
    sta f:$0348
    lda $80
    sta f:$0344
    sep #$20
    lda #11
    sta f:$0342
    lda #1
    sta f:OS_BUSY
    rep #$20
    tsc
    tax
    and #$ff00
    cmp #$0100
    beq @os_stack
    lda #OS_STACK_TOP
    tcs
@os_stack:
    phx
    lda #0
    tcd
    pea 0
    plb
    plb
    ldx #0
    pea CIOV
    cli
    cop $00
    sei
    rep #$30
    pla                      ; ROM target
    pla                      ; native S
    tcs
    pla
    sta f:$0348
    pla
    sta f:$0344
    pla
    sta f:$0342
    sep #$20
    lda #0
    sta f:OS_BUSY
    rep #$20
    tsc
    clc
    adc #24
    tcs
@restore:
    restore_full
    plp
    rtl
boot_report_end:
boot_hex: .byte "0123456789ABCDEF"
boot_status: .byte "OK",0,"FAILED",0
.include "boot-labels.inc"
