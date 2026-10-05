; Synthetic resident lifecycle: two activations reuse the same retained
; request/endpoint. All gate and source operations are fixture-private.
.setcpu "65816"
.smart
.macpack longbranch
.include "tasks.inc"
.include "exec-abi.inc"
.include "native-interrupts.inc"
.segment "PROBE"
.a16
.i16
.export arm, raw_notify, complete
arm:
    php
    sei
    lda 9,s
    cmp #2
    jeq source_check
    cmp #1
    jeq source_release
    lda 5,s
    sta f:CONTROL
    sep #$20
    lda 7,s
    sta f:CONTROL+2
    lda #0
    sta f:CONTROL+8
    sta f:E816_PROBE0
    sta f:E816_PROBE0+1
    lda #1
    sta f:CONTROL+3
    sta f:NI_ENABLED+NI_SOURCE_PROBE
    .if MODE = 1
        sta f:NI_BLOCKED+NI_SOURCE_PROBE
    .endif
    .if MODE = 3
        lda #0
        sta f:NI_ENABLED+NI_SOURCE_PROBE
    .endif
    plp
    rtl
.a16
source_release:
    sep #$20
    lda #0
    sta f:NI_BLOCKED+NI_SOURCE_PROBE
    .if MODE = 3
        lda f:NI_PENDING+NI_SOURCE_PROBE
        jne failed
        lda #1
        sta f:NI_ENABLED+NI_SOURCE_PROBE
        sta f:NI_PENDING+NI_SOURCE_PROBE
    .endif
    plp
    rtl
.a16
source_check:
    lda f:NI_ACTIVE
    jne failed
    sep #$20
    lda f:NI_ENABLED+NI_SOURCE_PROBE
    ora f:NI_PENDING+NI_SOURCE_PROBE
    ora f:NI_RUNNING+NI_SOURCE_PROBE
    ora f:NI_BLOCKED+NI_SOURCE_PROBE
    jne failed
    rep #$20
    lda f:E816_VBI_COUNT
    cmp f:CONTROL+6
    jne failed
    plp
    rtl

.a8
.i8
raw_notify:
    lda f:CONTROL+3
    beq source_prearm
    cmp #2
    beq source_notify
    lda f:E816_PROBE0
    beq raw_done
source_notify:
    lda f:NI_ENABLED+NI_SOURCE_PROBE
    beq :+
    lda #1
    sta f:NI_PENDING+NI_SOURCE_PROBE
:
    lda #0
    sta f:CONTROL+3
    .if MODE = 5
        lda f:NI_RUNNING+NI_SOURCE_PROBE
        beq :+
    .endif
    lda #0
    sta f:$d40e
:
    lda #$80
    sta f:E816_PROBE0+1
    lda f:CONTROL+5
    inc a
    sta f:CONTROL+5
    lda f:E816_VBI_COUNT
    sta f:CONTROL+6
    lda f:E816_VBI_COUNT+1
    sta f:CONTROL+7
raw_done:
    rtl
source_prearm:
    lda #$80
    sta f:E816_PROBE0+1
    rtl

.a8
.i16
complete:
    lda f:NI_ACTIVE
    cmp #1
    jne failed
    lda f:NI_RUNNING+NI_SOURCE_PROBE
    cmp #1
    jne failed
    lda f:CONTROL+8
    inc a
    sta f:CONTROL+8
    .if MODE = 2
        cmp #1
        bne :+
        lda #2
        rtl
:
    .endif
    .if MODE = 5
        cmp #1
        bne :+
        ; New hint after acknowledgement must survive a callback returning 0.
        lda #2
        sta f:CONTROL+3
source_running_wait:
        lda f:CONTROL+3
        bne source_running_wait
        lda #0
        rtl
:
    .endif
    rep #$30
    lda f:CONTROL+2
    and #$ff
    tax
    lda f:CONTROL
    jsl REPLY
    sep #$20
    lda f:CONTROL+4
    inc a
    sta f:CONTROL+4
    lda #0
    sta f:NI_ENABLED+NI_SOURCE_PROBE
    rtl
failed:
    rep #$30
    cld
    lda #$f8ff
    pha
    jsl FAULT
