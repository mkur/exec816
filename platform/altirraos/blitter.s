; Resident VBXE source. Mailbox and binding stay in upper Task metadata.
; IRQ/NMI never borrow Task or C pointers. All hardware changes preserve I.
.include "blitter.inc"
.segment "SIGNAL_CODE"
.export blitter_prepare,blitter_prepare_end,blitter_claim,blitter_claim_end
.export blitter_release,blitter_release_end,blitter_release_unchecked
.export blitter_arm,blitter_arm_end,blitter_state,blitter_state_end
.export blitter_reset,blitter_reset_end,blitter_irq_complete,blitter_irq_posted
.a16
.i16
blitter_prepare:
    php
    sei
    lda 5,s
    sta f:BV_OWNER
    lda 9,s
    sta f:BV_GENERATION
    lda 11,s
    sta f:BV_GENERATION+2
    sep #$20
    lda 7,s
    sta f:BV_OWNER+2
    rep #$20
    plp
    rtl
blitter_prepare_end:

; Bind has already validated the retained target and allocated mask.
blitter_claim:
    php
    sei
    lda f:BV_OWNER
    ora f:BV_OWNER+1
    beq blitter_claim_bad
    lda f:BV_OWNER
    cmp f:BV_BINDING+T_BINDING_TASK
    bne blitter_claim_bad
    sep #$20
    lda f:BV_OWNER+2
    cmp f:BV_BINDING+T_BINDING_TASK+2
    bne blitter_claim_bad8
    lda f:BV_BINDING+T_BINDING_ACTIVE
    bne blitter_claim_bad8
    lda #0
    sta f:$d654
    sta f:BV_CONTROL
    sta f:BV_EVENT
    rep #$20
    lda f:$0216
    sta f:BV_OLDIRQ
    sta f:blitter_saved_irq
    lda #blitter_emulation_entry
    sta f:$0216
    sep #$20
    lda #1
    sta f:BV_BINDING+T_BINDING_ACTIVE
    rep #$20
    plp
    lda #1
    rtl
blitter_claim_bad8:
    rep #$20
blitter_claim_bad:
    plp
    lda #0
    rtl
blitter_claim_end:

blitter_release:
blitter_release_unchecked:
    php
    sei
    sep #$20
    lda f:BV_BINDING+T_BINDING_ACTIVE
    beq blitter_release_done
    lda #0
    sta f:$d654
    sta f:BV_CONTROL
    sta f:BV_BINDING+T_BINDING_ACTIVE
    rep #$20
    lda f:BV_OLDIRQ
    sta f:$0216
blitter_release_done:
    rep #$20
    plp
    rtl
blitter_release_end:

; Existing command arena is fully uploaded/unmapped before this short section.
; ID and start tick publish before ARMED. Enable and START cannot lose an IRQ.
blitter_arm:
    php
    sei
    sep #$20
    lda f:BV_BINDING+T_BINDING_ACTIVE
    beq blitter_arm_bad
    lda f:BV_EVENT
    cmp #BV_ARMED
    beq blitter_arm_bad
    lda f:$d653
    and #3
    bne blitter_arm_bad
    lda #0
    sta f:$d654
    rep #$20
    lda 5,s
    sta f:BV_ID
    lda 7,s
    sta f:BV_ID+2
    lda f:E816_VBI_COUNT
    sta f:BV_STARTED
    sep #$20
    lda #<BV_COMMAND
    sta f:$d650
    lda #>BV_COMMAND
    sta f:$d651
    lda #^BV_COMMAND
    sta f:$d652
    lda #BV_ARMED
    sta f:BV_EVENT
    lda #1
    sta f:BV_CONTROL
    sta f:$d654
    sta f:$d653
.export blitter_launched
blitter_launched:
    rep #$20
    plp
    lda #0
    rtl
blitter_arm_bad:
    rep #$20
    plp
    lda #1
    rtl
blitter_arm_end:

; An IRQ changes only the one-byte event. ID remains immutable until next arm.
blitter_state:
    lda 4,s
    cmp f:BV_ID
    bne blitter_state_bad
    lda 6,s
    cmp f:BV_ID+2
    bne blitter_state_bad
    lda f:BV_EVENT
    and #$ff
    rtl
blitter_state_bad:
    lda #$ffff
    rtl
blitter_state_end:

blitter_reset:
    php
    sei
    sep #$20
    lda #0
    sta f:$d654
    sta f:BV_CONTROL
    sta f:BV_EVENT
    rep #$20
    plp
    rtl
blitter_reset_end:

; Full context saved, I=1, E=0, M=1, X=0. No scheduling from this activation.
; Return carry set if this owned source was acknowledged.
.a8
blitter_irq_service:
    lda f:BV_BINDING+T_BINDING_ACTIVE
    beq blitter_irq_none
    lda f:BV_CONTROL
    beq blitter_irq_none
    lda f:$d654
    and #1
    beq blitter_irq_none
    lda #0
    sta f:$d654
    sta f:BV_CONTROL
    lda f:BV_EVENT
    cmp #BV_ARMED
    bne blitter_irq_handled
    lda f:$d653
    and #3
    bne blitter_irq_handled
blitter_irq_complete:
    lda #BV_DONE
    sta f:BV_EVENT
    ldx #BV_BINDING-T_BASE
    jsr signal_post_binding
blitter_irq_posted:
blitter_irq_handled:
    sec
    rts
blitter_irq_none:
    clc
    rts

; VIMIRQ runs before ROM has saved registers. Preserve both possible E modes.
.segment "IRQ"
.a8
.i8
blitter_emulation_entry:
    php
    clc
    xce
    php
    jsl blitter_emulation
    bcs blitter_emulation_handled
    plp
    xce
    plp
    jmp (blitter_saved_irq)
blitter_emulation_handled:
    plp
    xce
    plp
    rti
blitter_saved_irq:
    .word 0
.segment "SIGNAL_CODE"
blitter_emulation:
    save_full
    cld
    lda #0
    tcd
    pea 0
    plb
    plb
    inc E816_IRQ_DEPTH
    sep #$20
    jsr blitter_irq_service
    bcc blitter_emulation_done
    rep #$20
    lda f:BV_EMULATIONS
    inc a
    sta f:BV_EMULATIONS
    sep #$20
    sec
    ; Preserve ROM dispatch for simultaneous POKEY sources.
    lda f:$d20e
    eor #$ff
    and f:$0010
    beq blitter_emulation_done
    clc
blitter_emulation_done:
    rep #$30
    dec E816_IRQ_DEPTH
    restore_full
    rtl

; Fixture-only emulation activation, with no OS or Task switch across it.
.export blitter_emulation_probe,blitter_emulation_probe_end
.a16
.i16
blitter_emulation_probe:
    php
    sei
    save_full
    tsc
    sta f:BV_PROBE_STACK
    lda #0
    tcd
    pea 0
    plb
    plb
    sep #$20
    lda #1
    sta f:OS_BUSY
    rep #$20
    lda #OS_STACK_TOP
    tcs
    jml blitter_probe_os
blitter_probe_return:
    rep #$30
    lda f:BV_PROBE_STACK
    tcs
    sep #$20
    lda #0
    sta f:OS_BUSY
    rep #$30
    restore_full
    plp
    rtl
blitter_emulation_probe_end:
.segment "IRQ"
.a8
.i8
blitter_probe_os:
    sep #$30
    sec
    xce
    cli
blitter_probe_wait:
    lda f:BV_EVENT
    cmp #BV_ARMED
    bne blitter_probe_exit
    wai
    bra blitter_probe_wait
blitter_probe_exit:
    sei
    clc
    xce
    rep #$30
    jml blitter_probe_return
.segment "SIGNAL_CODE"
.a16
.i16
