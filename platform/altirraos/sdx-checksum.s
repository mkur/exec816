; Ordinary Action! native ABI wrapper around the private CRC update routine.
.include "sdx.inc"
.segment "NATIVE_WORK"
.export sdx_checksum_update, sdx_checksum_update_end
.a16
.i16
sdx_checksum_update:
    lda SDX_CRC_ARG_POINTER,s
    sta SDX_CRC_POINTER_DP
    sep #$20
.a8
    lda SDX_CRC_ARG_POINTER+2,s
    sta SDX_CRC_POINTER_DP+2
    rep #$20
.a16
    lda SDX_CRC_ARG_STATE,s
    sta SDX_CRC_STATE_DP
    lda SDX_CRC_ARG_STATE+2,s
    sta SDX_CRC_STATE_DP+2
    lda SDX_CRC_ARG_COUNT,s
    jsl sdx_crc32_update
    lda SDX_CRC_STATE_DP
    ldx SDX_CRC_STATE_DP+2
    rtl
sdx_checksum_update_end:
.include "sdx-crc32.s"
