; Shared message transactions. Task gateways retain SWITCHING; native producers
; hold IRQ_DEPTH or NI_ACTIVE. NI_PORT_BUSY excludes NMI continuations even at
; an admitted return boundary. Far accesses carry across bank boundaries.
.segment "NATIVE_WORK"
.a16
.i16

PORT_LOCAL = 24
PORT_ARG = PORT_LOCAL+6
PORT_PEAK = PORT_LOCAL+3+2

; Local layout: port 1..3, message 4..6, predecessor 7..9, successor 10..12,
; recipient 13..15, context 16..17, masks 18..21, kind 22, result 23..24.
.macro port_enter checked
.local okay, overflow
    .if STACK_CHECKS .and checked
        tsc
        tax
        cmp A816_DP_STACK_CEILING_OFFSET
        bcc :+
        bne overflow
:
        sec
        sbc #PORT_PEAK
        bcc overflow
        cmp A816_DP_STACK_FLOOR_OFFSET
        bcs okay
overflow:
        lda #PORT_PEAK
        jml stack_overflow
okay:
    .endif
    phd
    tsc
    sec
    sbc #PORT_LOCAL
    tcs
    tcd
    php
.endmacro

; Copy immutable arguments before masking. SWITCHING already excludes native
; continuation admission; IRQ producers may run until the first shared read.
.macro port_lock
    sei
    sep #$20
    lda #1
    sta f:NI_PORT_BUSY
    rep #$20
.endmacro

.macro port_argument offset, destination
    lda PORT_ARG+offset
    sta destination
    lda PORT_ARG+offset+2
    and #$ff
    sta destination+2
.endmacro

.macro port_unlock
    sep #$20
    lda #0
    sta f:NI_PORT_BUSY
    rep #$20
    plp
.endmacro

.macro port_leave
    tsc
    clc
    adc #PORT_LOCAL
    tcs
    pld
.endmacro

; Diagnostic-only instruction boundaries around every shared far link access.
; The production image reserves no probe slots or code.
.macro port_link_checkpoint point
    .if HEAP_PROBE
        .ident(.sprintf("port_link_probe_%u", point)):
        .export .ident(.sprintf("port_link_probe_%u", point))
        .repeat 4
            nop
        .endrepeat
    .endif
.endmacro

; Append(port *, message *, kind8), all inputs validated by Task policy.
; Task notification follows publication in policy. SWITCHING protects that
; ownership interval; the native reply entry publishes directly below.
.export ports_append, ports_append_end
ports_append:
    port_enter 1
    port_argument 0, 1
    port_argument 3, 4
    lda PORT_ARG+6
    sta 22
    port_lock
    jsr port_append_links
    port_unlock
    port_leave
    rtl
ports_append_end:

port_append_links:
    ldy #P_MSGPORT_MP_MSGLIST+6
    port_link_checkpoint 0
    lda [1],y
    port_link_checkpoint 1
    sta 7
    iny
    iny
    sep #$20
    port_link_checkpoint 2
    lda [1],y
    port_link_checkpoint 3
    sta 9
    rep #$20
    ; Construct the embedded tail sentinel as a full 24-bit pointer.
    lda 1
    clc
    adc #P_MSGPORT_MP_MSGLIST+3
    sta 10
    sep #$20
    lda 3
    adc #0
    sta 12
    lda 22
    ldy #6
    port_link_checkpoint 4
    sta [4],y
    port_link_checkpoint 5
    rep #$20
    lda 10
    port_link_checkpoint 6
    sta [4]
    port_link_checkpoint 7
    sep #$20
    lda 12
    ldy #2
    port_link_checkpoint 8
    sta [4],y
    port_link_checkpoint 9
    rep #$20
    lda 7
    ldy #3
    port_link_checkpoint 10
    sta [4],y
    port_link_checkpoint 11
    sep #$20
    lda 9
    ldy #5
    port_link_checkpoint 12
    sta [4],y
    port_link_checkpoint 13
    rep #$20
    lda 4
    port_link_checkpoint 14
    sta [7]
    port_link_checkpoint 15
    ldy #P_MSGPORT_MP_MSGLIST+6
    port_link_checkpoint 16
    sta [1],y
    port_link_checkpoint 17
    sep #$20
    lda 6
    ldy #2
    port_link_checkpoint 18
    sta [7],y
    port_link_checkpoint 19
    ldy #P_MSGPORT_MP_MSGLIST+8
    port_link_checkpoint 20
    sta [1],y
    port_link_checkpoint 21
    rep #$20
    rts

; Peek(port *) returns the head without transferring ownership.
.export ports_peek, ports_peek_end
ports_peek:
    port_enter 1
    port_argument 0, 1
    port_lock
    jsr port_head
    jmp port_pointer_return
ports_peek_end:

port_head:
    ldy #P_MSGPORT_MP_MSGLIST
    port_link_checkpoint 22
    lda [1],y
    port_link_checkpoint 23
    sta 4
    iny
    iny
    sep #$20
    port_link_checkpoint 24
    lda [1],y
    port_link_checkpoint 25
    sta 6
    rep #$20
    port_link_checkpoint 26
    lda [4]
    port_link_checkpoint 27
    sta 10
    ldy #2
    sep #$20
    port_link_checkpoint 28
    lda [4],y
    port_link_checkpoint 29
    sta 12
    rep #$20
    and #$ff
    ora 10
    bne :+
    stz 4
    stz 6
:
    rts

; Get(port *) is shared by the fast gateway and native test probes.
.export ports_take, ports_take_end
ports_take:
    port_enter 1
    bra port_take_body
.export ports_take_fast
ports_take_fast:
    ; The admitted fast gateway already owns a frame within the Task pool.
    ; Its local D is not a compiler DP. Total gateway + helper peak is below
    ; the existing 256-byte interrupt reserve; no domain-header read here.
    port_enter 0
port_take_body:
    port_argument 0, 1
    port_lock
    jsr port_head
    lda 4
    ora 6
    beq port_pointer_return
    jsr port_remove_links
port_pointer_return:
    port_unlock
    ldy 4
    lda 6
    and #$ff
    tax
    port_leave
    tya
    rtl
ports_take_end:

port_remove_links:
    port_link_checkpoint 30
    lda [4]
    port_link_checkpoint 31
    sta 10
    ldy #2
    sep #$20
    port_link_checkpoint 32
    lda [4],y
    port_link_checkpoint 33
    sta 12
    rep #$20
    ldy #3
    port_link_checkpoint 34
    lda [4],y
    port_link_checkpoint 35
    sta 7
    ldy #5
    sep #$20
    port_link_checkpoint 36
    lda [4],y
    port_link_checkpoint 37
    sta 9
    rep #$20
    lda 10
    port_link_checkpoint 38
    sta [7]
    port_link_checkpoint 39
    sep #$20
    lda 12
    ldy #2
    port_link_checkpoint 40
    sta [7],y
    port_link_checkpoint 41
    rep #$20
    lda 7
    ldy #3
    port_link_checkpoint 42
    sta [10],y
    port_link_checkpoint 43
    sep #$20
    lda 9
    ldy #5
    port_link_checkpoint 44
    sta [10],y
    port_link_checkpoint 45
    rep #$20
    rts

; Collect(message *) returns the pre-transaction kind and detaches a reply.
.export ports_collect, ports_collect_end
ports_collect:
    port_enter 1
    port_argument 0, 4
    port_lock
    ldy #6
    lda [4],y
    and #$ff
    sta 23
    cmp #P_NT_REPLYMSG
    bne port_kind_return
    jsr port_remove_links
    sep #$20
    lda #P_NT_FREEMSG
    ldy #6
    sta [4],y
    rep #$20
port_kind_return:
    port_unlock
    ldy 23
    port_leave
    tya
    rtl
ports_collect_end:

; Public assembly-only ReplyMsg. The complete interrupt context is owned by
; the adapter. Save every caller register before using activation-local work;
; never inspect compiler DP headers from an interrupt activation.
.export exec_reply_msg_native, exec_reply_msg_native_end
exec_reply_msg_native:
    php
    rep #$30
    pha
    phx
    phy
    phd
    phb
    cld
    lda 10,s
    and #$34
    cmp #4
    jne port_native_fault
    lda f:E816_IRQ_DEPTH
    bne :+
    lda f:NI_ACTIVE
    and #$ff
    jeq port_native_fault
:
    lda f:OS_BUSY
    and #$ff
    jne port_native_fault
    .if STACK_CHECKS
        tsc
        sec
        sbc #PORT_LOCAL+32
        jcc port_native_fault
        tay
        ; IRQs may interrupt either an admitted Task or the kernel domain.
        tsc
        cmp #E816_KERNEL_STACK_BASE
        bcc port_native_task_stack
        cmp #E816_KERNEL_STACK_TOP+1
        bcs port_native_task_stack
        cpy #E816_KERNEL_STACK_BASE
        jcc port_native_fault
        bra port_native_stack_ok
port_native_task_stack:
        lda f:E816_CURRENT
        and #$ff
        cmp #T_CAPACITY+1
        jcs port_native_fault
        .repeat T_SHIFT
            asl a
        .endrepeat
        tax
        ; stackFloor excludes the already reserved 256-byte interrupt area.
        lda f:T_BASE+T_TCB_STACKFLOOR,x
        sec
        sbc #$100
        phy
        cmp 1,s
        ply
        jcs port_native_fault
        tsc
        cmp f:T_BASE+T_TCB_STACKTOP,x
        bcc port_native_stack_ok
        jne port_native_fault
port_native_stack_ok:
    .endif
    tsc
    sec
    sbc #PORT_LOCAL
    tcs
    tcd
    sep #$20
    lda #0
    pha
    plb
    lda f:NI_PORT_BUSY
    jne port_native_fault
    rep #$20
    lda PORT_LOCAL+8
    sta 4
    and #1
    jne port_native_fault
    lda PORT_LOCAL+6
    cmp #$100
    jcs port_native_fault
    sta 6
    ora 4
    jeq port_native_fault
    lda 4
    clc
    adc #P_MESSAGE_BYTES-1
    bcc :+
    lda 6
    and #$ff
    cmp #$ff
    jeq port_native_fault
:
    ldy #P_MESSAGE_MN_REPLYPORT
    lda [4],y
    sta 1
    iny
    iny
    sep #$20
    lda [4],y
    sta 3
    rep #$20
    and #$ff
    ora 1
    bne port_native_endpoint
    sep #$20
    lda #P_NT_FREEMSG
    ldy #6
    sta [4],y
    bra port_native_return

.a16
port_native_endpoint:
    jsr port_reply_endpoint
    jcs port_native_fault
    ; An outer deferred continuation may admit an IRQ after immutable endpoint
    ; validation. No queue link has been observed and NI_ACTIVE still excludes
    ; recursive NMI work. A native IRQ caller keeps its original exclusion.
    lda f:E816_IRQ_DEPTH
    bne :+
    cli
    nop
    sei
:
    sep #$20
    lda #1
    sta f:NI_PORT_BUSY
    rep #$20
    lda #P_NT_REPLYMSG
    sta 22
    jsr port_append_links
    ; Message ownership has transferred. Only retained endpoint metadata is
    ; accessed from this point, even if a later boundary runs the recipient.
    lda 18
    ora 20
    beq port_native_return
    tdc
    clc
    adc #18
    tay
    ldx 16
    jsr signal_post_recipient
port_native_return:
    sep #$20
    lda #0
    sta f:NI_PORT_BUSY
    rep #$30
    tsc
    clc
    adc #PORT_LOCAL
    tcs
    plb
    pld
    ply
    plx
    pla
    plp
    rtl
exec_reply_msg_native_end:

port_native_fault:
    rep #$30
    lda #FAULT_CONTEXT
    jml finish

; Validate the stable endpoint and resolve its already-retained recipient.
; No allocation, membership scan or lease acquisition occurs here.
port_reply_endpoint:
    stz 18
    stz 20
    lda 1
    clc
    adc #P_MSGPORT_BYTES-1
    bcc :+
    lda 3
    and #$ff
    cmp #$ff
    beq port_endpoint_bad
:
    ldy #6
    lda [1],y
    and #$ff
    cmp #P_NT_MSGPORT
    bne port_endpoint_bad
    ldy #P_MSGPORT_MP_FLAGS
    lda [1],y
    and #$ff
    cmp #P_PA_IGNORE
    beq port_endpoint_ok
    cmp #P_PA_SIGNAL
    bne port_endpoint_bad
    ldy #P_MSGPORT_MP_SIGBIT
    lda [1],y
    and #$ff
    cmp #32
    bcs port_endpoint_bad
    asl a
    asl a
    tax
    lda f:port_signal_masks,x
    sta 18
    lda f:port_signal_masks+2,x
    sta 20
port_mask_ready:
    ldy #P_MSGPORT_MP_SIGTASK
    lda [1],y
    sta 13
    iny
    iny
    sep #$20
    lda [1],y
    sta 15
    rep #$20
    and #$ff
    ora 13
    beq port_endpoint_bad
    lda 13
    clc
    adc #T_TASK_SIZE-1
    bcc :+
    lda 15
    and #$ff
    cmp #$ff
    beq port_endpoint_bad
:
    bra port_endpoint_context
port_endpoint_ok:
    clc
    rts

port_endpoint_bad:
    sec
    rts
port_endpoint_context:
    ldy #T_TASK_TC_EXECPRIVATE+2
    lda [13],y
    and #$ff
    cmp #^T_BASE
    bne port_endpoint_bad
    ldy #T_TASK_TC_EXECPRIVATE
    lda [13],y
    sec
    sbc #.loword(T_BASE)
    cmp #T_PUBLIC_CONTEXT_BYTES
    bcs port_endpoint_bad
    tax
    and #T_SIZE-1
    bne port_endpoint_bad
    stx 16
    lda f:T_BASE+T_TCB_STATE,x
    and #$ff
    beq port_endpoint_bad
    lda f:T_BASE+T_TCB_ITEM,x
    cmp 13
    bne port_endpoint_bad
    lda f:T_BASE+T_TCB_ITEM+2,x
    and #$ff
    sep #$20
    cmp 15
    rep #$20
    bne port_endpoint_bad
    clc
    rts

; Fixed cost for every allocated signal, including bit 31. Table capacity
; lives inside the existing upper native-code reservation.
port_signal_masks:
    .repeat 32, bit
        .dword (1 << bit)
    .endrepeat
