; Disposable SIO engine. E=0, M=1, X=0, I=1, D=STATE, DBR=0.
; Timer 1 free-runs at 224 PAL base cycles; enabled only for phase delays.
; Timer 2 free-runs at 7168 cycles for the active deadline. STIMER is used
; once at initialization, never to arm an alarm or change serial direction.
PHASE_STATE = STATE+40
REMAIN = STATE+42
ACTUAL = STATE+44
CHECKSUM = STATE+46
VALUE = STATE+47
ERROR = STATE+48
DIRECTION = STATE+49
ALARM_LEFT = STATE+50
TIME_LEFT = STATE+51
TRANS = STATE+52
EMU_COUNT = STATE+54
TIMER_COUNT = STATE+56
WATCH_COUNT = STATE+58
RX_COUNT = STATE+60
OLD_SERIN = STATE+62
OLD_SEROC = STATE+64
OLD_TIMER1 = STATE+66
OLD_TIMER2 = STATE+68
OLD_PBCTL = STATE+70
OLD_SKCTL = STATE+71
OLD_DEFERRED = STATE+72
DEFERRED_COUNT = STATE+74
RELEASE_CLOCK = STATE+76
ROM_IRQ_COUNT = STATE+78
RESULTS = STATE+80          ; four {error, actual_lo, actual_hi, reserved}
COMMAND = STATE+144         ; five-byte command frame
SAVED_POKEY = $2100         ; 32-byte reservation for preflight snapshot
TX_BUFFER = $04ffc0
RX_BUFFER = $06ffc0
VERIFY_BUFFER = $08ffc0

CURSOR=STATE+132

P_IDLE=0
P_SETUP=1
P_COMMAND=2
P_COMMAND_DRAIN=3
P_HOLD=4
P_ACK=5
P_WRITE_DELAY=6
P_WRITE=7
P_WRITE_DRAIN=8
P_DATA_ACK=9
P_RESULT=10
P_READ=11
P_CHECKSUM=12
P_TERMINAL=13
OWNED_MASK=$3b

.export PHASE_STATE, ACTUAL, ERROR, TRANS, EMU_COUNT, TIMER_COUNT, WATCH_COUNT
.export RX_COUNT, RESULTS, DEFERRED_COUNT, SAVED_POKEY, TX_BUFFER, RX_BUFFER, VERIFY_BUFFER
.export ROM_IRQ_COUNT
.export transaction_start, command_begin, command_end, write_begin, terminal_post
.export rx_service, tx_service, alarm_service, watchdog_service

; Update both the authoritative IRQ shadow and hardware. A contains full mask.
set_mask:
    sta a:POKMSK
    sta IRQEN
    rts

; Arm a number of free-running fine ticks, with no serial/timer reset.
arm_alarm:
    sta ALARM_LEFT
    lda a:POKMSK
    and #$fe
    sta IRQEN
    ora #1
    jmp set_mask

; Caller initializes COMMAND/DIRECTION and receive pointer before publication.
transaction_start:
    stz ERROR
    stz CHECKSUM
    rep #$20
    stz ACTUAL
    sep #$20
    lda #250
    sta TIME_LEFT
    lda #$23
    sta $0232
    sta $d20f
    sta $d20a              ; clear sticky serial errors
    lda #P_SETUP
    sta PHASE_STATE
    lda a:POKMSK
    and #($ff-OWNED_MASK)
    ora #2
    jsr set_mask
    lda $d303
    and #$c7
    ora #$30              ; CB2 output low: COMMAND asserted
    sta $d303
    lda #8
    jmp arm_alarm

; Native router acknowledges latched sources before calling these routines.
alarm_service:
    rep #$20
    inc TIMER_COUNT
    sep #$20
    dec ALARM_LEFT
    beq :+
    rts
:
    lda a:POKMSK
    and #$fe
    jsr set_mask
    lda PHASE_STATE
    cmp #P_SETUP
    beq command_begin
    cmp #P_HOLD
    beq command_end
    cmp #P_WRITE_DELAY
    beq write_begin
    jmp protocol_error
command_begin:
    rep #$20
    lda #COMMAND
    sta CURSOR
    lda #5
    sta REMAIN
    sep #$20
    stz CURSOR+2
    lda #P_COMMAND
    sta PHASE_STATE
    lda a:POKMSK
    ora #$10
    jsr set_mask
    jmp tx_service
command_end:
    lda #$13              ; RX configured BEFORE COMMAND rises
    sta $0232
    sta $d20f
    lda #P_ACK
    sta PHASE_STATE
    lda a:POKMSK
    ora #$20
    jsr set_mask
    lda $d303
    ora #$38
    sta $d303
    rts
write_begin:
    lda #$23
    sta $0232
    sta $d20f
    rep #$20
    lda #.loword(TX_BUFFER)
    sta CURSOR
    lda #129
    sta REMAIN
    sep #$20
    lda #^TX_BUFFER
    sta CURSOR+2
    lda #P_WRITE
    sta PHASE_STATE
    lda a:POKMSK
    and #$df
    ora #$10
    jsr set_mask
    jmp tx_service

tx_service:
    rep #$20
    lda REMAIN
    sep #$20
    bne tx_byte
    ; Last byte has entered the shifter. Only now enable output-complete.
    inc PHASE_STATE
    lda a:POKMSK
    and #$ef
    ora #8
    jmp set_mask
tx_byte:
    lda [$84]
    sta SEROUT
    rep #$20
    inc SENT
    inc CURSOR
    bne :+
    sep #$20
    inc CURSOR+2
    rep #$20
:
    dec REMAIN
    sep #$20
    rts

tx_complete:
    lda a:POKMSK
    and #$f7
    jsr set_mask
    lda PHASE_STATE
    cmp #P_COMMAND_DRAIN
    bne :+
    lda #P_HOLD
    sta PHASE_STATE
    lda #7                ; six to seven fine periods plus bounded service
    jmp arm_alarm
:
    cmp #P_WRITE_DRAIN
    bne protocol_error
    lda #$13
    sta $0232
    sta $d20f
    lda #P_DATA_ACK
    sta PHASE_STATE
    lda a:POKMSK
    ora #$20
    jmp set_mask

rx_service:
    lda $d20d             ; SERIN read once, before slower bookkeeping
    sta VALUE
    rep #$20
    inc RX_COUNT
    sep #$20
    lda $d20f
    and #$a0
    cmp #$a0
    beq :+
    lda #6                ; framing/overrun diagnostic error
    jmp fail
:
    lda PHASE_STATE
    cmp #P_ACK
    beq ack_received
    cmp #P_DATA_ACK
    beq data_ack_received
    cmp #P_RESULT
    beq result_received
    cmp #P_READ
    bne :+
    jmp data_received
:
    cmp #P_CHECKSUM
    bne :+
    jmp checksum_received
:
protocol_error:
    lda #7
    jmp fail
ack_received:
    lda VALUE
    cmp #$4e
    beq nak_received
    cmp #$41
    bne protocol_error
    lda DIRECTION
    cmp #2
    bne to_result
    lda #P_WRITE_DELAY
    sta PHASE_STATE
    lda #10               ; 1.1–1.3 ms from ACK: selected profile window
    jmp arm_alarm
data_ack_received:
    lda VALUE
    cmp #$4e
    beq nak_received
    cmp #$41
    bne protocol_error
    rep #$20
    lda #128
    sta ACTUAL
    sep #$20
to_result:
    lda #P_RESULT
    sta PHASE_STATE
    rts
nak_received:
    lda #2
    jmp fail
result_received:
    lda VALUE
    cmp #$43
    beq :+
    cmp #$45
    bne protocol_error
    lda #3
    sta ERROR             ; drain expected data even after E
:
    lda DIRECTION
    cmp #1
    beq :+
    jmp terminal_post
:
    lda #P_READ
    sta PHASE_STATE
    stz CHECKSUM
    rep #$20
    lda #.loword(RX_BUFFER)
    sta CURSOR
    lda #128
    sta REMAIN
    sep #$20
    lda #^RX_BUFFER
    sta CURSOR+2
    lda TRANS
    bne :+
    lda #4
    sta REMAIN
:
    cmp #3
    bne :+
    lda #^VERIFY_BUFFER
    sta CURSOR+2
:
    rts
data_received:
    lda VALUE
    sta [$84]
    clc
    adc CHECKSUM
    adc #0
    sta CHECKSUM
    rep #$20
    inc ACTUAL
    inc CURSOR
    bne :+
    sep #$20
    inc CURSOR+2
    rep #$20
:
    dec REMAIN
    sep #$20
    bne :+
    lda #P_CHECKSUM
    sta PHASE_STATE
:
    rts
checksum_received:
    lda VALUE
    cmp CHECKSUM
    beq terminal_post
    lda ERROR
    bne terminal_post
    lda #4
    jmp fail

watchdog_service:
    rep #$20
    inc WATCH_COUNT
    sep #$20
    dec TIME_LEFT
    bne :+
    lda #1
    jmp fail
:
    rts
fail:
    sta ERROR
terminal_post:
    lda a:POKMSK
    and #($ff-OWNED_MASK)
    jsr set_mask
    lda #P_TERMINAL
    sta PHASE_STATE
    lda #1
    sta PENDING
    rep #$20
    inc POSTS
    sep #$20
    rts
