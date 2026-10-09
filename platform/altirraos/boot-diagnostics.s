; Boot-only OS-screen tracing. Reuse the reserved upper blitter code arena.
; No new bank-zero state. CIO uses a private 24-byte native-stack text buffer;
; OS_BUSY suppresses switching throughout the page-one ROM activation.
.include "boot-config.inc"
.segment "BLITTER_CODE"
.export boot_report,boot_report_end,boot_record,boot_record_end
.export boot_display_report,boot_display_report_end
.export boot_active,boot_active_end,boot_complete,boot_complete_end
.export boot_abort,boot_abort_end
.a16
.i16
boot_active:
    lda f:E816_BOOT_PHASE
    and #$ff
    cmp #DIAG_PHASE_ACTIVE
    beq :+
    lda #0
    rtl
:
    lda #1
    rtl
boot_active_end:

boot_complete:
    lda f:E816_BOOT_PHASE
    and #$ff
    cmp #DIAG_PHASE_ACTIVE
    bne :+
    sep #$20
    lda #0
    sta f:E816_BOOT_PHASE
    rep #$20
:
    rtl
boot_complete_end:

boot_abort:
    lda 4,s
    jml finish
boot_abort_end:

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
    bcc @stage_test
    cmp #DIAG_FAILURE_LAST+1
    bcc @enabled
@stage_test:
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
    cmp #DIAG_ADOPT
    beq @status
    cmp #DIAG_TASK_INIT
    beq @status
    cmp #DIAG_VBI_IRQ
    beq @status
    cmp #DIAG_WORKER
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
    sep #$20
    lda #'1'
    sta [$80],y
    iny
    lda #'.'
    sta [$80],y
    iny
    rep #$20
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
    lda 32,s
    cmp #DIAG_WORKER
    bne :+
    tya
    dec a                   ; omit the ATASCII newline; helper advances a row
    sta $84
    jsl boot_worker_line
    jmp @free
:
    ; Preserve the IOCB0 command/status, buffer and length, including on error.
    ; Use the retained console's column zero while preserving OS margins.
    lda f:$0052
    pha
    lda #$2700
    sta f:$0052
    lda #0
    sta f:$0055
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
    pla
    sta f:$0052
    sep #$20
    lda #0
    sta f:OS_BUSY
    rep #$20
@free:
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

; Terminal entry abandons the caller stack before pushing any return address.
; Spare adapter-state bytes retain the first cause even if shutdown requires
; a reset. No allocation, ROM entry or worker IPC belongs in this path.
.segment "SIGNAL_CODE"
.a16
.i16
boot_finish_prepare:
    lda f:E816_BOOT_PHASE
    and #$ff
    cmp #DIAG_PHASE_ACTIVE
    bne :+
    lda f:STATUS
    sta f:E816_BOOT_CAUSE
    sep #$20
    lda #DIAG_PHASE_FAILED
    sta f:E816_BOOT_PHASE
    rep #$20
:
    lda #E816_KERNEL_DP
    tcd
    lda #E816_KERNEL_STACK_TOP-1
    tcs
    cld
    jml finish_prepared

; Also handles direct reset-required entries which never passed finish.
boot_reset_prepare:
    lda f:E816_BOOT_PHASE
    and #$ff
    cmp #DIAG_PHASE_ACTIVE
    bne :+
    lda #$ff93
    sta f:E816_BOOT_CAUSE
    sep #$20
    lda #DIAG_PHASE_FAILED
    sta f:E816_BOOT_PHASE
    rep #$20
:
    lda #E816_KERNEL_DP
    tcd
    lda #E816_KERNEL_STACK_TOP-1
    tcs
    cld
    jsl boot_failure_line
    jml reset_park

; IRQ/NMI are disabled and D/S belong to the kernel. Print on the final OS row,
; after screen restoration. Never hand a live DMA/bus owner back to the OS.
.export boot_failure_line,boot_failure_line_end
boot_failure_line:
    lda f:E816_BOOT_PHASE
    and #$ff
    cmp #DIAG_PHASE_FAILED
    jne @done
    sep #$20
    lda #DIAG_PHASE_REPORTED
    sta f:E816_BOOT_PHASE
    rep #$20
    lda f:E816_BOOT_SCREEN
    cmp #$9000
    jcc @done
    cmp #$bc41
    jcs @done
    clc
    adc #920
    sta $80
    sep #$20
    stz $82
    lda f:DISPLAY_KIND
    cmp #2
    bne :+
    rep #$20
    lda f:BV_PAGE_OFFSET
    tax
    sep #$20
    lda #0
    sta f:$d640,x            ; disable FX scanout; DMA/storage remain owned
:
    rep #$20
    lda f:E816_BOOT_LIST
    sta f:$0230
    sta f:$d402
    sep #$20
    lda f:E816_BOOT_DMA
    sta f:$022f
    sta f:$d400
    lda #1
    sta f:$02f0             ; keep the OS cursor from covering the fatal line
    lda #0
    ldy #39
@clear:
    sta [$80],y
    dey
    bpl @clear
    ldy #0
    ldx #0
@label:
    lda f:boot_halted_text,x
    beq @code
    cmp #96
    bcs :+
    sec
    sbc #32
:
    sta [$80],y
    iny
    inx
    bra @label
@code:
    rep #$20
    lda f:E816_BOOT_CAUSE
    sta $84
    ldx #4
@digit:
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
    sec
    sbc #32
    sta [$80],y
    iny
    rep #$20
    plx
    asl $84
    asl $84
    asl $84
    asl $84
    dex
    bne @digit
@done:
    rep #$30
    rtl
boot_failure_line_end:
boot_halted_text: .byte "System halted: $",0
