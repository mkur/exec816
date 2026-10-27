; Startup-only diagnostics after the SDX installer returns. A is its unchanged
; result. IRQs are already masked; install returned with normal VBI enabled.
; Print directly to the saved OS screen, without entering unknown ROM/mapping.
; Keep NMI off across this block; only a successful install resumes VBI.
; All bytes fit existing SDX upper code capacity. D-relative $80-$90 is scratch.
.segment "SDX_WORK"
.export boot_rom_diagnostics,boot_rom_diagnostics_end,boot_rom_crc_range
.a16
.i16
.macro boot_rom_event event
    lda #event|BOOT_DIAG_FORCE|BOOT_DIAG_NO_NMI
    jsl boot_report
.endmacro

boot_rom_diagnostics:
    php
    sei
    save_full
    cmp #0
    bne @report
    lda f:SDX_ROM_PROFILE
    cmp #SDX_ROM_FALLBACK_PROFILE
    beq @report
    lda f:B_ADDRESS+B_FIELD_FLAGS
    and #B_FLAG_VERBOSE
    jeq @done
@report:
    sep #$20
    lda #0
    sta f:NMIEN
    rep #$20
    lda 8,s
    cmp #0
    beq @captured
    boot_rom_event DIAG_ROM_CRC|BOOT_DIAG_UNAVAILABLE
    boot_rom_event DIAG_ROM_PROFILE|BOOT_DIAG_UNAVAILABLE
    bra @result
@captured:
    lda f:SDX_ROM_CRC
    tax
    lda f:SDX_ROM_CRC+2
    tay
    boot_rom_event DIAG_ROM_CRC
    lda f:SDX_ROM_PROFILE
    tax
    boot_rom_event DIAG_ROM_PROFILE
@result:
    lda 8,s
    tax
    boot_rom_event DIAG_SDX_ROM
    lda 8,s
    cmp #1
    beq @mapping
    cmp #0
    bne @resume
    lda f:SDX_ROM_PROFILE
    cmp #SDX_ROM_FALLBACK_PROFILE
    bne @resume
    lda f:SDX_ROM_IMAGE+$3ffa
    tax
    boot_rom_event DIAG_ROM_NMI
    lda f:SDX_ROM_IMAGE+$3ffe
    tax
    boot_rom_event DIAG_ROM_IRQ
    ; Section CRCs distinguish math-pack overlays from other visible changes.
    ; Read the captured snapshot, never registers or the now-shadowed vectors.
    ldx #0
    lda #$1000
    jsl boot_rom_crc_range
    boot_rom_event DIAG_ROM_LOW
    ldx #$1800
    lda #$2000
    jsl boot_rom_crc_range
    boot_rom_event DIAG_ROM_MATH
    ldx #$2000
    lda #$4000
    jsl boot_rom_crc_range
    boot_rom_event DIAG_ROM_HIGH
    bra @resume
@mapping:
    lda f:$00d303
    and #$ff
    tax
    boot_rom_event DIAG_ROM_PBCTL
    lda f:$00d301
    and #$ff
    tax
    boot_rom_event DIAG_ROM_PORTB
@resume:
    lda 8,s
    bne @done                ; terminal failure retains NMI exclusion
    sep #$20
    lda #$40
    sta f:NMIEN
    rep #$20
@done:
    restore_full
    plp
    rtl
boot_rom_diagnostics_end:

; X=start offset, A=exclusive end; return X=CRC low, Y=CRC high.
; Same reflected CRC-32/ISO-HDLC table, initial/final XOR as admission.
; $84/$86 is the private accumulator, $88 the end. No global state is added.
boot_rom_crc_range:
    sta $88
    lda #$ffff
    sta $84
    sta $86
@byte:
    sep #$20
    lda f:SDX_ROM_IMAGE,x
    eor $84
    rep #$20
    and #$ff
    asl a
    asl a
    phx
    tax
    lda $85
    eor f:sdx_rom_crc_table,x
    sta $84
    lda $87
    and #$ff
    eor f:sdx_rom_crc_table+2,x
    sta $86
    plx
    inx
    cpx $88
    bcc @byte
    lda $84
    eor #$ffff
    tax
    lda $86
    eor #$ffff
    tay
    rtl
