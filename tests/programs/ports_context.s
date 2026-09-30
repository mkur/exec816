; Qualification-only native caller: full-width and caller-masked GetMsg.
.setcpu "65816"
.smart
.include "tasks.inc"
.include "ports.inc"
.segment "PROBE"
.a16
.i16
    php
    phb
    lda #.loword(PORT+P_MSGPORT_MP_MSGLIST+3)
    sta f:PORT+P_MSGPORT_MP_MSGLIST
    lda #.loword(PORT+P_MSGPORT_MP_MSGLIST)
    sta f:PORT+P_MSGPORT_MP_MSGLIST+6
    sep #$20
    lda #^(PORT+P_MSGPORT_MP_MSGLIST)
    sta f:PORT+P_MSGPORT_MP_MSGLIST+2
    sta f:PORT+P_MSGPORT_MP_MSGLIST+8
    lda #P_NT_MSGPORT
    sta f:PORT+P_MSGPORT_MP_NODE+6
    lda #P_PA_IGNORE
    sta f:PORT+P_MSGPORT_MP_FLAGS
    lda #$12
    pha
    plb
    rep #$20
    tsc
    sec
    sbc #3
    tcs
    sta f:CHECKS+12
    lda #.loword(PORT)
    sta 1,s
    sep #$20
    lda #^PORT
    sta 3,s
    rep #$20
    .if VARIANT=1
        sei
    .elseif VARIANT=2
        lda #0
        tcd
    .endif
    jsl GETMSG
    sta f:CHECKS
    txa
    sta f:CHECKS+2
    tya
    sta f:CHECKS+4
    tdc
    sta f:CHECKS+6
    tsc
    sta f:CHECKS+8
    php
    phb
    sep #$20
    pla
    sta f:CHECKS+10
    pla
    sta f:CHECKS+11
    rep #$20
    tsc
    clc
    adc #3
    tcs
    plb
    plp
    lda #1
    sta f:CHECKS+14
    rtl
