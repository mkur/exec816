.include "console-layout.inc"
.include "console-storage.inc"
; Terminal safe-bus cleanup, after finish has selected the kernel stack/domain
; and disabled IRQ/NMI. Never reached on the reset-required $FF93 path.
; Normal worker shutdown uses preemptible Action copies instead.
.segment "SIGNAL_CODE"
.export console_shutdown
.a16
.i16
console_shutdown:
    sep #$20
    lda f:CS_PRESENTATION+CON_PRESENTATION_CLAIMED
    bne :+
    rep #$20
    rtl
:
    rep #$30
    phd
    tsc
    sec
    sbc #6
    tcs
    tcd
    lda f:CS_PRESENTATION+CON_PRESENTATION_SCREEN
    sta 1
    lda f:CS_PRESENTATION+CON_PRESENTATION_SNAPSHOT
    sta 4
    sep #$20
    lda f:CS_PRESENTATION+CON_PRESENTATION_SCREEN+2
    sta 3
    lda f:CS_PRESENTATION+CON_PRESENTATION_SNAPSHOT+2
    sta 6
    ldy #0
:
    lda [4],y
    sta [1],y
    iny
    cpy #960
    bcc :-
    lda f:CS_PRESENTATION+CON_PRESENTATION_SAVEDCURSOR
    sta f:$02f0
    lda f:CS_PRESENTATION+CON_PRESENTATION_SAVEDATTRACT
    sta f:$004d
    lda #0
    sta f:CS_PRESENTATION+CON_PRESENTATION_CLAIMED
    sta f:CS_PRESENTATION+CON_PRESENTATION_VISIBLE
    sta f:CS_BASE+CON_SERVICE_STATE
    rep #$30
    tsc
    clc
    adc #6
    tcs
    pld
    rtl

; Translate an admitted span without changing D, DBR, S or interrupt masking.
; All temporaries belong to the calling domain. No stack frame or patched code.
.segment "SIGNAL_CODE"
.export console_span,console_span_end,console_span_store
.a16
.i16
console_span:
    lda 4,s
    sta A816_DP_SCRATCH_OFFSET
    lda 5,s
    sta A816_DP_SCRATCH_OFFSET+1
    lda 7,s
    sta A816_DP_SCRATCH_OFFSET+3
    lda 8,s
    sta A816_DP_SCRATCH_OFFSET+4
    lda 10,s
    sta A816_DP_SCRATCH_OFFSET+6
    beq console_span_done
    ldy #0
console_span_next:
    sep #$20
    lda [A816_DP_SCRATCH_OFFSET+3],y
    cmp #128
    bcs console_span_unknown
    rep #$20
    and #$ff
    tax
    sep #$20
    lda f:CS_GLYPHS,x
    bra console_span_store
console_span_unknown:
    lda #31
console_span_store:
    sta [A816_DP_SCRATCH_OFFSET],y
    iny
    rep #$20
    cpy A816_DP_SCRATCH_OFFSET+6
    bne console_span_next
console_span_done:
    rtl
console_span_end:
