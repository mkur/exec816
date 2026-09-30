; Disposable buffered SIO feasibility experiment. No public Exec device ABI.
; Worker COP $50 = atomic consume-or-block. IRQ post = one hardcoded bit.
; Complete native frames remain on the suspended contexts' own stacks.
.setcpu "65816"
.smart
.export start, done, native_irq, native_nmi, wait_call, worker_wake
.export irq_post, emulation_post, wait_blocked, background, nmi_return
.export stream_start
.export critic_enter, critic_enter_next, critic_leave, critic_leave_next
.export STATE, SENT, POSTS, WAITS, NMIS, BG_PROGRESS, WORK_S, BG_S

.ifndef DIVISOR
DIVISOR = 0
.endif
.ifndef VBI
VBI = 1
.endif
.ifndef BUSY
BUSY = 1
.endif
.ifndef STALL
STALL = 0
.endif
.ifndef PHASE
PHASE = 0
.endif
.ifndef VCOUNT_PHASE
VCOUNT_PHASE = -1
.endif
.ifndef SCENARIO
SCENARIO = 0
.endif

STATE = $2000
SENT = STATE+2
POSTS = STATE+4
WAITS = STATE+6
NMIS = STATE+8
BG_PROGRESS = STATE+10
WORK_S = STATE+12
BG_S = STATE+14
PENDING = STATE+16
BLOCKED = STATE+17
CURRENT = STATE+18             ; 0=worker, 1=background/idle
OS_DEPTH = STATE+19
OLD_NMI = STATE+20
OLD_IRQ = STATE+23
OLD_COP = STATE+26
OLD_VBI = STATE+29
OLD_SEROR = STATE+31
OLD_MASK = STATE+33
OLD_CRITIC = STATE+34
PTR = STATE+128

VNMIN = $0259
VIRQN = $025c
VCOPN = $0256
VVBLKI = $0222
VSEROR = $020c
POKMSK = $0010
IRQST = $d20e
IRQEN = $d20e
SEROUT = $d20d
NMIEN = $d40e

; Extra PHP retains the entry widths for chaining an untouched OS vector.
; Saved layout from S: DBR 1, D 2, Y 4, X 6, A 8, entry P 10,
; interrupted P 11, PC 12, PBR 14. Interrupt entry already saved P/PC/PBR.
.macro save_full
    php
    rep #$30
    pha
    phx
    phy
    phd
    phb
.endmacro
.macro restore_full
    rep #$30
    plb
    pld
    ply
    plx
    pla
    plp
.endmacro
.macro domain_zero
    cld
    lda #0
    tcd
    phk
    plb
.endmacro

.segment "CODE"
.a8
.i8
start:
    sei
    cld
    stz NMIEN
    clc
    xce
    rep #$30
    lda #$01ef
    tcs
    domain_zero
    lda #0
    ldx #$fe
:
    sta STATE,x
    dex
    dex
    bpl :-
    lda $02e7
    cmp #STATE+1
    bcs bad_memory
    lda $02e5
    cmp #$5010
    bcc bad_memory
    bra memory_ok
bad_memory:
    lda #$eeee
    sta STATE
    jmp done
memory_ok:
    lda #$a5a5
    ldx #$11e
:
    sta $21f0,x              ; worker DP and guards
    sta $23f0,x              ; background DP and guards
    dex
    dex
    bpl :-
    ldx #$61e
:
    sta $41f0,x              ; worker stack $4200-$47ff and guards
    sta $49f0,x              ; background stack $4a00-$4fff and guards
    dex
    dex
    bpl :-
    ldx #$ee
:
    sta $0100,x              ; reserved OS stack and bottom guard; no live calls
    dex
    dex
    bpl :-
    lda VNMIN
    sta OLD_NMI
    lda VIRQN
    sta OLD_IRQ
    lda VCOPN
    sta OLD_COP
    lda VVBLKI
    sta OLD_VBI
    lda VSEROR
    sta OLD_SEROR
    lda #native_nmi
    sta VNMIN
    lda #native_irq
    sta VIRQN
    lda #wait_gateway
    sta VCOPN
    lda #vbi_hook
    sta VVBLKI
    lda #emulation_post
    sta VSEROR
    lda $020a
    sta OLD_SERIN
    lda $020e
    sta OLD_SEROC
    lda $0210
    sta OLD_TIMER1
    lda $0212
    sta OLD_TIMER2
    lda $0224
    sta OLD_DEFERRED
    lda #emulation_rx
    sta $020a
    lda #emulation_complete
    sta $020e
    lda #emulation_alarm
    sta $0210
    lda #emulation_watchdog
    sta $0212
    lda #deferred_hook
    sta $0224
    sep #$20
    lda VNMIN+2
    sta OLD_NMI+2
    lda VIRQN+2
    sta OLD_IRQ+2
    lda VCOPN+2
    sta OLD_COP+2
    stz VNMIN+2
    stz VIRQN+2
    stz VCOPN+2
    lda a:POKMSK
    sta OLD_MASK
    lda a:$42
    sta OLD_CRITIC
    lda $0232
    sta OLD_SKCTL
    lda $d303
    sta OLD_PBCTL
critic_enter:
    lda #1
    sta a:$42
    lda OLD_MASK
    ; Own serial/timer configuration for this disposable run. Keep keyboard IRQs.
    and #$c0
    sta a:POKMSK
    sta IRQEN
    stz $d20f
    lda #7
    sta $d200              ; fine alarm: 8 * 28 base cycles
    stz $d201
    lda #$ff
    sta $d202              ; coarse deadline: 256 * 28 base cycles
    stz $d203
    stz $d205
    stz $d206
    stz $d207
    lda #DIVISOR
    sta $d204
    lda #$28                 ; linked timers 3+4, base clock
    sta $d208
    lda #$23                 ; serial output clock from timer 4, keyboard active
    sta $0232
    sta $d20f
    sta $d20a
    sta $d209              ; initialize once; no reset during a transaction

    ldx #255
    lda #$a5
:
    sta f:TX_BUFFER-32,x
    sta f:RX_BUFFER-32,x
    sta f:VERIFY_BUFFER-32,x
    dex
    bpl :-
    stz CHECKSUM
    ldx #0
:
    txa
    eor #$a7
    sta f:TX_BUFFER,x
    clc
    adc CHECKSUM
    adc #0
    sta CHECKSUM
    inx
    cpx #128
    bcc :-
    lda CHECKSUM
    sta f:TX_BUFFER+128

    ; Construct one background RTI continuation without admitting a public Task.
    rep #$30
    lda #$4ffe
    tcs
    sep #$20
    lda #0
    pha                      ; PBR
    rep #$20
    lda #background
    pha                      ; PC
    sep #$20
    lda #0
    pha                      ; interrupted P: native 16-bit, IRQs enabled
    lda #4
    pha                      ; handler-entry P
    rep #$20
    lda #$abcd
    pha
    lda #$1234
    pha
    lda #$5678
    pha
    lda #$2400
    pha
    sep #$20
    lda #$12
    pha
    rep #$20
    tsc
    sta BG_S
    lda #$47fe
    tcs
    lda #$2200
    tcd
    sep #$20
    lda #$34
    pha
    plb
.if VBI
    lda #$40
    sta f:NMIEN
.endif
stream_start:
    .repeat PHASE*4
        nop
    .endrepeat
.if VCOUNT_PHASE >= 0
    ; Align to a real PAL raster phase as well as sweeping fine IRQ offsets.
    ; No transaction is active; keep unrelated IRQs serviceable while waiting.
    cli
vcount_wait:
    lda f:$d40b
    cmp #VCOUNT_PHASE
    bne vcount_wait
.endif
worker_next:
    sei
    rep #$30
    domain_zero
    lda #STATE
    tcd
    sep #$20
critic_enter_next:
    lda #1
    sta a:$42
    stz PENDING
    lda #$31
.if SCENARIO=1
    lda #$32               ; absent D2: silent-peripheral timeout
.endif
    sta COMMAND
    lda #$52
    sta COMMAND+1
    lda #4
    sta COMMAND+2
    stz COMMAND+3
    lda #1
    sta DIRECTION
    lda TRANS
    bne :+
    lda #$53
    sta COMMAND+1
    stz COMMAND+2
:
    lda TRANS
    cmp #2
    bne :+
    lda #$50
    sta COMMAND+1
    lda #2
    sta DIRECTION
:
.if SCENARIO=2
    stz COMMAND+1          ; unsupported command, no data: NAK
    stz DIRECTION
.elseif SCENARIO=3
    lda #$51               ; Happy 1050 quiet: ACK/Complete, no data frame
    sta COMMAND+1
    stz DIRECTION
.endif
    stz CHECKSUM
    ldx #0
:
    lda COMMAND,x
    clc
    adc CHECKSUM
    adc #0
    sta CHECKSUM
    inx
    cpx #4
    bcc :-
    sta COMMAND+4
    jsr transaction_start
    rep #$20
    lda #$2200
    tcd
    sep #$20
    lda #$34
    pha
    plb
    rep #$30
    lda #$abcd
    ldx #$1234
    ldy #$5678
    cli
wait_call:
    cop $50
worker_wake:
    ; One wake per terminal transaction, never one wake per byte.
    rep #$30
    domain_zero
    sep #$20
    lda TRANS
    asl
    asl
    tax
    lda ERROR
    sta RESULTS,x
    rep #$20
    lda ACTUAL
    sta RESULTS+1,x
    sep #$20
    lda ERROR
    beq :+
    jmp finish
:
.if SCENARIO=3
    jmp finish
.endif
    inc TRANS
    lda TRANS
    cmp #4
    bcc :+
    jmp finish
:
    lda OLD_CRITIC
    sta a:$42
critic_leave_next:
    rep #$20
    lda NMIS
    sta RELEASE_CLOCK
between_transactions:
    wai
    lda NMIS
    sec
    sbc RELEASE_CLOCK
    cmp #2
    bcc between_transactions
    jmp worker_next

background:
.if STALL
    sep #$20
    lda f:PHASE_STATE
    cmp #P_READ
    beq :+
    jmp no_stall
:
    sei
    .repeat STALL
        nop
    .endrepeat
    cli
no_stall:
    rep #$20
.endif
.if BUSY
    lda f:BG_PROGRESS
    inc a
    sta f:BG_PROGRESS
.else
    wai
.endif
    jmp background

wait_gateway:
    save_full
    domain_zero
    lda 12,s
    dec a
    sta PTR
    sep #$20
    lda 14,s
    sta PTR+2
    rep #$20
    lda #STATE
    tcd
    sep #$20
    lda [$80]
    cmp #$50
    beq our_wait
    restore_full
    jmp [OLD_COP]
our_wait:
    rep #$20
    lda #0
    tcd
    inc WAITS
    sep #$20
    lda PENDING
    bne consume_now
    lda #1
    sta BLOCKED
wait_blocked:
    sta CURRENT
    rep #$20
    tsc
    sta WORK_S
    lda BG_S
    tcs
    restore_full
    rti
consume_now:
    stz PENDING
    restore_full
    rti

native_irq:
    save_full
    domain_zero
    lda #STATE
    tcd
    sep #$20
    ; Serial first, then phase alarm/watchdog. No unbounded drain loop.
    lda IRQST
    eor #$ff
    and a:POKMSK
    and #$20
    beq :+
    lda a:POKMSK
    and #$df
    sta IRQEN
    lda a:POKMSK
    sta IRQEN
    jsr rx_service
:
    lda IRQST
    eor #$ff
    and a:POKMSK
    and #$10
    beq :+
    lda a:POKMSK
    and #$ef
    sta IRQEN
    lda a:POKMSK
    sta IRQEN
    jsr tx_service
:
    lda IRQST
    eor #$ff
    and a:POKMSK
    and #$08
    beq :+
    jsr tx_complete
:
    lda IRQST
    eor #$ff
    and a:POKMSK
    and #$01
    beq :+
    lda a:POKMSK
    and #$fe
    sta IRQEN
    lda a:POKMSK
    sta IRQEN
    jsr alarm_service
:
    lda IRQST
    eor #$ff
    and a:POKMSK
    and #$02
    beq :+
    lda a:POKMSK
    and #$fd
    sta IRQEN
    lda a:POKMSK
    sta IRQEN
    jsr watchdog_service
:
    lda IRQST
    eor #$ff
    and a:POKMSK
    and #($ff-OWNED_MASK)
    bne through_rom
    jmp maybe_wake
irq_post = terminal_post
through_rom:
    rep #$30
    domain_zero
    inc ROM_IRQ_COUNT
    tsc
    tax
    and #$ff00
    cmp #$0100
    beq :+
    lda #$01ef
    tcs
:
    phx
    sep #$20
    inc OS_DEPTH
    phk
    pea irq_return
    lda #4
    pha
    rep #$30
    jmp [OLD_IRQ]
irq_return:
    sei
    rep #$30
    sep #$20
    dec OS_DEPTH
    rep #$20
    pla
    tcs
    jmp maybe_wake

; ROM callbacks may enter in E=1 or native M=X=1. Retain old E in carry
; on the private saved flags, preserve hidden B and retire ROM before switching.
.a8
.i8
emulation_rx:
    lda #0
    bra emulation_common
emulation_post:
    lda #1
    bra emulation_common
emulation_complete:
    lda #2
    bra emulation_common
emulation_alarm:
    lda #3
    bra emulation_common
emulation_watchdog:
    lda #4
emulation_common:
    clc
    xce
    php
    rep #$30
    pha
    phx
    phy
    phd
    phb
    tay
    lda #STATE
    tcd
    phk
    plb
    inc EMU_COUNT
    sep #$20
    tya
    cmp #0
    bne :+
    jsr rx_service
    bra emulation_return
:
    cmp #1
    bne :+
    jsr tx_service
    bra emulation_return
:
    cmp #2
    bne :+
    jsr tx_complete
    bra emulation_return
:
    cmp #3
    bne :+
    jsr alarm_service
    bra emulation_return
:
    jsr watchdog_service
emulation_return:
    rep #$30
    plb
    pld
    ply
    plx
    pla
    sep #$30
    plp
    xce
    pla
    rti

.a8
.i8
deferred_hook:
    inc DEFERRED_COUNT
    bne :+
    inc DEFERRED_COUNT+1
:
    jmp (OLD_DEFERRED)

.a16
.i16
native_nmi:
    save_full
    domain_zero
    tsc
    tax
    and #$ff00
    cmp #$0100
    beq :+
    lda #$01ef
    tcs
:
    phx
    sep #$20
    inc OS_DEPTH
    phk
    pea nmi_return
    ; Preserve the original I bit in the OS's synthetic interrupt frame.
    lda f:11,x
    and #4
    pha
    rep #$30
    jmp [OLD_NMI]
nmi_return:
    sei
    rep #$30
    sep #$20
    dec OS_DEPTH
    rep #$20
    pla
    tcs
maybe_wake:
    sep #$20
    lda OS_DEPTH
    bne resume
    lda CURRENT
    beq resume
    lda PENDING
    beq resume
    lda BLOCKED
    beq resume
    lda 11,s
    and #4
    bne resume
    rep #$20
    tsc
    sta BG_S
    lda WORK_S
    tcs
    sep #$20
    stz CURRENT
    stz BLOCKED
    stz PENDING
resume:
    restore_full
    rti

.a8
.i8
vbi_hook:
    inc NMIS
    bne :+
    inc NMIS+1
:
    jmp (OLD_VBI)

.a16
.i16
finish:
    sei
    rep #$30
    domain_zero
    sep #$20
    lda OLD_PBCTL
    sta $d303
    lda a:POKMSK
    and #($ff-OWNED_MASK)
    sta a:POKMSK
    sta IRQEN
    ; Restore owned write-only settings from the recorded preflight snapshot.
    ldx #8
:
    lda SAVED_POKEY,x
    sta $d200,x
    dex
    bpl :-
    lda OLD_SKCTL
    sta $0232
    sta $d20f
    sta $d209
    lda OLD_CRITIC
    sta a:$42
critic_leave:
    rep #$20
    lda NMIS
    sta RELEASE_CLOCK
    sep #$20
    cli
finish_vbi:
    wai
    rep #$20
    lda NMIS
    sec
    sbc RELEASE_CLOCK
    cmp #2
    sep #$20
    bcc finish_vbi
    sei
    stz NMIEN
    lda OLD_MASK
    sta a:POKMSK
    sta IRQEN
    rep #$20
    lda OLD_NMI
    sta VNMIN
    lda OLD_IRQ
    sta VIRQN
    lda OLD_COP
    sta VCOPN
    lda OLD_VBI
    sta VVBLKI
    lda OLD_SEROR
    sta VSEROR
    lda OLD_SERIN
    sta $020a
    lda OLD_SEROC
    sta $020e
    lda OLD_TIMER1
    sta $0210
    lda OLD_TIMER2
    sta $0212
    lda OLD_DEFERRED
    sta $0224
    sep #$20
    lda OLD_NMI+2
    sta VNMIN+2
    lda OLD_IRQ+2
    sta VIRQN+2
    lda OLD_COP+2
    sta VCOPN+2
    rep #$20
    lda #$600d
    sta STATE
    ; A disposable XEX: remain on a known OS stack after restoring its vectors.
    lda #$01ef
    tcs
    lda #0
    tcd
    sec
    xce
.a8
.i8
    lda #$40
    sta NMIEN
    cli
done:
    jmp done

.a8
.i16
.include "engine.inc"
