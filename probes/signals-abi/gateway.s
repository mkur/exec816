; ABI-only COP responder. It implements test echoes, never task policy.
.setcpu "65816"
.smart
.include "task-abi.inc"
.export probe_cop, probe_cop_end
.segment "CODE"
.include "signal-gateway.inc"
.a16
.i16
probe_cop:
    rep #$30
    pha
    phx
    phy
    phd
    phb
    cld
    cpy #T_PROFILE_TAG
    beq :+
    brk $ff
:
    ; The generated wrappers supply a bank-zero outgoing packet in X/Y.
    ; No DP/DBR scratch and no shared kernel activation are needed.
    lda T_FRAME_A_FULL,s
    cmp #T_SERVICE_ALLOC_SIGNAL
    beq allocate
    cmp #T_SERVICE_FREE_SIGNAL
    beq free
    cmp #T_SERVICE_SET_SIGNAL
    beq set
    cmp #T_SERVICE_SIGNAL
    beq signal
    cmp #T_SERVICE_WAIT
    beq wait
    brk $ff                 ; unexpected ABI probe call
allocate:
    lda f:0,x
    and #$ff
    eor #$ff
    sta T_FRAME_A_FULL,s
    bra restore
free:
    sep #$20
    lda f:0,x
    sta f:FREED
    rep #$20
    bra restore
set:
    lda f:0,x
    eor f:4,x
    sta T_FRAME_A_FULL,s
    lda f:2,x
    eor f:6,x
    sta T_FRAME_X,s
    bra restore
signal:
    lda f:0,x
    sta f:TARGET
    sep #$20
    lda f:2,x
    sta f:TARGET+2
    rep #$20
    lda f:4,x
    sta f:MASKS+24
    lda f:6,x
    sta f:MASKS+26
    bra restore
wait:
    lda f:0,x
    eor #$5678
    sta T_FRAME_A_FULL,s
    lda f:2,x
    eor #$1234
    sta T_FRAME_X,s
restore:
    plb
    pld
    ply
    plx
    pla
    rti
probe_cop_end:
