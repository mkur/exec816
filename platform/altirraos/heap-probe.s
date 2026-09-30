; Qualification only. Independent byte-at-a-time poison fill and a masked
; caller around the public wrappers. No new persistent storage is reserved.
.segment "SIGNAL_CODE"
.a16
.i16
.export heap_probe_fill, heap_probe_fill_end, heap_probe_masked, heap_probe_masked_end
heap_probe_fill:
    lda 4,s
    sta A816_DP_POINTER0_OFFSET
    sep #$20
    lda 6,s
    sta A816_DP_POINTER0_OFFSET+2
    lda 12,s
    sta A816_DP_SCRATCH_OFFSET+7
    rep #$20
    lda 8,s
    sta A816_DP_SCRATCH_OFFSET+3
    lda 10,s
    sta A816_DP_SCRATCH_OFFSET+5
heap_probe_fill_loop:
    lda A816_DP_SCRATCH_OFFSET+3
    ora A816_DP_SCRATCH_OFFSET+5
    beq heap_probe_fill_done
    sep #$20
    lda A816_DP_SCRATCH_OFFSET+7
    sta [A816_DP_POINTER0_OFFSET]
    inc A816_DP_POINTER0_OFFSET
    bne :+
    inc A816_DP_SCRATCH_OFFSET+1
    bne :+
    inc A816_DP_POINTER0_OFFSET+2
:
    rep #$20
    lda A816_DP_SCRATCH_OFFSET+3
    sec
    sbc #1
    sta A816_DP_SCRATCH_OFFSET+3
    lda A816_DP_SCRATCH_OFFSET+5
    sbc #0
    sta A816_DP_SCRATCH_OFFSET+5
    bra heap_probe_fill_loop
heap_probe_fill_done:
    rtl
heap_probe_fill_end:

; Independent byte-wise verifier: unlike CLEAR's indexed word stores, this
; advances a 24-bit cursor after every byte and checks the entire payload.
.export heap_probe_verifyzero, heap_probe_verifyzero_end
heap_probe_verifyzero:
    lda 4,s
    sta A816_DP_POINTER0_OFFSET
    sep #$20
    lda 6,s
    sta A816_DP_POINTER0_OFFSET+2
    rep #$20
    lda 8,s
    sta A816_DP_SCRATCH_OFFSET+3
    lda 10,s
    sta A816_DP_SCRATCH_OFFSET+5
heap_probe_zero_loop:
    lda A816_DP_SCRATCH_OFFSET+3
    ora A816_DP_SCRATCH_OFFSET+5
    beq heap_probe_zero_done
    sep #$20
    lda [A816_DP_POINTER0_OFFSET]
    bne heap_probe_zero_failed
    inc A816_DP_POINTER0_OFFSET
    bne :+
    inc A816_DP_SCRATCH_OFFSET+1
    bne :+
    inc A816_DP_POINTER0_OFFSET+2
:
    rep #$20
    lda A816_DP_SCRATCH_OFFSET+3
    sec
    sbc #1
    sta A816_DP_SCRATCH_OFFSET+3
    lda A816_DP_SCRATCH_OFFSET+5
    sbc #0
    sta A816_DP_SCRATCH_OFFSET+5
    bra heap_probe_zero_loop
heap_probe_zero_failed:
    rep #$20
    lda #0
    rtl
heap_probe_zero_done:
    lda #1
    rtl
heap_probe_verifyzero_end:

heap_probe_masked:
    .if STACK_CHECKS
    tsc
    cmp A816_DP_STACK_CEILING_OFFSET
    bcc :+
    beq :+
    bra heap_probe_mask_overflow
:
    sec
    sbc #30
    bcc heap_probe_mask_overflow
    cmp A816_DP_STACK_FLOOR_OFFSET
    bcs :+
heap_probe_mask_overflow:
    lda #30
    jml stack_overflow
:
    .endif
    php
    sei
    tsc
    sec
    sbc #5
    tcs                         ; pointer 1..3, first I result 4..5, saved P 6
    sec
    sbc #9
    tcs
    lda #9
    sta 1,s
    lda #0
    sta 3,s
    sta 5,s
    lda #1                      ; CLEAR high flags word
    sta 7,s
    sep #$20
    lda #0
    sta 9,s
    rep #$20
    jsl heap_alloc_mem
    sta 10,s
    txa
    sep #$20
    sta 12,s
    rep #$20
    tsc
    clc
    adc #9
    tcs
    php
    sep #$20
    pla
    and #4
    rep #$20
    and #$00ff
    sta 4,s
    lda 3,s
    and #$00ff
    ora 1,s
    bne :+
    lda #0
    brl heap_probe_mask_result
:
    tsc
    sec
    sbc #9
    tcs
    lda 10,s
    sta 1,s
    sep #$20
    lda 12,s
    sta 3,s
    lda #0
    sta 4,s
    sta 9,s
    rep #$20
    lda #9
    sta 5,s
    lda #0
    sta 7,s
    jsl heap_free_mem
    tsc
    clc
    adc #9
    tcs
    php
    sep #$20
    pla
    and #4
    rep #$20
    and #$00ff
    and 4,s
    cmp #4
    beq :+
    lda #0
    bra heap_probe_mask_result
:
    lda #1
heap_probe_mask_result:
    sta A816_DP_SCRATCH_OFFSET+8
    tsc
    clc
    adc #5
    tcs
    plp
    lda A816_DP_SCRATCH_OFFSET+8
    rtl
heap_probe_masked_end:
