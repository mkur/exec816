; Disposable XEX for the no-cartridge bank-zero audit, not a hosted adapter.
; Exercise CPU reads/writes, native D/S addressing and the real ROM CIO/VBI.
.setcpu "65816"
.export start, done
RESULT = $2000
BASE = $9000
BYTES = $2c20
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
    lda #$01ef
    tcs
    lda #0
    tcd
    phk
    plb
    stz RESULT
    stz RESULT+2
    lda $02e5
    cmp #BASE+BYTES-1
    bcs :+
    jmp fail
:
    lda #$a55a
    jsr pattern
    lda #$5aa5
    jsr pattern
    ; Native DP/stack addressing in the candidate range. NMI is masked;
    ; asynchronous hosted Task domain switching is outside this probe.
    lda #$b000
    tcd
    lda #$bbef
    tcs
    lda #$1234
    sta $00
    pea $5678
    jsr private_stack
    pla
    cmp #$5678
    bne fail
    lda $02
    cmp #$4321
    bne fail
    lda #$01ef
    tcs
    lda #0
    tcd
    lda #1
    sta RESULT+2
    ; Restore a full address-dependent canary after using the private D/S.
    lda #$5aa5
    jsr pattern
    sep #$20
.a8
    lda #11
    sta $0342
    lda #<message
    sta $0344
    lda #>message
    sta $0345
    lda #message_end-message
    sta $0348
    stz $0349
    lda #$40
    sta $d40e
    cli
    rep #$30
.a16
    ldx #0
    ldy #0
    pea $e456
    cop $00
    tya
    sta RESULT+4
    pla
    sep #$20
.a8
    lda $14
    sta RESULT+6
    ldx #120
wait_tick:
    lda $14
wait_change:
    cmp $14
    beq wait_change
    dex
    bne wait_tick
    lda $14
    sta RESULT+7
    sei
    stz $d40e
    rep #$30
.a16
    lda #$5aa5
    sta seed
    jsr verify
    lda #$ffff
    sta RESULT
done:
    bra done
fail:
    lda #$eeee
    sta f:RESULT
    jmp done
private_stack:
    lda $00
    cmp #$1234
    bne fail
    lda #$4321
    sta $02
    rts
pattern:
    sta seed
    ldx #BYTES-2
fill:
    txa
    eor seed
    sta BASE,x
    dex
    dex
    bpl fill
verify:
    ldx #BYTES-2
compare:
    txa
    eor seed
    cmp BASE,x
    bne fail
    dex
    dex
    bpl compare
    rts
seed:
    .word 0
message:
    .byte "HIGH RAM ROM CIO/VBI",$9b
message_end:
