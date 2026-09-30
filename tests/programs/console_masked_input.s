; Test-only deliberate IRQ starvation: real POKEY scanning must flag overrun.
; SIO is owned but idle. NMI continues; interrupted I=1 defers task switching.
.setcpu "65816"
.smart
.segment "PROBE"
.a16
.i16
start:
    php
    sei
    sep #$20
    lda #1
    sta f:READY
wait_gate:
    lda f:GATE
    beq wait_gate
    rep #$20
    plp
    rtl
