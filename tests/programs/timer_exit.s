; One real VBI at each publication boundary, then no later tick to rescue work.
.setcpu "65816"
.smart
.macpack longbranch
.include "tasks.inc"
.include "exec-abi.inc"
.include "native-interrupts.inc"
.include "timer-device.inc"
.segment "PROBE"
.a16
.i16
.export arm, snapshot_hook, leave_hook, edit_hook, unblock_hook
arm:
    php
    sei
    sep #$20
    lda #0
    sta f:$d40e
    sta f:TI_VERSION
    sta f:TI_FAULT
    rep #$20
    lda #7
    sta f:TI_CLOCK_HI
    lda #10
    sta f:TI_CLOCK_LO
    lda #0
    sta f:TI_CLOCK_HI+2
    sta f:TI_CLOCK_LO+2
    lda 9,s
    sta f:CONTROL
    plp
    rtl

.macro tick_at number
.local skip
    php
    rep #$30
    pha
    phx
    phy
    lda f:CONTROL
    cmp #number
    bne skip
    lda #0
    sta f:CONTROL
    lda f:CONTROL+2
    ora #(1 << (number-1))
    sta f:CONTROL+2
    jsl one_tick
    .if number = 1
        ; Snapshot predates the tick and the first queue entry is unpublished.
        lda f:TI_ARMED
        and #$ff
        jne failed
        lda f:NI_PENDING+NI_SOURCE_TIMER
        and #$ff
        jne failed
        lda f:CONTROL+4
        inc a
        sta f:CONTROL+4
    .endif
skip:
    ply
    plx
    pla
    plp
.endmacro

snapshot_hook:
    ; Duplicate the far-pointer argument below this extra return address.
    sep #$20
    lda 6,s
    pha
    rep #$20
    lda 5,s
    pha
    jsl SNAPSHOT
    tay
    tsc
    clc
    adc #3
    tcs
    tya
    tick_at 1
    rtl

leave_hook:
    tick_at 2
    jsl LEAVE
    tick_at 6
    rtl

.a8
edit_hook:
    tick_at 3
    sta f:TI_EDIT
    tick_at 4
    rtl

.a8
unblock_hook:
    sta f:NI_BLOCKED+NI_SOURCE_TIMER
    tick_at 5
    rtl

.a16
one_tick:
    lda f:E816_VBI_COUNT
    tax
    sep #$20
    lda #$40
    sta f:$d40e
    rep #$20
wait_tick:
    txa
    cmp f:E816_VBI_COUNT
    beq wait_tick
    sep #$20
    lda #0
    sta f:$d40e
    rep #$20
    lda f:TI_CLOCK_LO
    cmp #11
    bne failed
    lda f:CONTROL+6
    inc a
    sta f:CONTROL+6
    rtl
failed:
    rep #$30
    lda #$f5ff
    pha
    jsl FAULT
