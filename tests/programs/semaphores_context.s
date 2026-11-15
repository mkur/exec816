; Replace only Main in a frozen diagnostic image; no C/Action! rebuild per case.
.p816
.smart
.include "tasks.inc"
.include "semaphore-abi.inc"
.segment "PROBE"
.a16
.i16
    php
    phd
    phb
    tsc
    sta f:RESULT+14
    tdc
    sta f:RESULT+16
    lda f:VARIANT
    and #$ff
ordinary:
    lda f:VARIANT
    and #$ff
    cmp #8
    bne :+
    sei
:
    ldx #.loword(DEVICE)
    ldy #T_PROFILE_TAG+.bankbyte(DEVICE)
    cmp #1
    bne :+
    ldy #$0100+.bankbyte(DEVICE)
:
    cmp #5
    bne :+
    lda #0
    tcd
:
    sep #$20
    lda #$12
    pha
    plb
    lda f:VARIANT
    cmp #2
    beq narrow_a
    cmp #3
    bne :+
    sep #$10
:
    rep #$20
    lda f:VARIANT
    and #$ff
    cmp #4
    bne :+
    lda #$0100+SEM_SERVICE_ATTEMPT_SEMAPHORE
    bra invoke
:
    cmp #6
    bne :+
    lda #SEM_SERVICE_RELEASE_SEMAPHORE
    bra invoke
:
    lda #SEM_SERVICE_ATTEMPT_SEMAPHORE
    bra invoke
narrow_a:
    lda #SEM_SERVICE_ATTEMPT_SEMAPHORE
invoke:
    sec
    clv
    sed
    cop $50
    php
    rep #$30
    sta f:RESULT
    txa
    sta f:RESULT+2
    tya
    sta f:RESULT+4
    tdc
    sta f:RESULT+6
    tsc
    sta f:RESULT+8
    phb
    sep #$20
    pla
    sta f:RESULT+10
    pla
    sta f:RESULT+11
    rep #$30
    cld
    lda #SEM_SERVICE_RELEASE_SEMAPHORE
    ldx #.loword(DEVICE)
    ldy #T_PROFILE_TAG+.bankbyte(DEVICE)
    cop $50
    plb
    pld
    plp
    sep #$20
    lda #1
    sta f:REACHED
    rep #$20
    rtl
