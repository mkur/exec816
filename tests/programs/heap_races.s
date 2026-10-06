; Test-only replacement for HEAPAPIPROBE.Fill (zero native stack use).
; Its size argument carries a checkpoint bit: split=1, coalesce=2, query=4.
; Shared compiler DP scratch is call-clobbered by this native import.
.setcpu "65816"
.smart
.macpack longbranch
.include "exec-abi.inc"
.include "tasks.inc"
.include "heap.inc"
.ifdef PORT_RACE
    .include "ports.inc"
.endif
.segment "PROBE"
.a16
.i16
.export checkpoint, consumer, native_dequeue
checkpoint:
.ifdef PORT_RACE
    .ifdef REGISTRY_RACE
        RACE_LIST = REGISTRY
        RACE_NODE = PORT
    .else
        RACE_LIST = PORT+16
        RACE_NODE = ITEM
    .endif
    ; Only the test message queue; scheduler/heap lists remain unstalled.
    lda 4,s
    cmp #.loword(RACE_LIST)
    beq port_pointer
    cmp #.loword(RACE_NODE)
    bne other_pointer
    lda 6,s
    and #$ff
    cmp #^RACE_NODE
    beq relevant_pointer
other_pointer:
    rtl
port_pointer:
    lda 6,s
    and #$ff
    cmp #^RACE_LIST
    bne other_pointer
relevant_pointer:
.endif
    lda f:ACTIVE
    and #$ff
    bne :+
    rtl
:
    lda f:E816_SWITCHING
    and #$ff
    cmp #1
    jne failed
    tdc
    cmp #E816_KERNEL_DP
    jne failed
    lda f:E816_VBI_COUNT
    sta $00
    lda f:E816_IRQ_COUNT
    sta $02
    lda f:WAKES
    sta $04
    lda f:CHECKPOINTS
    ora 8,s
    sta f:CHECKPOINTS
    jsr hardware_wait
    rtl

; JSL from the native GetMsg link-write checkpoint. Preserve its local DP,
; registers and flags. The native queue body has no compiler-domain scratch.
native_dequeue:
    php
    rep #$30
    pha
    phx
    phy
    phd
    lda f:ACTIVE
    and #$ff
    beq native_done
.ifdef PORT_RACE
    .ifdef ATOMIC_PORTS
        lda 1                  ; shared transaction's validated port
        cmp #.loword(PORT)
    .else
        lda 10
        cmp #.loword(ITEM)
    .endif
    bne native_done
    .ifdef ATOMIC_PORTS
        lda 3
    .else
        lda 12
    .endif
    and #$ff
    cmp #^PORT
    bne native_done
.endif
    tsc
    sec
    sbc #6
    tcs
    tcd
    lda f:E816_SWITCHING
    and #$ff
    cmp #1
    jne failed
    lda f:E816_VBI_COUNT
    sta 1
    lda f:E816_IRQ_COUNT
    sta 3
    lda f:WAKES
    sta 5
    ; Shared wait code uses offsets 0/2/4; point D one byte into our frame.
    tdc
    inc a
    tcd
    lda f:CHECKPOINTS
    .ifdef ATOMIC_PORTS
        ora #3
    .else
        ora #2
    .endif
    sta f:CHECKPOINTS
    jsr hardware_wait
    tsc
    clc
    adc #6
    tcs
native_done:
    pld
    ply
    plx
    pla
    plp
    rtl

hardware_wait:
    sep #$20
    lda #0
    sta f:$d20f
    sta f:$d205
    sta f:$d206
    sta f:$d207
    lda #6
    sta f:$d204
    lda #$28
    sta f:$d208
    lda #$23
    sta f:$0232
    sta f:$d20f
    sta f:$d20a
    sta f:$d209
    lda f:$0010
    ora #$10
    sta f:$0010
    sta f:$d20e
    lda #$5a
    sta f:$d20d
    rep #$20
wait_entries:
    wai
    .ifdef ATOMIC_PORTS
        ; IRQ must remain deferred throughout the partially updated list.
        lda f:E816_IRQ_COUNT
        cmp $02
        bne failed
        lda f:E816_VBI_COUNT
        cmp $00
        beq wait_entries
    .else
    lda f:E816_IRQ_COUNT
    cmp $02
    beq wait_entries
    lda f:E816_VBI_COUNT
    cmp $00
    beq wait_entries
    .endif
    lda f:WAKES             ; the IRQ/NMI must not enter Task policy here
    cmp $04
    bne failed
    rts
failed:
    lda #$ff75
    jml FINISH

; Prepend a bounded buffer read to the existing IRQ signal post. The fixture
; retains this allocation until Release has quiesced the producer.
consumer:
    rep #$20
    .repeat 4, I
        lda f:BUFFER+I*2
        cmp #$a55a
        bne failed
    .endrepeat
    ; Memory COP from IRQ context must reject before reading the bad packet,
    ; without borrowing or overwriting the interrupted heap policy's DP.
    ldx #0
    ldy #T_PROFILE_TAG
.ifdef PORT_RACE
    lda #P_SERVICE_PUT_MSG
.else
    lda #H_SERVICE_AVAIL_MEM
.endif
    cop E816_COP
    cmp #E816_ERROR_CONTEXT
    bne failed
    lda f:IRQREADS
    inc a
    sta f:IRQREADS
    ; Original entry: LDX binding / REP #$20 / PHD / TSC. The injected COP
    ; changes X, so restore the producer selection before continuing.
    ldx #T_SERIAL_BINDING-T_BASE
    phd
    tsc
    jml POST_CONTINUE
