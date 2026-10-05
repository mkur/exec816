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
.export arm
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
    lda #0
    sta f:TI_CLOCK_HI+2
    lda #$ffff
    sta f:TI_CLOCK_LO
    sta f:TI_CLOCK_LO+2
    lda 9,s
    sta f:CONTROL
    plp
    rtl

.macro snapshot_hook number, origin
.local skip, wait_tick
    .ident(.sprintf("snapshot_hook_%u", number)):
    .export .ident(.sprintf("snapshot_hook_%u", number))
    ; Execute the displaced production load/store exactly once.
    .if number = 6
        lda #0
    .else
        lda f:origin
    .endif
    sta [1],y
    php
    rep #$30
    pha
    phx
    lda f:CONTROL
    cmp #number
    bne skip
    lda #0
    sta f:CONTROL
    lda f:CONTROL+2
    ora #(1 << (number-1))
    sta f:CONTROL+2
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
skip:
    plx
    pla
    plp
    rtl
.endmacro
snapshot_hook 1, TI_CLOCK_HI
snapshot_hook 2, TI_CLOCK_HI+2
snapshot_hook 3, TI_CLOCK_LO
snapshot_hook 4, TI_CLOCK_LO+2
snapshot_hook 5, TI_RATE
snapshot_hook 6, 0
