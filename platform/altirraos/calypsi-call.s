; Native -> Calypsi __simple_call LONG(ULONG). No gateway or Task admission.
; Save the lower DP workspace, including runtime spill-helper bytes 20..23.
; IRQ/NMI and scheduling stay enabled; every save belongs to the calling Task.
.segment "SIGNAL_CODE"
.export calypsi_invoke,calypsi_invoke_end,calypsi_invoke_return
.a16
.i16
calypsi_invoke:
    php
    rep #$30
    pha
    phx
    phy
    phd
    phb
.repeat 12, I
    lda I*2
    pha
.endrepeat
    jsl calypsi_invoke_dispatch
calypsi_invoke_return:
    tay
    lda 26,s
    tcd
    sty A816_DP_SCRATCH_OFFSET
    stx A816_DP_SCRATCH_OFFSET+2
.repeat 12, I
    pla
    sta 22-I*2
.endrepeat
    plb
    pld
    ply
    plx
    pla
    plp
    lda A816_DP_SCRATCH_OFFSET
    ldx A816_DP_SCRATCH_OFFSET+2
    rtl
calypsi_invoke_dispatch:
    lda 41,s
    sec
    sbc #1
    sta A816_DP_SCRATCH_OFFSET
    sep #$20
    lda 43,s
    ; RTL increments PC within its bank. A $0000 entry needs $ffff with
    ; the original bank, not a borrow into the preceding bank.
    pha
    rep #$20
    lda A816_DP_SCRATCH_OFFSET
    pha
    ; The synthesized return address adds three bytes to these offsets.
    lda 50,s
    tax
    lda 48,s
    rtl
calypsi_invoke_end:
