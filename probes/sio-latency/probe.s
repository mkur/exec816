; Disposable two-context serial latency experiment. No public Exec ABI.
; Worker COP $50 = atomic consume-or-block. IRQ post = one hardcoded bit.
; Complete native frames remain on the suspended contexts' own stacks.
.setcpu "65816"
.smart
.export start, done, native_irq, native_nmi, wait_call, worker_wake
.export irq_post, emulation_post, wait_blocked, background, nmi_return
.export stream_start
.export STATE, SENT, POSTS, WAITS, NMIS, BG_PROGRESS, WORK_S, BG_S

.ifndef DIVISOR
DIVISOR = 0
.endif
.ifndef BYTE_COUNT
BYTE_COUNT = 4096
.endif
.ifndef VBI
VBI = 1
.endif
.ifndef ROM_IRQ
ROM_IRQ = 0
.endif
.ifndef BUSY
BUSY = 1
.endif
.ifndef STALL
STALL = 0
.endif
.ifndef CRITICAL
CRITICAL = 0
.endif
.ifndef PHASE
PHASE = 0
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
    ldx #$e
:
    sta $0100,x              ; OS page-one bottom guard
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
    lda POKMSK
    sta OLD_MASK
    lda $42
    sta OLD_CRITIC
    lda #CRITICAL
    sta $42
    lda OLD_MASK
    ; Own serial/timer configuration for this disposable run. Keep keyboard IRQs.
    and #$c0
    sta POKMSK
    sta IRQEN
    stz $d20f
    stz $d204
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
    sta $d209

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
    lda #$c0 | $10
    sta f:POKMSK
    sta f:IRQEN
.if VBI
    lda #$40
    sta f:NMIEN
.endif
stream_start:
    .repeat PHASE*4
        nop
    .endrepeat
    lda #0
    sta f:SEROUT             ; prime actual POKEY transmission
    rep #$20
    lda #1
    sta f:SENT
    cli
worker_next:
    rep #$30
    lda #$abcd
    ldx #$1234
    ldy #$5678
wait_call:
    cop $50
worker_wake:
    ; Trace observes the restored registers before this first worker instruction.
    lda f:SENT
    cmp #BYTE_COUNT
    bcc :+
    jmp finish
:
    sep #$20
    sta f:SEROUT             ; next byte is supplied by the worker, never the ISR
    rep #$20
    lda f:SENT
    inc a
    sta f:SENT
    bra worker_next

background:
.if STALL
    sei
    .repeat STALL
        nop
    .endrepeat
    cli
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
.if !ROM_IRQ
    sep #$20
    lda IRQST
    and #$10
    bne through_rom
    lda POKMSK
    and #$ef
    sta IRQEN
    lda POKMSK
    sta IRQEN
irq_post:
    lda #1
    sta PENDING
    rep #$20
    inc POSTS
    jmp maybe_wake
.else
irq_post:
.endif
through_rom:
    rep #$30
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

; ROM's emulation IRQ dispatcher already saved A and acknowledged serial ready.
; No task switching or native-frame manipulation in this callback.
.a8
.i8
emulation_post:
    lda #1
    sta PENDING
    inc POSTS
    bne :+
    inc POSTS+1
:
    pla
    rti

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
    sep #$20
:
    lda f:IRQST
    and #8
    bne :-                   ; finish the final byte; no streaming poll path
    sei
    rep #$30
    domain_zero
    sep #$20
    stz NMIEN
    lda OLD_MASK
    sta POKMSK
    sta IRQEN
    lda OLD_CRITIC
    sta $42
    lda #3
    sta $0232
    sta $d20f
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
