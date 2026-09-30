; Bounded serial ownership and IRQ routing for the AltirraOS native adapter.
; Caller supplies SIO_ACTIVE, SIO_SAVED_MASK, SIO_SAVED_CRITIC, SIO_OS_BUSY,
; SIO_SAVED_SEROR and a bank-zero SIO_EMULATION_ENTRY callback.
; State may be in upper RAM. Calls require native E=0, M=1, I=1; preserve X/Y,
; D/DBR and S, clobber A/P. Claim returns C clear on success, set when busy.
; Registration, vector installation and device configuration belong to the
; caller's protected ownership transaction. Release follows device quiescence.

SIO_IRQ_BITS = $38

.macro serial_ownership_routines claim, release
.local busy, released
claim:
    lda f:SIO_ACTIVE
    bne busy
    lda f:SIO_OS_BUSY
    bne busy
    lda f:$0010
    and #SIO_IRQ_BITS
    sta f:SIO_SAVED_MASK
    lda f:$0042
    sta f:SIO_SAVED_CRITIC
    lda f:$020c
    sta f:SIO_SAVED_SEROR
    lda f:$020d
    sta f:SIO_SAVED_SEROR+1
    lda #<SIO_EMULATION_ENTRY
    sta f:$020c
    lda #>SIO_EMULATION_ENTRY
    sta f:$020d
    lda #1
    sta f:SIO_ACTIVE
    sta f:$0042
    lda f:$0010
    and #($ff-SIO_IRQ_BITS)
    sta f:$0010
    sta f:$d20e
    clc
    rts
busy:
    sec
    rts
release:
    lda f:SIO_ACTIVE
    beq released
    lda f:SIO_SAVED_SEROR
    sta f:$020c
    lda f:SIO_SAVED_SEROR+1
    sta f:$020d
    lda f:$0010
    and #($ff-SIO_IRQ_BITS)
    ora f:SIO_SAVED_MASK
    sta f:$0010
    sta f:$d20e
    lda f:SIO_SAVED_CRITIC
    sta f:$0042
    lda #0
    sta f:SIO_ACTIVE
released:
    rts
.endmacro

; ROM VBI can enable IRQs while executing in emulation mode. Its serial
; dispatcher acknowledges the source and saves A before calling VSEROR.
; This registered callback must only post: E=1, M=X=1, I=1, D=DBR=0;
; notify preserves X/Y, D/DBR, E and stack. The outer native adapter decides
; readiness after retiring the live OS activation. Two JSR stack bytes.
.macro serial_emulation_ready notify
    jsr notify
    pla
    rti
.endmacro

; Full interrupted context has already been saved. Entry native M=1, X=0,
; I=1. No live OS/IRQ activation may be suspended by safe_exit. post is a
; same-bank bounded JSR callback: M=1, I=1 on return; no switching or shared
; compiler scratch. It may clobber A/X/Y but must preserve D/DBR and stack.
; Serial-ready is active-low and must also be enabled. Unowned sources go to
; the existing ROM adapter, including a source concurrent with serial-ready.
.macro serial_irq_route post, rom_entry, safe_exit
.local unowned
    lda f:SIO_ACTIVE
    beq unowned
    lda f:$d20e
    eor #$ff
    and f:$0010
    and #$10
    beq unowned
    lda f:$0010
    and #$ef
    sta f:$d20e
    lda f:$0010
    sta f:$d20e
    jsr post
    lda f:$d20e
    eor #$ff
    and f:$0010
    and #$ef
    bne unowned
    jmp safe_exit
unowned:
    jmp rom_entry
.endmacro
