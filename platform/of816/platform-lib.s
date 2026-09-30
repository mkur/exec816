; Compiled inside OF816's bank; use its own parameter-stack helpers.
.import of_putchar, of_getchar, of_key_ready, of_handoff

.proc of_system_interface
    cmp #SI_EMIT
    beq emit
    cmp #SI_KEY
    beq key
    cmp #SI_KEYQ
    beq keyq
    cmp #SI_GET_FCODE
    beq fcode
    cmp #SI_RESET_ALL
    beq unsupported
    ; The two initialization callbacks need no additional platform work.
    cmp #SI_POST_INIT+1
    bcs unsupported
success:
    lda #0
    tay
    clc
    rtl
emit:
    jsr _popay
    tya
    jsl of_putchar
    bra success
key:
    jsl of_getchar
    tay
    lda #0
    jsr _pushay
    bra success
keyq:
    jsl of_key_ready
    tay
    jsr _pushay
    bra success
fcode:
    lda #0
    tay
    jsr _pushay
    bra success
unsupported:
    lda #.hiword(-21)
    ldy #.loword(-21)
    sec
    rtl
.endproc
.export of_system_interface
