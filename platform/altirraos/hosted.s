; Native Action! hosted by the pinned AltirraOS 65816 ROM.
; COOPERATIVE enables two tasks. DLI and third-party handlers are excluded.
.setcpu "65816"
.smart
.macpack longbranch
.include "action65816-native-v2.inc"
.include "exec-abi.inc"
.include "layout.inc"
.if GENERAL_TASKS
    .include "tasks.inc"
.endif
.if BANKED
    .include "memory.inc"
.endif
.export start, done, console_write, console_write_end, stack_overflow
.export stack_overflow_end, arithmetic_fault, arithmetic_fault_end
.export native_nmi, native_irq, native_return, state_rejected
.export heap_fault, heap_fault_end, startup_complete

.macro save_full
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
.endmacro

; Test builds wait for a real hardware interrupt at one selected transition.
; WAI changes no caller register or flags; production PROBE_NMI=0 emits nothing.
.macro checkpoint number
    .if PROBE_NMI = number
        wai
    .endif
.endmacro

.segment "BOOT"
.a8
.i8
start:
    sei
    cld
    stz NMIEN
    clc
    xce
    rep #$30
    lda #OS_STACK_TOP
    tcs
    lda #0
    tcd
    phk
    plb
    .if BANKED
        lda M_OLD_MEMLO
    .else
        lda MEMLO
    .endif
    cmp #STATE+1
    bcs memory_fault
    lda MEMTOP
    cmp #APP_LIMIT
    bcc memory_fault
    bra memory_ok
memory_fault:
    ; The state page is unclaimed. Report through this exported rejection
    ; entry, without writing state or installing vectors.
    jmp state_rejected
memory_ok:
    lda #0
    ldx #E816_STATE_BYTES-2
clear_state:
    sta STATE,x
    dex
    dex
    bpl clear_state
    lda #$ffff
    sta STATUS
    .if BANKED
        lda M_OLD_MEMLO
    .else
        lda MEMLO
    .endif
    sta OLD_MEMLO
    lda #APP_LIMIT
    sta MEMLO
    lda VNMIN
    sta OLD_NMI
    lda VIRQN
    sta OLD_IRQ
    sep #$20
    lda VNMIN+2
    sta OLD_NMI+2
    lda VIRQN+2
    sta OLD_IRQ+2
    lda $14
    sta START_CLOCK
    rep #$20
    lda #native_nmi
    sta VNMIN
    lda #native_irq
    sta VIRQN
    sep #$20
    stz VNMIN+2
    stz VIRQN+2
    rep #$20
    lda #$a5a5
    ldx #$011e
guard_dp:
    sta TASK_DP-$10,x
    dex
    dex
    bpl guard_dp
    ldx #$061e
guard_stack:
    sta STACK_BASE-$10,x
    dex
    dex
    bpl guard_stack
    ldx #$000e
guard_os_stack:
    sta $0100,x
    dex
    dex
    bpl guard_os_stack
    lda #0
    ldx #$00fe
clear_dp:
    sta TASK_DP,x
    dex
    dex
    bpl clear_dp
    lda #STATE
    sta TASK_DP+A816_DP_OWNER_POINTER_OFFSET
    lda #STACK_FLOOR
    sta TASK_DP+A816_DP_STACK_FLOOR_OFFSET
    lda #STACK_CEILING
    sta TASK_DP+A816_DP_STACK_CEILING_OFFSET
    ; owner bank and kind=task are already zero.
    .if COOPERATIVE
        jsr cooperative_init
    .endif
    .if BANKED
        ; OS vectors are installed, but no owned task is active yet. Boot
        ; policy runs with I=1 on the kernel domain; NMI cannot dispatch it.
        lda #E816_KERNEL_DP
        tcd
        lda #E816_KERNEL_STACK_TOP-1
        tcs
        sep #$20
        lda #0
        sta 1,s
        rep #$20
        jsl MEMORY_INIT
        cmp #0
        beq :+
        lda #FAULT_CONTEXT
        jmp finish
:
    .endif
    .if GENERAL_TASKS
        ; Adoption is complete: the INITAD loader/staging may now be reclaimed.
        jsl TASK_INIT
        cmp #0
        beq :+
        lda #FAULT_CONTEXT
        jmp finish
:
    .endif
    .if BANKED
        ; Every startup consumer has returned. No bootstrap callback remains;
        ; normal bank operations use the adopted table, not the manifest.
        sep #$20
        lda #1
        sta f:M_RETIRED
        rep #$20
    .endif
startup_complete:
    lda #TASK_DP
    tcd
    lda #STACK_TOP
    tcs
    sep #$20
    lda #$40
    sta f:NMIEN
    rep #$20
    .if INITIAL_I = 0
        cli
    .endif
    ; Ordinary v1 zero-argument call: one zero padding byte, then JSL.
    tsc
    dec a
    tcs
    sep #$20
    lda #0
    sta 1,s
    rep #$20
    .if COOPERATIVE
        jsl task_start
    .else
        jsl PROGRAM_ENTRY
    .endif
native_return:
    php
    sei                          ; protect shared return diagnostics from switching
    sep #$20
    phb
    pla
    sta f:RETURN_DBR
    pla
    sta f:RETURN_P
    clc
    xce
    lda #0
    rol a
    sta f:RETURN_E
    rep #$30
    tsc
    inc a
    tcs
    sta f:RETURN_S
    .if COOPERATIVE
        jmp cooperative_return
    .endif
    cmp #STACK_TOP
    bne return_fault
    tdc
    sta f:RETURN_D
    cmp #TASK_DP
    bne return_fault
    lda #0
    jmp finish
return_fault:
    lda #FAULT_RETURN
    jmp finish

; Entry saves all registers before inspecting S. If already on page one, keep
; the current S: resetting it would overwrite a live OS/COP/interrupt frame.
; saved_s lives on the OS stack, never in a shared global or task DP scratch.
.macro os_interrupt vector, counter, scheduling
    .local already_os, os_return
    save_full
    cld
    tsc
    tax
    and #$ff00
    cmp #$0100
    beq already_os
    lda #OS_STACK_TOP
    tcs
already_os:
    phx                          ; interrupted saved_s, private to this activation
    lda #0
    tcd
    phk
    plb
    .if PREEMPTIVE .and (scheduling = 0)
        inc E816_IRQ_DEPTH
    .endif
    inc counter
    phk                          ; synthetic native interrupt frame
    pea os_return
    sep #$20
    lda f:A816_SAVED_FRAME_P_OFFSET,x
    and #$04                     ; OS VBI sees the original I bit
    pha
    rep #$30
    jmp [vector]
os_return:
    sei                          ; ROM RTI may have restored I=0
    rep #$30
    .if PREEMPTIVE .and (scheduling = 0)
        dec E816_IRQ_DEPTH
    .endif
    pla                          ; saved_s; no live OS frame remains below it
    tcs
    .if PREEMPTIVE
        jmp interrupt_schedule
    .endif
    restore_full
    rti
.endmacro

.segment "NMI"
.a16
.i16
native_nmi:
    os_interrupt OLD_NMI, NMI_COUNT, 1

.if PREEMPTIVE
    .include "preemptive.s"
.endif

.segment "IRQ"
.a16
.i16
native_irq:
    .if GENERAL_TASKS
        save_full
        cld
        lda #0
        tcd
        phk
        plb
        inc E816_IRQ_DEPTH
        sep #$20
        .export signal_route_begin, signal_route_return
signal_route_begin:
        jsl signal_route
signal_route_return:
        rep #$30
        dec E816_IRQ_DEPTH
        bcc :+
        inc IRQ_COUNT
        jmp interrupt_schedule
:
        restore_full
    .endif
    os_interrupt OLD_IRQ, IRQ_COUNT, 0

.segment "CONSOLE"
.a16
.i16
console_write:
    ; Ordinary v1 entry. Check before pushing any adapter bytes; preserve I.
    .if STACK_CHECKS
    tsc
    tax
    cmp A816_DP_STACK_CEILING_OFFSET
    bcc check_floor
    beq check_floor
    bra overflow
check_floor:
    sec
    sbc #WRITE_STACK_BYTES
    bcc overflow
    cmp A816_DP_STACK_FLOOR_OFFSET
    bcs stack_ok
overflow:
    lda #WRITE_STACK_BYTES
    jml stack_overflow
stack_ok:
    .endif
    php
    save_full
    checkpoint 1
    ; Argument offsets are checked against --emit-interfaces by the builder.
    lda 18,s                     ; CARD length: entry+8, plus ten saved bytes
    bne :+
    jmp empty_write
:
    cmp #256
    bcc :+
    jmp invalid_pointer
:
    .if BANKED
        sep #$20
        lda 16,s
        cmp #^M_IMAGE_DATA_BASE
        beq :+
        jmp invalid_pointer_8
:
        rep #$20
        lda 14,s
        cmp #.loword(M_IMAGE_DATA_BASE)
        bcs :+
        jmp invalid_pointer
:
        clc
        adc 18,s
        .if .loword(M_IMAGE_DATA_END) = 0
        ; An exclusive end at the next bank permits an exact wrap to zero.
        bcc :+
        cmp #0
        beq :+
        jmp invalid_pointer
:
        .else
        bcc :+
        jmp invalid_pointer
:
        cmp #.loword(M_IMAGE_DATA_END)+1
        bcc :+
        jmp invalid_pointer
:
        .endif
    .else
    sep #$20
    lda 16,s                     ; pointer bank: entry+6
    beq :+
    jmp invalid_pointer_8
:
    rep #$20
    lda 14,s                     ; pointer low word: entry+4
    cmp #APP_BASE
    bcs :+
    jmp invalid_pointer
:
    clc
    adc 18,s
    bcs invalid_pointer
    cmp #APP_LIMIT+1
    bcs invalid_pointer
    .endif
    sep #$20
    .if GENERAL_TASKS
        lda f:SD_OWNED
        .if CONSOLE_NATIVE
            ora f:CS_BASE+CON_SERVICE_STATE
            ora f:CI_ACTIVE
        .endif
        jne busy
    .endif
    lda f:OS_BUSY
    jne busy
    lda #1
    sta f:OS_BUSY
    .if COOPERATIVE
        lda f:E816_CURRENT
        sta f:E816_OS_OWNER
    .endif
    rep #$20
    .if COOPERATIVE
        inc E816_OS_CALLS
    .endif
    .if BANKED
        ; A ROM IOCB accepts a bank-zero pointer. Stage upper image data on
        ; this activation's checked Task stack while OS_BUSY blocks switching.
        lda 14,s
        sta A816_DP_SCRATCH_OFFSET
        lda 18,s
        sta A816_DP_SCRATCH_OFFSET+3
        sta f:$0348
        sep #$20
        lda 16,s
        sta A816_DP_SCRATCH_OFFSET+2
        rep #$20
        tsc
        sec
        sbc #256
        tcs
        inc a
        sta f:$0344
        tax
        ldy #0
copy_rom_buffer:
        sep #$20
        lda [A816_DP_SCRATCH_OFFSET],y
        sta f:$000000,x
        inx
        iny
        rep #$20
        tya
        cmp A816_DP_SCRATCH_OFFSET+3
        bcc copy_rom_buffer
    .else
        lda 14,s
        sta f:$0344              ; IOCB0 buffer
        lda 18,s
        sta f:$0348              ; IOCB0 length
    .endif
    sep #$20
    lda #11                      ; PUT CHARACTERS; exact ATASCII bytes
    sta f:$0342
    rep #$20
    tsc
    tax
    checkpoint 2
    lda #OS_STACK_TOP
    tcs
    checkpoint 3
    phx                          ; saved_s for this serialized call
    lda #0
    tcd
    phk
    plb
    checkpoint 4
    ldx #0
    .if PROBE_NMI = 18
        pea os_vbi_probe
    .else
        pea CIOV
    .endif
    cli                          ; hardware IRQs remain available to the OS
    checkpoint 5
    cop FORWARD_SIGNATURE        ; production=$00; other low signatures in tests
    rep #$30
    pla                          ; discard COP0 target word
    tya
    and #$00ff                   ; unsigned CIO status
    tay
    checkpoint 6
    pla                          ; recover private saved_s
    .if BANKED
        clc
        adc #256                 ; discard this call's ROM staging buffer
    .endif
    tcs
    checkpoint 7
    tya
    sta 8,s                      ; replace saved A with function result
    sep #$20
    .if COOPERATIVE
        lda #$ff
        sta f:E816_OS_OWNER
    .endif
    lda #0
    sta f:OS_BUSY
    rep #$20
    bra write_return
invalid_pointer_8:
    rep #$20
invalid_pointer:
    lda #ERROR_POINTER
    bra result
busy:
    rep #$20
    lda #ERROR_BUSY
    bra result
empty_write:
    lda #1
result:
    sta 8,s
write_return:
    plb
    pld
    checkpoint 8
    ply
    plx
    pla
    plp                          ; restore caller I and native boundary widths
    .if COOPERATIVE
        pha                      ; preserve CIO result across pending delivery
        lda #E816_SERVICE_POLL
        cop E816_COP
        pla
    .endif
    rtl
console_write_end:

.segment "FAULT"
.a16
.i16
heap_fault:
    lda 4,s                    ; private nonreturning native Abort(reason)
    jmp finish
heap_fault_end:

stack_overflow:
    sta f:FAULT_REQUIRED          ; compiler raw fault contract: A=need, X=S
    txa
    sta f:FAULT_S
    lda #FAULT_STACK
    jmp finish
stack_overflow_end:

; Compiler raw arithmetic-fault ABI: A16=1 (division by zero), X16=S.
; Terminal transfer, no push/unwind; reuse the existing fault report cells.
arithmetic_fault:
    sta f:FAULT_REQUIRED
    txa
    sta f:FAULT_S
    lda #$ff97
    jmp finish
arithmetic_fault_end:

.segment "EXIT"
.a16
.i16
finish:
    sta f:STATUS
    sei
    sep #$20
    lda #0
    sta f:NMIEN
    .if GENERAL_TASKS
        lda f:SD_OWNED
        beq sio_exit_checked
        lda f:SD_STARTED
        beq sio_exit_checked
        lda f:SD_SAFE
        bne sio_exit_checked
        lda #1
        sta f:SD_OFFLINE
sio_exit_checked:
        lda f:SD_OFFLINE
        beq :+
        ; No qualified bus recovery: park with interrupts off, without handing
        ; owned POKEY/callback state or live kernel storage back to ROM.
        rep #$30
        lda #$ff93
        sta f:STATUS
        lda #OS_STACK_TOP
        tcs
        lda #0
        tcd
        phk
        plb
        sep #$30
        sec
        xce
        jmp done
:
        jsl signal_release_shutdown
    .endif
    rep #$30
    cld
    .if GENERAL_TASKS
        ; Terminal cleanup owns the kernel domain; no checked caller wrapper.
        ; Adoption precedes heap initialization, which zeroes the claim ledger.
        lda f:M_ADOPTED
        cmp #M_VERSION
        bne :+
        lda #E816_KERNEL_DP
        tcd
        lda #E816_KERNEL_STACK_TOP-1
        tcs
        sep #$20
        lda #0
        sta 1,s
        rep #$20
        .if CONSOLE_NATIVE
            jsl console_shutdown
        .endif
        jsl HEAP_SHUTDOWN
:
    .endif
    lda #OS_STACK_TOP
    tcs
    lda #0
    tcd
    phk
    plb
    .if COOPERATIVE
        .if PREEMPTIVE
            lda E816_OLD_VBI
            sta VVBLKI
        .endif
        lda E816_OLD_COP
        sta VCOPN
        sep #$20
        lda E816_OLD_COP+2
        sta VCOPN+2
        rep #$20
    .endif
    lda OLD_NMI
    sta VNMIN
    lda OLD_IRQ
    sta VIRQN
    sep #$20
    lda OLD_NMI+2
    sta VNMIN+2
    lda OLD_IRQ+2
    sta VIRQN+2
    lda $14
    sta END_CLOCK
    rep #$20
    lda OLD_MEMLO
    sta MEMLO
state_rejected:
park_os:
    sep #$30
    sec
    xce
    lda #$40
    sta NMIEN
    cli
done:
    bra done                     ; controlled end; OS VBI/IRQ continue

.if COOPERATIVE
    .include "cooperative.s"
.endif

.if GENERAL_TASKS
    .include "tasks-bindings.inc"
.endif
