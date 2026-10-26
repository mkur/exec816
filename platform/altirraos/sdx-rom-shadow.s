; Reversible firmware shadow and early emulation IRQ/NMI routing.
;
; The including build supplies disjoint upper-memory SDX_ROM_IMAGE (16 KiB,
; snapshot of CPU-visible ROM), SDX_ROM_BACKUP (14 KiB), SDX_ROM_STATE (2 bytes), and a
; bank-zero SDX_ROM_NMI entry (and optional SDX_ROM_IRQ entry). State byte 0 is ownership; byte 1 saves PORTB.
; Both entries require E=0, M=X=0, decimal clear, I=1, NMIEN=0, DLI disabled,
; no live ROM activation, and code/stack outside the ROM windows. The caller
; owns interrupt exclusion for the entire operation. No DP scratch is used.
; Preserve D/DBR/S; clobber A/X/Y/P. RTL with A=0 success, 1 mapping mismatch,
; 2 unsupported ROM, 3 already installed (or not installed on Remove).
;
; Only $C000-CFFF and $D800-FFFF are copied: $D000-D7FF is hardware, not RAM.
; Original underlying RAM is restored before re-enabling ROM. The ROM file
; is never modified. Cold/warm reset, self-test and third-party PORTB changes
; are outside this component's admitted lifetime.
.export sdx_rom_install, sdx_rom_remove, sdx_rom_end, sdx_rom_identify
.a16
.i16
sdx_rom_install:
    lda f:SDX_ROM_STATE
    and #$00ff
    beq :+
    jmp sdx_rom_state_error
:
    sep #$20
.a8
    lda f:$00d303
    and #$04
    bne :+
    jmp sdx_rom_install_mapping_error
:
    lda f:$00d301
    and #$81
    cmp #$81
    beq :+
    jmp sdx_rom_install_mapping_error
:
    rep #$20
.a16
    ; Capture while the original ROM is mapped. The I/O gap is private
    ; install-only scratch inside the existing snapshot reservation.
    ldx #$0ffe
sdx_rom_capture_low:
    lda f:$00c000,x
    sta f:SDX_ROM_IMAGE,x
    dex
    dex
    bpl sdx_rom_capture_low
    ldx #$27fe
sdx_rom_capture_high:
    lda f:$00d800,x
    sta f:SDX_ROM_IMAGE+$1800,x
    dex
    dex
    bpl sdx_rom_capture_high
    jsl sdx_rom_identify
    cmp #0
    beq :+
    rtl                         ; no mapping or underlying RAM has changed
:
    ; Publish original destinations only while IRQ/NMI are excluded. These
    ; operands stay fixed for the installed lifetime; patched vectors recurse.
    .ifdef SDX_ROM_CHAIN_NMI
        lda f:SDX_ROM_IMAGE+$3ffa
        sta f:SDX_ROM_CHAIN_NMI
    .endif
    .ifdef SDX_ROM_CHAIN_NESTED
        lda f:SDX_ROM_IMAGE+$3ffa
        sta f:SDX_ROM_CHAIN_NESTED
    .endif
    .ifdef SDX_ROM_CHAIN_IRQ
        lda f:SDX_ROM_IMAGE+$3ffe
        sta f:SDX_ROM_CHAIN_IRQ
    .endif
    sep #$20
.a8
    lda f:$00d301
    sta f:SDX_ROM_STATE+1
    and #$fe
    sta f:$00d301
    rep #$20
.a16
    ldx #$0ffe
sdx_rom_copy_low:
    lda f:$00c000,x
    sta f:SDX_ROM_BACKUP,x
    lda f:SDX_ROM_IMAGE,x
    sta f:$00c000,x
    dex
    dex
    bpl sdx_rom_copy_low
    ldx #$27fe
sdx_rom_copy_high:
    lda f:$00d800,x
    sta f:SDX_ROM_BACKUP+$1000,x
    lda f:SDX_ROM_IMAGE+$1800,x
    sta f:$00d800,x
    dex
    dex
    bpl sdx_rom_copy_high
    lda #SDX_ROM_NMI
    sta f:$00fffa
    .ifdef SDX_ROM_IRQ
        lda #SDX_ROM_IRQ
        sta f:$00fffe
    .endif
    sep #$20
.a8
    lda #1
    sta f:SDX_ROM_STATE
    rep #$20
.a16
    lda #0
    rtl
sdx_rom_install_mapping_error:
    rep #$20
.a16
sdx_rom_mapping_error:
    lda #1
    rtl
sdx_rom_image_error:
    lda #2
    rtl
sdx_rom_state_error:
    lda #3
    rtl

sdx_rom_remove:
    lda f:SDX_ROM_STATE
    and #$00ff
    beq sdx_rom_state_error
    ; Do not touch a foreign mapping if ownership has been violated.
    sep #$20
.a8
    lda f:$00d303
    and #$04
    beq sdx_rom_remove_mapping_error
    lda f:SDX_ROM_STATE+1
    and #$fe
    cmp f:$00d301
    bne sdx_rom_remove_mapping_error
    rep #$20
.a16
    ldx #$0ffe
sdx_rom_restore_low:
    lda f:SDX_ROM_BACKUP,x
    sta f:$00c000,x
    dex
    dex
    bpl sdx_rom_restore_low
    ldx #$27fe
sdx_rom_restore_high:
    lda f:SDX_ROM_BACKUP+$1000,x
    sta f:$00d800,x
    dex
    dex
    bpl sdx_rom_restore_high
    sep #$20
.a8
    lda f:SDX_ROM_STATE+1
    sta f:$00d301
    lda #0
    sta f:SDX_ROM_STATE
    rep #$20
.a16
    lda #0
    rtl
sdx_rom_remove_mapping_error:
    rep #$20
.a16
    bra sdx_rom_mapping_error
; Pure staged-image identification, also used by the negative fixture.
; No DP or bank-zero scratch. CRC-32 identifies accidental modifications;
; host tooling additionally pins the full ROM file SHA-256.
sdx_rom_identify:
    lda #0
    sta f:SDX_ROM_PROFILE
    lda #$ffff
    sta f:SDX_ROM_CRC
    sta f:SDX_ROM_CRC+2
    ldx #0
sdx_rom_crc_byte:
    sep #$20
.a8
    lda f:SDX_ROM_IMAGE,x
    eor f:SDX_ROM_CRC
    rep #$20
.a16
    and #$ff
    asl a
    asl a
    phx
    tax
    lda f:SDX_ROM_CRC+1
    eor f:sdx_rom_crc_table,x
    sta f:SDX_ROM_CRC
    lda f:SDX_ROM_CRC+3
    and #$ff
    eor f:sdx_rom_crc_table+2,x
    sta f:SDX_ROM_CRC+2
    plx
    inx
    cpx #$1000
    bne :+
    ldx #$1800
:
    cpx #$4000
    bcc sdx_rom_crc_byte
    lda f:SDX_ROM_CRC
    eor #$ffff
    sta f:SDX_ROM_CRC
    lda f:SDX_ROM_CRC+2
    eor #$ffff
    sta f:SDX_ROM_CRC+2
    ldx #0
sdx_rom_profile_next:
    lda f:SDX_ROM_CRC
    cmp f:sdx_rom_profiles+2,x
    bne sdx_rom_profile_skip
    lda f:SDX_ROM_CRC+2
    cmp f:sdx_rom_profiles+4,x
    bne sdx_rom_profile_skip
    lda f:SDX_ROM_IMAGE+$3ffa
    cmp f:sdx_rom_profiles+6,x
    bne sdx_rom_profile_skip
    lda f:SDX_ROM_IMAGE+$3ffe
    cmp f:sdx_rom_profiles+8,x
    bne sdx_rom_profile_skip
    lda f:sdx_rom_profiles,x
    sta f:SDX_ROM_PROFILE
    lda #0
    rtl
sdx_rom_profile_skip:
    txa
    clc
    adc #SDX_ROM_PROFILE_STRIDE
    tax
    cpx #SDX_ROM_PROFILE_COUNT*SDX_ROM_PROFILE_STRIDE
    bcc sdx_rom_profile_next
    lda #2
    rtl
.include "generated/sdx-firmware.inc"
sdx_rom_end:
