; Qualification-only raw COP callers. Replaces Main in the fault fixture.
.p816
.smart
.segment "PROBE"
.a16
.i16
    ldx #0
    ldy #TASK_ABI_TAG
    lda #$13                    ; FindTask(NULL), requires M=X=0
    .if VARIANT = 7
        sep #$20
    .elseif VARIANT = 8
        sep #$10
    .elseif VARIANT = 9
        phd
        pea $0000
        pld                     ; wrong direct-page owner
    .elseif VARIANT = 10
        ldy #$0100              ; invalid gateway tag
    .elseif VARIANT = 11
        lda #$0113              ; unused A bits must be zero
    .elseif VARIANT = 12
        sei
        lda #$12                ; RemTask(NULL) cannot abandon an IRQ-masked task
    .endif
    cop $50
    rep #$30
    lda #1
    sta f:REACHED
    rtl
