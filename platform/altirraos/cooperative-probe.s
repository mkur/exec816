; Qualification-only entry. Production builds emit none of these instructions.
; Test COP with every M/X combination, hidden B, decimal mode, DBR and DP scratch.
.segment "BOOT"
.a16
.i16
.macro probe_slot_offset
    .if GENERAL_TASKS
        ; Four captures fit in adapter state; the rest use test-only scratch.
        cmp #4*32
        bcc :+
        clc
        adc #E816_TEST_REGISTER_EXTENSION-E816_PROBE0-4*32
:
    .endif
.endmacro
raw_context_probe:
    .if BANKED
        ; Keep the original near return frame, but interrupt with PBR=$02.
        jml bankprobe
raw_context_probe_return:
        rts
        .segment "BANKPROBE"
        .export bankprobe
bankprobe:
    .endif
    .if PREEMPTIVE
        ; Record the switch counter without changing the tested register image.
        sei
        lda E816_CURRENT
        and #$00ff
        asl a
        asl a
        asl a
        asl a
        asl a
        probe_slot_offset
        tax
        lda E816_SWITCH_COUNT
        sta E816_PROBE0+20,x
    .endif
    lda #$beef
    sta $20
    sep #$20
    lda #$12
    pha
    plb
    lda #PROBE_FLAGS
    pha
    rep #$30
    lda #$ab01
    ldx #$1234
    ldy #$5678
    plp
    .if PREEMPTIVE
        wai                      ; actual VBI, no voluntary yield
    .else
        cop E816_COP
    .endif
    ; Snapshot flags before any flag-changing instruction, then full registers.
    php
    save_full
    cld
    pea $0000
    plb
    plb
    tsc
    tax
    lda E816_CURRENT
    and #$00ff
    asl a
    asl a
    asl a
    asl a
    asl a
    probe_slot_offset
    tay
    .repeat 5, offset
        lda f:1+offset*2,x
        sta E816_PROBE0+offset*2,y
    .endrepeat
    txa
    clc
    adc #10
    sta E816_PROBE0+10,y
    lda $20
    sta E816_PROBE0+12,y
    .if PREEMPTIVE
        lda E816_SWITCH_COUNT
        sta E816_PROBE0+22,y
    .endif
    txa
    clc
    adc #10
    tcs
    ; Unknown services and foreign domains must return errors without switching.
    lda #$ff
    cop E816_COP
    sta E816_PROBE0+14,y
    phd
    lda #E816_KERNEL_DP           ; not a public Task's domain
    tcd
    lda #E816_SERVICE_VERSION
    cop E816_COP
    sta E816_PROBE0+16,y
    pld
    ; Raw exit under I must leave the task alive. The public nonreturning
    ; ExitTask wrapper turns this refusal into a fault instead of returning.
    sei
    ldx #7
    lda #E816_SERVICE_EXIT
    cop E816_COP
    sta E816_PROBE0+18,y
    ; Return to the ordinary Action ABI, and deliver a yield deferred by I.
    rep #$30
    cld
    cli
    lda #E816_SERVICE_POLL
    cop E816_COP
    .if BANKED
        jml raw_context_probe_return
    .else
        rts
    .endif
