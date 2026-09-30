; Task scheduling checkpoint after an empty guarded peek, before Wait.
.setcpu "65816"
.smart
.segment "PROBE"
.a16
.i16
    lda f:CHECKPOINTS
    inc a
    sta f:CHECKPOINTS
    sep #$20
    lda #1
    sta f:GO
    rep #$20
    jsl YIELD
    ; Replay the four displaced bytes from ports_wait_empty.
    lda 12,s
    sta $00
    jml CONTINUE
