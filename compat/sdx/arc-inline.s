; ARC 4.50 block 1 +$05ED: replacement for the six-byte inline helper.
; Included in the guest bank, E=1, D page-aligned, DBR=PBR=guest bank.
; No pushes: 3,S / 4,S remain the outer JSR's saved return address.
; ARC_COUNT is the relocated address of block 2 +4294.
; A=count (six in the audited callers), decimal clear, enough page-one space.
; Result matches the original: A=first argument byte, X=entry S low, Y=0,
; N=0, Z=1, C/V from return-address addition; count and FE/FF preserved.
.setcpu "65816"
.a8
.i8
    sta a:ARC_COUNT
    clc
    lda 3,s
    sta $fe
    adc a:ARC_COUNT
    sta 3,s
    lda 4,s
    sta $ff
    adc #0
    sta 4,s
    ldy a:ARC_COUNT
@copy:
    tyx
    lda ($fe),y
    sta $ef,x
    dey
    bne @copy
    tsx
    ldy #0
    rts
    nop
    nop
