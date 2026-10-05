; Included by hosted.s. Hardware entry/restore keeps I=1; the Task policy runs
; with IRQs enabled once its kernel domain and transition guard are stable.
; NMI may arrive between any two instructions, including TCS/TCD. Its OS frame
; is activation-local; only eligible task returns can borrow the kernel domain.
.export native_cop, task_start, context_restore, dispatch_call
.export exec_version, exec_version_end, exec_task_id, exec_task_id_end
.export exec_yield, exec_yield_end, exec_poll, exec_poll_end
.export exec_lock, exec_lock_end, exec_unlock, exec_unlock_end
.export exec_exit, exec_exit_end

.segment "GATE"
.a16
.i16
native_cop:
    rep #$30
    pha
    checkpoint 13
    phx
    phy
    phd
    phb
    cld
    tsc
    tax
    .if GENERAL_TASKS
        ; IRQ/OS code can enter COP while the interruptible policy owns its
        ; direct page. Decode the signature in activation-local stack storage
        ; before deciding whether this entry may borrow the kernel domain.
        sec
        sbc #4
        tcs
        tcd
    .else
        ; The small two-task probe retains its original protected lookup.
        lda #E816_KERNEL_DP
        tcd
    .endif
    phk
    plb
    checkpoint 14
    lda f:A816_SAVED_FRAME_PC_OFFSET,x
    dec a
    .if GENERAL_TASKS
        sta 1
        sep #$20
        lda f:A816_SAVED_FRAME_PBR_OFFSET,x
        sta 3
        lda [1]
        rep #$20
        and #$00ff
        tay
        txa
        tcs
        lda #E816_KERNEL_DP
        tcd
        tya
    .else
    sta A816_DP_POINTER0_OFFSET
    sep #$20
    lda f:A816_SAVED_FRAME_PBR_OFFSET,x
    sta A816_DP_POINTER0_OFFSET+2
    lda [A816_DP_POINTER0_OFFSET]
    .endif
    cmp #E816_COP
    beq exec_entry
    rep #$20
    .if GENERAL_TASKS
        lda f:SD_OWNED
        .if CONSOLE_NATIVE
            ora f:CS_BASE+CON_SERVICE_STATE
        .endif
        .if INPUT_NATIVE
            ora f:CI_ACTIVE
        .endif
        and #$ff
        beq :+
        ; No ROM activation may take the owned serial/alarm channels. The
        ; caller's original complete frame, including DP and P, remains intact.
        lda #ERROR_BUSY
        sta f:A816_SAVED_FRAME_A_FULL_OFFSET,x
        restore_full
        rti
:
    .endif
    inc E816_FORWARD_COUNT
    restore_full
    ; P remains in the hardware frame. The pinned ROM dispatcher establishes
    ; M=X=0 before using A/X/Y and restores the original P through RTI.
    jmp [E816_OLD_COP]
exec_entry:
    rep #$20
    ; Reject interrupt/OS/kernel activations before borrowing the kernel stack.
    lda E816_SWITCHING
    and #$00ff
    .if GENERAL_TASKS
        beq :+
        jmp rejected
:
    .else
    bne rejected
    .endif
    .if GENERAL_TASKS
        ; A complete local frame is enough to permit IRQs: validation reads
        ; immutable pool bounds and saves its scratch on this same stack.
        ; Claim scheduler exclusion first, including for a foreign frame that
        ; validation will reject. Nested IRQ/NMI cannot borrow policy state.
        sep #$20
        lda #1
        sta E816_SWITCHING
        rep #$20
        lda f:A816_SAVED_FRAME_P_OFFSET,x
        and #$0004
        bne :+
        cli
:
    .endif
    jsr validate_frame
    .if GENERAL_TASKS
        bcc :+
        sei
        stz E816_SWITCHING
        jmp rejected
:
    .else
    bcs rejected
    .endif
    inc E816_GATE_COUNT
    .if GENERAL_TASKS
        jsl native_resume_decode
        bcc :+
        jmp dispatch_frame
:
    .endif
    lda f:A816_SAVED_FRAME_A_FULL_OFFSET,x
    and #$00ff
    tay
    .if GENERAL_TASKS
        jml fast_entry
    .endif
dispatch_frame:
    sep #$20
    lda #1
    sta E816_SWITCHING
    rep #$20
    .if GENERAL_TASKS
        ; The full frame is validated and SWITCHING excludes policy reentry.
        ; IRQ/NMI save and restore the current S/D even during the following
        ; kernel-domain transition; neither borrows compiler scratch. Open
        ; IRQs here, before tick bookkeeping and installing the kernel stack.
        lda f:A816_SAVED_FRAME_P_OFFSET,x
        and #$0004
        bne dispatch_masked
        sep #$20
        lda #1
        sta f:T_IRQ_ALLOW
        rep #$20
        cli
        bra dispatch_guarded
dispatch_masked:
        sep #$20
        lda #0
        sta f:T_IRQ_ALLOW
        rep #$20
dispatch_guarded:
    .endif
    checkpoint 9
    .if PREEMPTIVE
        ; A single TRB consumes the tick atomically against NMI. The VBI hook
        ; only sets this byte, so a later tick remains pending for another pass.
        phx
        sep #$20
        lda #1
        trb E816_TICK_PENDING
        checkpoint 15
        beq :+
        lda E816_CURRENT
        rep #$20
        and #$00ff
        .if GENERAL_TASKS
            .repeat T_SHIFT
                asl a
            .endrepeat
        .else
            .repeat 4
                asl a
            .endrepeat
        .endif
        tax
        sep #$20
        lda #1
        .if GENERAL_TASKS
            sta f:T_BASE+T_TCB_PENDING,x
            sta f:T_TIMER_PENDING
        .else
            sta E816_TASK0+E816_TCB_PENDING,x
        .endif
:
        rep #$20
        plx
    .endif
    lda #E816_KERNEL_STACK_TOP
    tcs
    checkpoint 10
    ; Dispatch(CARD saved_s, BYTE service): three outgoing bytes, no padding.
    sep #$20
    tya
    pha
    rep #$20
    phx
dispatch_call:
    jsl DISPATCH_ENTRY
    .if GENERAL_TASKS
        sei
    .endif
    ; Outgoing arguments need not be popped: this stack is now inactive.
    .if GENERAL_TASKS
        cmp #T_FAULT
        beq context_fault
    .endif
    cmp #0
    beq all_exited
    tax
    jsr validate_frame
    bcs context_fault
    .if GENERAL_TASKS .and SIGNAL_AUTO
        ; An IRQ may post after policy selection but before its final RTL.
        ; With I=1, either reenter Poll on the selected frame or commit its
        ; restore. Each consumed target leaves WAIT, so posts cannot keep
        ; refilling a drain without another task activation.
        lda f:T_WAKE_PENDING
        and #$00ff
        beq :+
        ldy #E816_SERVICE_POLL
        jmp dispatch_frame
:
    .endif
restore_selected:
    checkpoint 11
    txa
    tcs
restore_commit:
    native_work_checkpoint 36
    checkpoint 12
    ; I is still set. Publish completion only after selecting the task stack.
    .if GENERAL_TASKS
        jml native_selected_return
    .else
        stz E816_SWITCHING
    .endif
context_restore:
    native_work_checkpoint 37
    checkpoint 16
    rep #$30
    plb
restore_after_plb:
    native_work_checkpoint 30
    pld
restore_after_pld:
    native_work_checkpoint 38
    checkpoint 17
    ply
restore_after_ply:
    native_work_checkpoint 31
    plx
restore_after_plx:
    native_work_checkpoint 32
    pla
restore_after_pla:
    native_work_checkpoint 33
    rti
restore_end:
.export restore_commit, restore_after_plb, restore_after_pld
.export restore_after_ply, restore_after_plx, restore_after_pla, restore_end
all_exited:
    stz E816_SWITCHING
    lda #0
    jmp finish
rejected:
    .if GENERAL_TASKS
        lda f:A816_SAVED_FRAME_A_FULL_OFFSET,x
        and #$00ff
        cmp #T_SERVICE_CREATE_TASK
        beq context_fault
        cmp #T_SERVICE_ADD_TASK
        bcc :+
        cmp #T_SERVICE_WAIT+1
        bcc context_fault
:
    .endif
    lda #E816_ERROR_CONTEXT
    sta f:A816_SAVED_FRAME_A_FULL_OFFSET,x
    bra context_restore
context_fault:
    lda #FAULT_CONTEXT
    jmp finish

; X points to a full frame. Permit the interrupt reserve below stack_floor;
; reject a foreign stack or D. Caller is on a task or kernel stack, DBR=0.
validate_frame:
    .if GENERAL_TASKS
        ; Keep the interrupted X and caller Y. Use the immutable pool bounds
        ; in the current TCB, never an untrusted frame's D as an address base.
        phy
        phx
        lda E816_CURRENT
        and #$00ff
        cmp #T_IDLE+1
        bcs invalid_general
        .repeat T_SHIFT
            asl a
        .endrepeat
        tay
        txa
        tyx
        tay                         ; X=context offset, Y=bank-zero frame
        clc
        adc #A816_SAVED_FRAME_SIZE
        cmp f:T_BASE+T_TCB_STACKFLOOR,x
        bcc invalid_general
        cmp f:T_BASE+T_TCB_STACKTOP,x
        bcc :+
        bne invalid_general
:
        lda a:A816_SAVED_FRAME_D_OFFSET,y
        cmp f:T_BASE+T_TCB_DP,x
        bne invalid_general
        plx
        ply
        clc
        rts
invalid_general:
        plx
        ply
        sec
        rts
    .else
    lda E816_CURRENT
    and #$00ff
    cmp #2
    bcs invalid_frame
    cmp #1
    beq second_frame
    cpx #STACK_FLOOR-A816_SAVED_FRAME_SIZE
    bcc invalid_frame
    cpx #STACK_TOP-A816_SAVED_FRAME_SIZE+1
    bcs invalid_frame
    lda f:A816_SAVED_FRAME_D_OFFSET,x
    cmp #TASK_DP
    bra checked_frame
second_frame:
    cpx #E816_TASK1_STACK_FLOOR-A816_SAVED_FRAME_SIZE
    bcc invalid_frame
    cpx #E816_TASK1_STACK_TOP-A816_SAVED_FRAME_SIZE+1
    bcs invalid_frame
    lda f:A816_SAVED_FRAME_D_OFFSET,x
    cmp #E816_TASK1_DP
checked_frame:
    bne invalid_frame
    clc
    rts
    .endif
invalid_frame:
    sec
    rts

.segment "STUBS"
.a16
.i16
.macro service_stub label, end_label, selector
label:
    .if GENERAL_TASKS
        .if selector >= T_SERVICE_ADD_TASK
        ldy #T_PROFILE_TAG
        .endif
    .endif
    lda #selector
    cop E816_COP
    rtl
end_label:
.endmacro
service_stub exec_version, exec_version_end, E816_SERVICE_VERSION
service_stub exec_task_id, exec_task_id_end, E816_SERVICE_TASK_ID
service_stub exec_yield, exec_yield_end, E816_SERVICE_YIELD
service_stub exec_poll, exec_poll_end, E816_SERVICE_POLL
service_stub exec_lock, exec_lock_end, E816_SERVICE_LOCK
service_stub exec_unlock, exec_unlock_end, E816_SERVICE_UNLOCK
exec_exit:
    lda 4,s
    tax
    lda #E816_SERVICE_EXIT
    cop E816_COP
    ; ExitTask cannot return. A protected exit is a defined launch fault.
    lda #FAULT_CONTEXT
    jmp finish
exec_exit_end:
task_start:
    .if CONSOLE_STARTUP
        ; Only the root enters here. Native Task children use general_task_start.
        ; Supply the ordinary one-byte zero-argument call padding.
        sep #$20
        lda #0
        pha
        rep #$20
        jsl CONSOLE_START
        and #$00ff
        tax
        tsc
        inc a
        tcs
        txa
        bne :+
        lda #CON_STARTUP_FAULT
        jmp finish
:
    .endif
    .if PROBE_FLAGS <> $100
        jsr raw_context_probe
    .endif
    jml PROGRAM_ENTRY
cooperative_return:
    .if GENERAL_TASKS
        ; The compiler domain binds stack limits to the slot. Compare against
        ; the current record as well, so a foreign D cannot satisfy the check.
        lda f:E816_CURRENT
        and #$00ff
        cmp #T_CAPACITY
        bcs bad_return
        .repeat T_SHIFT
            asl a
        .endrepeat
        tax
        lda f:RETURN_S
        cmp f:T_BASE+T_TCB_INITIALS,x
        bne bad_return
        tdc
        cmp f:T_BASE+T_TCB_DP,x
        bra check_return
    .else
    sep #$20
    lda f:E816_CURRENT
    rep #$20
    and #$00ff
    bne second_return
    lda f:RETURN_S
    cmp #STACK_TOP
    bne bad_return
    tdc
    cmp #TASK_DP
    bra check_return
second_return:
    lda f:RETURN_S
    cmp #E816_TASK1_STACK_TOP
    bne bad_return
    tdc
    cmp #E816_TASK1_DP
    .endif
check_return:
    bne bad_return
    sta f:RETURN_D
    ; Reapply the caller's I flag captured by native_return.
    lda f:RETURN_P
    and #$0004
    bne bad_return
    .if GENERAL_TASKS
        lda f:T_BASE+T_TCB_FINALPC,x
        bne custom_finalizer
        sep #$20
        lda f:T_BASE+T_TCB_FINALPC+2,x
        rep #$20
        and #$00ff
        bne custom_finalizer
        ldx #0
        ldy #T_PROFILE_TAG
        lda #T_SERVICE_REM_TASK
        cli
        cop E816_COP
        bra bad_return
custom_finalizer:
        ; Native zero-argument caller area. A returning finalizer faults below.
        tsc
        dec a
        tcs
        sep #$20
        lda #0
        sta 1,s
        rep #$20
        cli
        jsl general_finalizer_start
    .else
    ldx #0
    lda #E816_SERVICE_EXIT
    cli                          ; return diagnostics and checks are complete
    cop E816_COP
    .endif
bad_return:
    lda #FAULT_RETURN
    jmp finish

.segment "COOP_BOOT"
.a16
.i16
cooperative_init:
    .if PREEMPTIVE
        lda VVBLKI
        sta E816_OLD_VBI
        lda #vbi_tick
        sta VVBLKI
    .endif
    lda VCOPN
    sta E816_OLD_COP
    sep #$20
    lda VCOPN+2
    sta E816_OLD_COP+2
    stz VCOPN+2
    lda #$ff
    sta E816_OS_OWNER
    rep #$20
    lda #native_cop
    sta VCOPN
    .if GENERAL_TASKS
        jmp general_domains
    .else
    lda #$a5a5
    ldx #$061e
guard_private_stacks:
    sta E816_TASK1_STACK_BASE-$10,x
    sta E816_KERNEL_STACK_BASE-$10,x
    dex
    dex
    bpl guard_private_stacks
    lda #0
    ldx #$00fe
zero_domains:
    sta E816_TASK1_DP,x
    sta E816_KERNEL_DP,x
    dex
    dex
    bpl zero_domains
    lda #E816_TASK0
    sta TASK_DP+A816_DP_OWNER_POINTER_OFFSET
    lda #E816_TASK1
    sta E816_TASK1_DP+A816_DP_OWNER_POINTER_OFFSET
    lda #E816_KERNEL_OWNER
    sta E816_KERNEL_DP+A816_DP_OWNER_POINTER_OFFSET
    lda #E816_TASK1_STACK_FLOOR
    sta E816_TASK1_DP+A816_DP_STACK_FLOOR_OFFSET
    lda #E816_TASK1_STACK_CEILING
    sta E816_TASK1_DP+A816_DP_STACK_CEILING_OFFSET
    lda #E816_KERNEL_STACK_FLOOR
    sta E816_KERNEL_DP+A816_DP_STACK_FLOOR_OFFSET
    lda #E816_KERNEL_STACK_CEILING
    sta E816_KERNEL_DP+A816_DP_STACK_CEILING_OFFSET
    sep #$20
    lda #A816_DOMAIN_IRQ
    sta E816_KERNEL_DP+A816_DP_DOMAIN_KIND_OFFSET
    lda #E816_STATE_READY
    sta E816_TASK0+E816_TCB_STATE
    sta E816_TASK1+E816_TCB_STATE
    lda #1
    sta E816_TASK1+E816_TCB_ID
    rep #$20
    ; First task uses a real JSL; task one gets the identical zero-argument
    ; call image plus a full native interrupt frame. All bytes initialized.
    FIRST_S = E816_TASK1_STACK_TOP-4-A816_SAVED_FRAME_SIZE
    lda #0
    ldx #16
clear_first_frame:
    sta FIRST_S,x
    dex
    dex
    bpl clear_first_frame
    lda #FIRST_S
    sta E816_TASK1+E816_TCB_SAVEDS
    lda #E816_TASK1_DP
    sta FIRST_S+A816_SAVED_FRAME_D_OFFSET
    lda #task_start
    sta FIRST_S+A816_SAVED_FRAME_PC_OFFSET
    lda #native_return-1
    sta FIRST_S+A816_SAVED_FRAME_SIZE+1
    rts
    .endif
.if GENERAL_TASKS
    .include "tasks.s"
.endif

.if PROBE_FLAGS <> $100
    .include "cooperative-probe.s"
.endif

.if PROBE_NMI = 18
    .segment "BOOT"
    .a8
    .i8
os_vbi_probe:
    ; COP #0 calls this in E=1 on the live shared OS stack. A real VBI must
    ; record a tick without switching. Continue through the actual CIO service.
    wai
    jmp CIOV
.endif
