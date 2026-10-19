; Isolated emitted-code tests, not production guest admission.
; NMI/IRQ are disabled here; interrupt coexistence belongs to the runtime gate.
.setcpu "65816"
.export start, done, native_end, guest_entry, guest_outer, guest_exit
.export native_run, crc_call, crc_return
PARAM = $2000
NATIVE_DP = $2400
NATIVE_S = $5fef

.segment "CODE"
.a8
.i8
start:
    sei
    cld
    stz $d40e
    clc
    xce
    rep #$30
.a16
.i16
    lda #NATIVE_S
    tcs
    lda #0
    tcd
    phk
    plb
    ldx #0
@copy:
    lda $4000,x
    sta f:NATIVE_BANK*$10000+$6000,x
    inx
    inx
    cpx #native_end-(NATIVE_BANK*$10000+$6000)
    bcc @copy
    ldx #0
@guest:
    lda $5000,x
    sta f:GUEST_BANK*$10000+$f000,x
    inx
    inx
    cpx #guest_end-(GUEST_BANK*$10000+$f000)
    bcc @guest
    lda #NATIVE_DP
    tcd
    sep #$20
.a8
    lda #3
    pha
    plb
    rep #$20
.a16
done:
    nop
    jml native_run

.segment "NATIVE"
.a16
.i16
native_run:
    lda f:PARAM+$2e
    bne native_arc
    ldy #$beef
    lda f:PARAM
crc_call:
    jsl sdx_crc32_update
crc_return:
    tya
    sta f:PARAM+2
    tdc
    sta f:PARAM+4
    tsc
    sta f:PARAM+6
    phb
    sep #$20
.a8
    pla
    sta f:PARAM+8
    rep #$20
.a16
    jml done
native_arc:
    jml guest_entry
.include "sdx-crc32.s"
native_end:

.segment "GUEST"
.a16
.i16
guest_entry:
    lda f:PARAM+4
    tcd
    sep #$20
.a8
    lda f:PARAM+8
    pha
    plb
    rep #$20
.a16
    lda f:PARAM+2
    tcs
    lda #$ab06
    ldx #$005a
    ldy #$00a6
    sec
    xce
.a8
.i8
    clv
    ; The host supplies an actual JSR followed by six bytes at $7FFC.
    ; Its saved return $7FFE carries into $8004 and sets V in the helper ADC.
    jmp $7ffc
.res $200-(*-guest_entry), $ea
guest_outer:
    ; Only this operand changes between the two relocation placements.
    jsr $ffff
    sta f:PARAM+$10
    php
    pla
    sta f:PARAM+$13
    txa
    sta f:PARAM+$11
    tya
    sta f:PARAM+$12
    tsx
    txa
    sta f:PARAM+$14
    rts
.res $300-(*-guest_entry), $ea
guest_exit:
    ; Change mode in the guest bank before crossing into the native adapter.
    clc
    xce
    rep #$30
.a16
.i16
    sta f:PARAM+$16
    lda #NATIVE_S
    tcs
    lda #NATIVE_DP
    tcd
    sep #$20
.a8
    lda #3
    pha
    plb
    rep #$20
.a16
    jml done
guest_end:
