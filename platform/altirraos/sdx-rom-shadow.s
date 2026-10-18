; Reversible early emulation-NMI routing for the pinned AltirraOS 816 ROM.
; Development adapter component; not installed by the ordinary hosted build.
;
; The including build supplies disjoint upper-memory SDX_ROM_IMAGE (16 KiB,
; exact pinned ROM), SDX_ROM_BACKUP (14 KiB), SDX_ROM_STATE (2 bytes), and a
; bank-zero SDX_ROM_NMI entry (and optional SDX_ROM_IRQ entry). State byte 0 is ownership; byte 1 saves PORTB.
; Both entries require E=0, M=X=0, decimal clear, I=1, NMIEN=0, DLI disabled,
; no live ROM activation, and code/stack outside the ROM windows. The caller
; owns interrupt exclusion for the entire operation. No DP scratch is used.
; Preserve D/DBR/S; clobber A/X/Y/P. RTL with A=0 success, 1 mapping mismatch,
; 2 ROM mismatch, 3 already installed (or not installed on Remove).
;
; Only $C000-CFFF and $D800-FFFF are copied: $D000-D7FF is hardware, not RAM.
; Original underlying RAM is restored before re-enabling ROM. The ROM file
; is never modified. Cold/warm reset, self-test and third-party PORTB changes
; are outside this component's admitted lifetime.
.export sdx_rom_install, sdx_rom_remove, sdx_rom_end
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
    ; Compare every CPU-visible ROM byte before changing mapping or RAM.
    ldx #$0ffe
sdx_rom_check_low:
    lda f:$00c000,x
    cmp f:SDX_ROM_IMAGE,x
    bne sdx_rom_image_error
    dex
    dex
    bpl sdx_rom_check_low
    ldx #$27fe
sdx_rom_check_high:
    lda f:$00d800,x
    cmp f:SDX_ROM_IMAGE+$1800,x
    bne sdx_rom_image_error
    dex
    dex
    bpl sdx_rom_check_high
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
sdx_rom_end:
