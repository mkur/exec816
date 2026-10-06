; Deferred native sources. All mutable state is in the fixed upper Task bank.
; Raw NMI only sets individual pending bytes. A hint is acknowledged before
; calling its owner; a notification during that call survives the return.
.segment "NATIVE_WORK"
.a16
.i16
.export native_work_service, native_work_pending, native_selected_return
.export native_interrupt_return
.export native_return_intercept, native_resume_entry, native_resume_decode
.export native_commit_tail, native_commit_end, native_source_notify

; C=1 when an enabled, unblocked source has retained work. Preserve X/Y/D.
native_work_pending:
    phx
    ldx #NI_SOURCE_COUNT-1
    sep #$20
native_pending_scan:
    lda f:NI_ENABLED,x
    beq native_pending_next
    lda f:NI_BLOCKED,x
    bne native_pending_next
    lda f:NI_PENDING,x
    bne native_pending_found
native_pending_next:
    dex
    bpl native_pending_scan
    rep #$20
    plx
    clc
    rtl
native_pending_found:
    rep #$20
    plx
    sec
    rtl

; A16=immutable source ID, I=1. Enable/disable and descriptor lifetime are
; owner operations. Notify never waits and never changes the running flag.
native_source_notify:
    php
    rep #$30
    pha
    phx
    cmp #NI_SOURCE_COUNT
    jcs port_native_fault
    tax
    sep #$20
    lda f:NI_ENABLED,x
    beq :+
    lda #1
    sta f:NI_PENDING,x
:
    rep #$20
    plx
    pla
    plp
    rtl

; Called only with a full, admitted native frame and no live ROM activation.
; Preserve registers and incoming flags; D/DBR remain private to each callback.
; A callback returns A8=0 done, 1 backlog, 2 blocked by its Task edit gate.
native_work_service:
    sep #$20
    lda #NI_SERVICE_BUDGET
    sta f:NI_BUDGET
    rep #$20
native_work_continue:
    php
    sei
    rep #$30
    pha
    phx
    phy
    phd
    phb
    lda f:NI_ACTIVE
    and #$ffff                    ; ACTIVE and PORT_BUSY are adjacent bytes
    jne native_service_done
    lda f:OS_BUSY
    and #$ff
    jne native_service_done
    lda f:E816_IRQ_DEPTH
    jne native_service_done
    sep #$20
    lda #1
    sta f:NI_ACTIVE
    rep #$20
    ; Retire pending hardware IRQs before starting another masked callback.
    cli
    nop
    sei
native_service_round:
    ldx #0
native_service_scan:
    sep #$20
    lda f:NI_ENABLED,x
    beq native_service_next
    lda f:NI_BLOCKED,x
    bne native_service_next
    lda f:NI_PENDING,x
    beq native_service_next
    lda #0
    sta f:NI_PENDING,x             ; acknowledge before inspecting owner state
    lda #1
    sta f:NI_RUNNING,x
    phx
    cpx #NI_SOURCE_TIMER
    bne :+
    jsl native_timer_work
    bra native_service_result
:
    .if HEAP_PROBE
        jsl native_probe_work
    .endif
native_service_result:
    plx
    cmp #2
    bne :+
    lda #1
    sta f:NI_BLOCKED,x
:
    cmp #0
    beq :+
    lda #1
    sta f:NI_PENDING,x
:
    lda #0
    sta f:NI_RUNNING,x
    ; NI_ACTIVE remains asserted across the IRQ opportunity and prevents
    ; recursive continuation service or policy entry in the interrupted frame.
    cli
    nop
    sei
    lda f:NI_BUDGET
    dec a
    sta f:NI_BUDGET
    beq native_service_retire
native_service_next:
    inx
    cpx #NI_SOURCE_COUNT
    bcc native_service_scan
    rep #$20
    jsl native_work_pending
    bcs native_service_round
native_service_retire:
    sep #$20
    lda #0
    sta f:NI_ACTIVE
native_service_done:
    rep #$30
    plb
    pld
    ply
    plx
    pla
    plp
    rtl

.if HEAP_PROBE
.export native_probe_work
.a8
native_probe_work:
    lda #0
    rtl
    nop                           ; four-byte diagnostic overlay entry
.endif

; Reached with S=selected complete Task frame, I=1, D=kernel DP, DBR=0.
; No compiled activation remains live. The saved Task I bit still controls
; admission, even though the adapter itself is restoring with I=1.
.a16
native_selected_return:
    sep #$20
    lda #NI_SERVICE_BUDGET
    sta f:NI_BUDGET
    rep #$20
native_commit_tail:
    ; This range never changes S. All native calls leave the range and return
    ; to its first check, including notifications in a service epilogue.
    tsc
    tax
    lda f:T_FRAME_P,x
    and #4
    jne native_commit_ready
    lda f:NI_ENABLED
    and #($ff | ($ff00 * HEAP_PROBE))
    beq native_commit_wakes
    .repeat NI_SOURCE_COUNT, source
        lda f:NI_ENABLED+source
        and #$ff
        beq :+
        lda f:NI_BLOCKED+source
        and #$ff
        bne :+
        lda f:NI_PENDING+source
        and #$ff
        bne native_commit_work
:
    .endrepeat
native_commit_wakes:
    lda f:T_WAKE_PENDING
    and #$ff
    bne native_commit_poll
    lda f:E816_TICK_PENDING
    and #$ff
    bne native_commit_tick
    bra native_commit_ready
native_commit_work:
    lda f:NI_BUDGET
    and #$ff
    bne native_commit_service
    ; Backlog with a runnable Task is retained for the next interrupt. Idle
    ; must create another bounded opportunity instead of sleeping over work.
    lda f:E816_CURRENT
    and #$ff
    cmp #T_IDLE
    bne native_commit_wakes
native_commit_poll:
    tsc
    tax
    ldy #E816_SERVICE_POLL
    jml dispatch_frame
native_commit_tick:
    jml native_return_tick
native_commit_service:
    jml native_return_service
native_commit_ready:
    native_work_checkpoint 34
    stz E816_SWITCHING
    native_work_checkpoint 35
    jml context_restore
native_commit_end:

native_return_service:
    jsl native_work_continue
    jml native_commit_tail
native_return_tick:
    jsl signal_tick_needed
    bcs native_commit_poll
    sep #$20
    stz E816_TICK_PENDING
    rep #$20
    jml native_commit_tail

; A validated outer IRQ/NMI frame may use the same return protocol. Claim
; scheduler exclusion before any native callback opens its IRQ opportunity.
native_interrupt_return:
    lda #E816_KERNEL_DP
    tcd
    sep #$20
    lda #1
    sta E816_SWITCHING
    rep #$20
    jml native_selected_return

; Private return destination. COP saves the completely restored Task context.
; Decode restores the original PC/PBR and dispatches internal Poll. There is
; no public selector, new COP signature, or application callback here.
native_resume_entry:
    cop E816_COP
    jml port_native_fault

; X=validated COP frame. C=1 and Y=POLL when it is our armed trampoline.
; Normal COPs preserve X and continue decoding their ordinary saved A.
native_resume_decode:
    lda f:T_FRAME_PC,x
    cmp #.loword(native_resume_entry+2)
    bne native_decode_other
    lda f:T_FRAME_PBR,x
    and #$ff
    cmp #^native_resume_entry
    bne native_decode_other
    php
    sei
    phx
    txy
    lda f:E816_CURRENT
    and #$ff
    asl a
    asl a
    tax
    lda f:NI_RESUME+3,x
    and #$ff
    jeq port_native_fault
    lda f:NI_RESUME,x
    sta a:T_FRAME_PC,y
    sep #$20
    lda f:NI_RESUME+2,x
    sta a:T_FRAME_PBR,y
    lda #0
    sta f:NI_RESUME+3,x
    rep #$20
    plx
    plp
    ldy #E816_SERVICE_POLL
    sec
    rtl
native_decode_other:
    clc
    rtl

; Enter immediately after retiring an NMI/IRQ ROM activation. The full nested
; frame remains below this JSL. Only adapter-owned restore instructions are
; recognized; arbitrary masked Task, kernel and foreign frames remain deferred.
; C=1 while a prior redirect must finish its private COP handoff. Interrupts
; may publish work, but cannot switch away with that Task's saved PC still live.
native_return_intercept:
    lda f:E816_CURRENT
    and #$ff
    cmp #T_IDLE+1
    jcs native_intercept_done
    asl a
    asl a
    tax
    lda f:NI_RESUME+3,x
    and #$ff
    beq :+
    sec
    rtl
:
    ; Most interrupts return to ordinary upper-bank code. Reject those PCs
    ; before scanning work or building the interceptor's local frame. The
    ; caller still performs ordinary interrupt service/admission afterwards.
    lda T_FRAME_PBR+3,s
    and #$ff
    beq native_intercept_candidate
    cmp #^native_commit_tail
    jne native_intercept_done
    lda T_FRAME_PC+3,s
    cmp #.loword(native_commit_tail)
    jcc native_intercept_done
    cmp #.loword(native_commit_end)
    jcs native_intercept_done
native_intercept_candidate:
    lda f:NI_ACTIVE
    and #$ffff
    jne native_intercept_done
    lda f:E816_IRQ_DEPTH
    jne native_intercept_done
    lda f:OS_BUSY
    and #$ff
    jne native_intercept_done
    jsl native_work_pending
    bcs :+
    lda f:T_WAKE_PENDING
    and #$ff
    jeq native_intercept_done
:
    phd
    tsc
    sec
    sbc #12
    tcs
    tcd
    clc
    adc #12+2+3
    sta 1                         ; nested complete frame
    tax
    stz 9                         ; bytes popped from the outer frame
    lda f:T_FRAME_PBR,x
    and #$ff
    jeq native_intercept_near
    cmp #^native_commit_tail
    jne native_intercept_leave
    lda f:T_FRAME_PC,x
    cmp #.loword(native_commit_tail)
    jcc native_intercept_leave
    cmp #.loword(native_commit_end)
    jcs native_intercept_leave
    brl native_intercept_frame
native_intercept_near:
    lda f:T_FRAME_PC,x
    cmp #interrupt_quiet_tail
    bcc :+
    cmp #interrupt_quiet_end
    jcc native_intercept_frame
:
    cmp #interrupt_restore
    bcc native_intercept_cop
    cmp #interrupt_restore_end
    bcs native_intercept_cop
    cmp #interrupt_restore+3
    bcc native_intercept_frame
    inc 9
    cmp #interrupt_restore+4
    bcc native_intercept_frame
    inc 9
    inc 9
    cmp #interrupt_restore+5
    bcc native_intercept_frame
    inc 9
    inc 9
    cmp #interrupt_restore+6
    bcc native_intercept_frame
    inc 9
    inc 9
    cmp #interrupt_restore+7
    bcc native_intercept_frame
    inc 9
    inc 9
    bra native_intercept_frame
native_intercept_cop:
    cmp #restore_commit
    jcc native_intercept_leave
    cmp #restore_end
    jcs native_intercept_leave
    cmp #restore_after_plb
    bcc native_intercept_frame
    inc 9
    cmp #restore_after_pld
    bcc native_intercept_frame
    inc 9
    inc 9
    cmp #restore_after_ply
    bcc native_intercept_frame
    inc 9
    inc 9
    cmp #restore_after_plx
    bcc native_intercept_frame
    inc 9
    inc 9
    cmp #restore_after_pla
    bcc native_intercept_frame
    inc 9
    inc 9
native_intercept_frame:
    lda 1
    clc
    adc #A816_SAVED_FRAME_SIZE
    sec
    sbc 9
    sta 3                         ; outer full frame (part may be popped)
    tay
    lda f:E816_CURRENT
    and #$ff
    cmp #T_IDLE+1
    jcs native_intercept_leave
    asl a
    asl a
    sta 7                         ; per-Task trampoline slot
    .repeat T_SHIFT-2
        asl a
    .endrepeat
    tax
    lda 3
    clc
    adc #A816_SAVED_FRAME_SIZE
    cmp f:T_BASE+T_TCB_STACKFLOOR,x
    jcc native_intercept_leave
    cmp f:T_BASE+T_TCB_STACKTOP,x
    bcc :+
    jne native_intercept_leave
:
    lda a:T_FRAME_P,y
    and #4
    jne native_intercept_leave
    lda 9
    cmp #3
    bcc :+
    ldy 1                         ; PLD already restored the Task D
:
    lda a:T_FRAME_D,y
    cmp f:T_BASE+T_TCB_DP,x
    jne native_intercept_leave
    ldx 7
    lda f:NI_RESUME+3,x
    and #$ff
    bne native_intercept_leave     ; existing redirect retains original PC
    sep #$20
    lda #1
    sta f:NI_ACTIVE                ; nested NMI cannot see a partial redirect
    rep #$20
    ldy 3
    lda a:T_FRAME_PC,y
    sta f:NI_RESUME,x
    lda #.loword(native_resume_entry)
    sta a:T_FRAME_PC,y
    sep #$20
    lda a:T_FRAME_PBR,y
    sta f:NI_RESUME+2,x
    lda #^native_resume_entry
    sta a:T_FRAME_PBR,y
    lda #1
    sta f:NI_RESUME+3,x
    lda #0
    sta f:NI_ACTIVE
    rep #$20
native_intercept_leave:
    tsc
    clc
    adc #12
    tcs
    pld
native_intercept_done:
    clc
    rtl
