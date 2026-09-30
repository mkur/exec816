; Task-only port bindings share the checked caller-domain mechanism of the
; memory imports. No invocation or message pointer is retained after COP.
.include "ports.inc"
.include "ports-storage.inc"
.segment "SIGNAL_CODE"
.a16
.i16
heap_packet ports_put_msg, P_SERVICE_PUT_MSG
heap_packet ports_get_msg, P_SERVICE_GET_MSG
heap_packet ports_reply_msg, P_SERVICE_REPLY_MSG
heap_packet ports_delete_check, P_SERVICE_DELETE_CHECK
heap_packet ports_add_port, P_SERVICE_ADD_PORT
heap_packet ports_rem_port, P_SERVICE_REM_PORT
heap_packet ports_find_port, P_SERVICE_FIND_PORT

.export ports_create_msg_port, ports_create_msg_port_end
.export ports_delete_msg_port, ports_delete_msg_port_end
ports_create_msg_port:
    heap_context
    jml PORTS_CREATE
ports_create_msg_port_end:
ports_delete_msg_port:
    heap_context
    jml PORTS_DELETE
ports_delete_msg_port_end:

.export ports_wait_port, ports_wait_port_end, ports_wait_empty
; Eight invocation-local bytes, plus one nested JSL return (11-byte peak).
; The original port argument remains at 12..14,S. No kernel continuation
; survives a head check: blocking uses the caller's existing Wait service.
ports_wait_port:
    heap_context
    tsc
    .if STACK_CHECKS
    cmp A816_DP_STACK_CEILING_OFFSET
    bcc :+
    beq :+
    brl ports_wait_overflow
:
    sec
    sbc #11
    bcc ports_wait_overflow
    cmp A816_DP_STACK_FLOOR_OFFSET
    bcc ports_wait_overflow
    clc
    adc #3
    .else
    sec
    sbc #8
    .endif
    tcs
ports_wait_check:
    tsc
    clc
    adc #12
    tax
    ldy #T_PROFILE_TAG
    lda #P_SERVICE_WAIT_HEAD
    cop E816_COP
    sta 1,s
    txa
    and #$ff
    ora 1,s
    beq ports_wait_empty
    lda 1,s
    tay
    tsc
    clc
    adc #8
    tcs
    tya
    rtl
ports_wait_empty:
    ; No signal is cleared between observing empty and entering Wait.
    lda 12,s
    sta A816_DP_POINTER0_OFFSET
    sep #$20
    lda 14,s
    sta A816_DP_POINTER0_OFFSET+2
    rep #$20
    ldy #P_MSGPORT_MP_SIGBIT
    lda [A816_DP_POINTER0_OFFSET],y
    and #$ff
    tax
    lda #1
    sta 1,s
    lda #0
    sta 3,s
    cpx #0
    beq ports_wait_block
ports_wait_bit:
    lda 1,s
    asl a
    sta 1,s
    lda 3,s
    rol a
    sta 3,s
    dex
    bne ports_wait_bit
ports_wait_block:
    jsl tasks_wait
    brl ports_wait_check
    .if STACK_CHECKS
ports_wait_overflow:
    lda #11
    jml stack_overflow
    .endif
ports_wait_port_end:
