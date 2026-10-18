; Native CRC-32/ISO-HDLC over staged SDX file bytes. See abi/sdx.json.
; Caller-owned transient DP scratch; the shared table/code live in upper RAM.
; No hardware access, IRQ masking, allocations or guest-mode dependency.
.setcpu "65816"
.a16
.i16
.ifndef SDX_ABI_VERSION
    .include "sdx.inc"
.endif
.export sdx_crc32_update, sdx_crc32_end
sdx_crc32_update:
    phy
    tay
    beq @done
@byte:
    sep #$20
    .a8
    lda [SDX_CRC_POINTER_DP]
    eor SDX_CRC_STATE_DP
    rep #$20
    .a16
    and #$00ff
    asl
    asl
    tax
    lda SDX_CRC_STATE_DP+1
    eor f:sdx_crc32_table,x
    sta SDX_CRC_STATE_DP
    lda SDX_CRC_STATE_DP+3
    and #$00ff
    eor f:sdx_crc32_table+2,x
    sta SDX_CRC_STATE_DP+2
    inc SDX_CRC_POINTER_DP
    bne @advance
    sep #$20
    .a8
    inc SDX_CRC_POINTER_DP+2
    rep #$20
    .a16
@advance:
    dey
    bne @byte
@done:
    ply
    rtl
sdx_crc32_end:
.include "sdx-crc32-table.inc"
