; Boot-only OS-screen tracing in existing upper code/data arenas.
; No new bank-zero state. CIO uses a private 40-byte native-stack text buffer;
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

BOOT_LINE_BYTES = 40
BOOT_DIAG_FORCE = $8000
BOOT_DIAG_UNAVAILABLE = $4000
BOOT_DIAG_NO_NMI = $2000
BOOT_DIAG_EVENT_MASK = $1fff

; Register entry: A=event, X=value; CRC events take Y=high word.
; Private FORCE/UNAVAILABLE bits do not change the public event numbers.
; Preserve complete native register context. D-relative $80-$90 is scratch.
boot_report:
    php
    sei
    save_full
    bit #BOOT_DIAG_FORCE
    jne @enabled
    and #BOOT_DIAG_EVENT_MASK
    cmp #DIAG_IDENTITY
    jeq @enabled
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
    bne @enabled
@verbosity:
    sep #$20
    lda f:B_ADDRESS+B_FIELD_FLAGS
    and #B_FLAG_VERBOSE
    rep #$20
    jne @enabled
    jmp @restore
@enabled:
    tsc
    sec
    sbc #BOOT_LINE_BYTES
    tcs
    inc a
    sta $80
    sep #$20
    stz $82
    rep #$20
    lda BOOT_LINE_BYTES+8,s
    and #BOOT_DIAG_EVENT_MASK
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
    lda BOOT_LINE_BYTES+8,s
    bit #BOOT_DIAG_UNAVAILABLE
    jne @unavailable
    and #BOOT_DIAG_EVENT_MASK
    cmp #DIAG_IDENTITY
    jeq @identity
    cmp #DIAG_ROM_PROFILE
    jeq @profile
    lda BOOT_LINE_BYTES+6,s
    tax
    stx $84
    stz $86
    lda BOOT_LINE_BYTES+8,s
    and #BOOT_DIAG_EVENT_MASK
    cmp #DIAG_ADOPT
    jeq @status
    cmp #DIAG_TASK_INIT
    jeq @status
    cmp #DIAG_VBI_IRQ
    jeq @status
    cmp #DIAG_WORKER
    jeq @status
    cmp #DIAG_SDX_ROM
    bne :+
    cpx #0
    jeq @status
:
    cmp #DIAG_VBXE_REVISION
    jeq @revision
    cmp #DIAG_ROM_CRC
    beq @crc
    cmp #DIAG_ROM_LOW
    bcc @word
    cmp #DIAG_ROM_HIGH+1
    bcs @word
@crc:
    lda BOOT_LINE_BYTES+4,s
    sta $84                 ; high word, rendered first
    stx $86                 ; low word, shifted through the high word
    ldx #8
    bra @hex
@word:
    ldx #4
@hex:
    sep #$20
    lda #'$'
    sta [$80],y
    iny
    rep #$20
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
    .repeat 4
        asl $86
        rol $84
    .endrepeat
    dex
    bne @digits
    lda BOOT_LINE_BYTES+8,s
    and #BOOT_DIAG_EVENT_MASK
    cmp #DIAG_SDX_ROM
    jeq @reason
    cmp #DIAG_VBXE_REVISION
    jne @newline
    lda BOOT_LINE_BYTES+6,s
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
    jmp @newline
@status:
    ldx #0
    lda BOOT_LINE_BYTES+6,s
    beq @status_copy
    ldx #3
@status_copy:
    sep #$20
    lda f:boot_status,x
    beq @newline
    sta [$80],y
    iny
    inx
    bra @status_copy
@identity:
    lda BOOT_LINE_BYTES+6,s
    tax
    sep #$20
@identity_copy:
    lda f:boot_identity_text,x
    beq @newline
    sta [$80],y
    iny
    inx
    bra @identity_copy
@unavailable:
    ldx #0
    sep #$20
@unavailable_copy:
    lda f:boot_unavailable,x
    beq @newline
    sta [$80],y
    iny
    inx
    bra @unavailable_copy
@profile:
    rep #$20
    lda BOOT_LINE_BYTES+6,s
    cmp #BOOT_ROM_PROFILE_COUNT
    bcc :+
    lda #0
:
    asl a
    tax
    lda f:boot_rom_profile_offsets,x
    tax
    sep #$20
@profile_copy:
    lda f:boot_rom_profile_text,x
    beq @newline
    sta [$80],y
    iny
    inx
    bra @profile_copy
@reason:
    rep #$20
    lda BOOT_LINE_BYTES+6,s
    cmp #4
    bcc :+
    lda #0
:
    asl a
    tax
    lda f:boot_rom_result_offsets,x
    tax
    sep #$20
    lda #' '
    sta [$80],y
    iny
@reason_copy:
    lda f:boot_rom_result_text,x
    beq @newline
    sta [$80],y
    iny
    inx
    bra @reason_copy
@newline:
    sep #$20
    lda #$9b
    sta [$80],y
    iny
    rep #$20
    lda BOOT_LINE_BYTES+8,s
    and #BOOT_DIAG_EVENT_MASK
    cmp #DIAG_WORKER
    beq @direct
    cmp #DIAG_ROM_CRC
    bcc @cio
    cmp #DIAG_ROM_PORTB+1
    bcs @cio
@direct:
    ; ROM diagnostics also use this bounded writer. Mapping rejection must
    ; never call the ROM whose visibility is in question. Startup owns the
    ; saved OS screen and normal VBI enable ($40), as does the worker event.
    tya
    dec a
    sta $84
    ldx #$40
    lda BOOT_LINE_BYTES+8,s
    bit #BOOT_DIAG_NO_NMI
    beq :+
    ldx #0
:
    jsl boot_worker_line
    jmp @free
@cio:
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
    pla
    pla
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
    adc #BOOT_LINE_BYTES
    tcs
@restore:
    restore_full
    plp
    rtl
boot_report_end:

; Keep tables in spare existing native-code capacity rather than enlarge the
; blitter reservation. Every table reference is explicitly long-addressed.
.segment "NATIVE_WORK"
boot_hex: .byte "0123456789ABCDEF"
boot_status: .byte "OK",0,"FAILED",0
boot_unavailable: .byte "UNAVAILABLE",0
boot_rom_result_offsets:
    .word 0,6,14,22
boot_rom_result_text: .byte "ERROR",0,"MAPPING",0,"UNKNOWN",0,"ALREADY INSTALLED",0
.include "boot-labels.inc"
.include "boot-build.inc"
.include "generated/sdx-firmware-labels.inc"
.export boot_identity,boot_identity_end
.a16
.i16
boot_identity:
    php
    sei
    save_full
    ldy #0
@line:
    tyx
    lda f:boot_identity_offsets,x
    tax
    lda #DIAG_IDENTITY
    jsl boot_report
    iny
    iny
    cpy #BOOT_IDENTITY_LINES*2
    bcc @line
    restore_full
    plp
    rtl
boot_identity_end:

.if SDX_ENABLED
    .include "boot-rom-diagnostics.s"
.endif

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
