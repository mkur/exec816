; Spin in an ordinary Task with its original D. A masked Task must defer the
; native continuation; Forbid alone must still allow completion without COP.
.setcpu "65816"
.smart
.macpack longbranch
.include "exec-abi.inc"
.segment "PROBE"
.a16
.i16
.export spin
spin:
    php
    phb
    lda 10,s
    tay
    lda 6,s
    clc
    adc #6                      ; Message node type
    tax
    lda 8,s
    and #$ff
    adc #0
    sep #$20
    pha
    plb
    rep #$20
    tya
    beq spin_unmasked
    sei
    lda f:E816_VBI_COUNT
    clc
    adc #3
    tay
spin_masked:
    tya
    cmp f:E816_VBI_COUNT
    bne spin_masked
    sep #$20
    lda a:$0000,x
    cmp #7                      ; NT_REPLYMSG
    jeq failed
    rep #$20
spin_unmasked:
    cli
    lda f:E816_VBI_COUNT
    clc
    adc #8
    tay
spin_wait:
    sep #$20
    lda a:$0000,x
    cmp #7
    beq spin_done
    rep #$20
    tya
    cmp f:E816_VBI_COUNT
    bne spin_wait
failed:
    rep #$30
    lda #$f7ff
    pha
    jsl FAULT
spin_done:
    rep #$20
    plb
    plp
    rtl
