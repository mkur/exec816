; Included in the native NMI segment. The ROM reaches VVBLKI in emulation mode
; for both native interrupts and NMIs that interrupt COP #0 OS work. A/X/Y are
; already saved; D=DBR=0. Leave the ROM's complete VBI chain intact.
.export vbi_tick, interrupt_schedule
.a8
.i8
vbi_tick:
    .if CONSOLE_NATIVE
        ; Before retained ROM stage one, keep its attract/color calculation
        ; stable even while the console worker is asleep. No drawing here.
        lda f:CS_PRESENTATION+CON_PRESENTATION_CLAIMED
        beq :+
        stz $004d
:
    .endif
    lda #1
    sta E816_TICK_PENDING
    inc E816_VBI_COUNT
    bne :+
    inc E816_VBI_COUNT+1
:
    jmp (E816_OLD_VBI)

; Enter only after retiring our OS interrupt activation, with S pointing to
; the full interrupted frame, I=1 and D=DBR=0. No scheduler scratch has yet
; been touched. IRQ returns also deliver ticks deferred inside an IRQ handler.
.a16
.i16
interrupt_schedule:
    lda E816_TICK_PENDING
    .if GENERAL_TASKS .and SIGNAL_AUTO
        ora T_WAKE_PENDING
    .endif
    and #$00ff
    beq resume_interrupted
    lda E816_SWITCHING
    and #$00ff
    bne resume_interrupted
    lda E816_IRQ_DEPTH
    bne resume_interrupted
    lda OS_BUSY
    and #$00ff
    bne resume_interrupted
    tsc
    tax
    lda f:A816_SAVED_FRAME_P_OFFSET,x
    and #$0004
    bne resume_interrupted
    jsr validate_frame
    bcs resume_interrupted
    .if GENERAL_TASKS
        jsl signal_tick_needed
        bcs :+
        ; No sleeper/ready peer and no pending wake: this tick needs no policy
        ; activation. The absolute VBI count is retained; retire the scheduling
        ; hint so subsequent byte IRQs do not repeatedly validate this frame.
        sep #$20
        stz E816_TICK_PENDING
        rep #$20
        bra resume_interrupted
:
    .endif
    ; Only an owned native task frame can reach the shared dispatcher.
    lda #E816_KERNEL_DP
    tcd
    inc E816_VBI_DISPATCHES
    ldy #E816_SERVICE_POLL
    jmp dispatch_frame
resume_interrupted:
    restore_full
    rti
