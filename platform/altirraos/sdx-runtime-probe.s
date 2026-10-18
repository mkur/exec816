; Shared emulation-mode bridge. SDX_ENABLED uses generated DP reservations
; and Image-owned guest banks. P2 diagnostic fixtures use the same transitions.
; One Image retains each slot through the Process retirement acknowledgement.
.include "generated/sdx.inc"
SDX_ROM_IMAGE = $280000
SDX_ROM_BACKUP = $284000
SDX_ROM_STATE = $287800
SDX_ROM_NMI = sdx_probe_nmi_stub
SDX_ROM_IRQ = sdx_probe_irq_stub
SR_OWNER = $287802
SR_PENDING = $287804
SR_INDEX = $287806
SR_ROUTE = $287808
SR_NMIS = $28780a
SR_IRQS = $28780c
SR_DEFERRED = $28780e
SR_EARLY = $287810
SR_INJECT = $287812
SR_REWINDS = $287814
SR_POPPED = $287816
SR_FORCED = $287818
SR_LEAK = $28781a
SR_SERIAL_IRQS = $28781c
SR_WORK = $28781e
SR_COPY_IRQS = $287820
SR_HOST = $287900
SR_CONTEXT = SDX_CONTEXT_BASE             ; two 512-byte records, first 256 = page one
SR_NATIVE_S = SR_CONTEXT+$100
SR_NATIVE_D = SR_CONTEXT+$102
SR_GUEST_S = SR_CONTEXT+$104
SR_EVENT = SR_CONTEXT+SDX_FIELDS_EVENT
SR_BANK = SR_CONTEXT+SDX_FIELDS_BANK

; Page-one transfers run on the native Task stack. Service owned byte/timer
; edges between at most sixteen words, without admitting ROM or scheduling.
; X indexes an aligned image/record. A is dead at each copy checkpoint.
.macro sr_copy_checkpoint
    .local done
    txa
    and #$1f
    bne done
    jsr sr_copy_irq
done:
.endmacro

; Diagnostic WAI sites force a real VBI at one return boundary. The NMI
; replaces the selected WAI with NOP once per guest, before normal handling.
; IRQ sources are disabled in these cases; no artificial interrupt is called.
.macro sr_test_restore name
    rep #$30
    .if SDX_RETURN_PROBE = 2
name:
        wai
    .endif
    plb
    .if SDX_RETURN_PROBE = 3
name:
        wai
    .endif
    pld
    .if SDX_RETURN_PROBE = 4
name:
        wai
    .endif
    ply
    .if SDX_RETURN_PROBE = 5
name:
        wai
    .endif
    plx
    .if SDX_RETURN_PROBE = 6
name:
        wai
    .endif
    pla
    .if SDX_RETURN_PROBE = 7
name:
        wai
    .endif
.endmacro

.macro sr_test_guest_pause pc
    .local done, other, counted, read_guest, write_guest
    .if SDX_RETURN_PROBE >= 8
        lda pc,s
        cmp #$f081+(SDX_RETURN_PROBE-8)*2
        bne done
        .if SDX_ENABLED
            lda f:SR_INDEX
            tax
            sep #$20
            lda f:SR_BANK,x
            sta f:read_guest+3
            sta f:write_guest+3
            rep #$20
read_guest:
            lda f:$00f080+(SDX_RETURN_PROBE-8)*2
            and #$ff
            cmp #$cb
            bne done
            sep #$20
.a8
            lda #$ea
write_guest:
            sta f:$00f080+(SDX_RETURN_PROBE-8)*2
        .else
        lda f:SR_OWNER
        cmp #1
        bne other
        lda f:$30f080+(SDX_RETURN_PROBE-8)*2
        and #$ff
        cmp #$cb
        bne done
        sep #$20
.a8
        lda #$ea
        sta f:$30f080+(SDX_RETURN_PROBE-8)*2
        bra counted
.a16
other:
        lda f:$31f080+(SDX_RETURN_PROBE-8)*2
        and #$ff
        cmp #$cb
        bne done
        sep #$20
.a8
        lda #$ea
        sta f:$31f080+(SDX_RETURN_PROBE-8)*2
counted:
        .endif
        rep #$20
.a16
        lda f:SR_FORCED
        inc a
        sta f:SR_FORCED
 done:
    .endif
.endmacro

.segment "STUBS"
.export sdx_probe_nmi_stub, sdx_probe_irq_stub, sdx_probe_stubs_end
.export sdx_probe_installed
.a8
.i8
sdx_probe_nmi_stub:
    php
    clc
    xce
    jml sdx_probe_emulation_nmi
.a8
.i8
sdx_probe_irq_stub:
    php
    ; Optional one-shot test hold, before XCE. A real VBI must return to this
    ; bank-zero entry, not the same PC offset in the guest bank. The hold's
    ; delay is deliberate test stimulus, not production IRQ timing evidence.
    pha
    lda f:SR_INJECT
    beq sr_entry_ready
    lda f:SR_OWNER
    beq sr_entry_ready
sr_entry_wait:
    lda f:SR_EARLY
    beq sr_entry_wait
sr_entry_ready:
    pla
    clc
    xce
    jml sdx_probe_emulation_irq
sdx_probe_chain_nmi:
    restore_full
    sec
    xce
    plp
    jml $00c17b
sdx_probe_chain_irq:
    restore_full
    sec
    xce
    plp
    jml $00c1e1
sdx_probe_emulation_return:
    sec
    xce
    plp
    rti
sdx_probe_stubs_end:
sdx_probe_installed:
    rtl                         ; bank-zero observation point for the pinned bridge
; E=1 does not stack PBR. All guest images must exclude this PC interval:
; a nested NMI here belongs to bank zero, even while SR_OWNER names a guest.
; Fixed synthetic images are checked by the test packager. A production
; loader must reserve equivalent transition ranges before binary admission.

.if SDX_ENABLED
    .segment "SDX_WORK"
.else
    .segment "NATIVE_WORK"
.endif
.include "sdx-rom-shadow.s"
.export sdx_probe_install, sdx_probe_remove, sdx_probe_run, sdx_probe_service
.export sdx_probe_install_end, sdx_probe_remove_end, sdx_probe_run_end
.export sdx_probe_native_nmi, sdx_probe_resume, sdx_probe_service_return
.a16
.i16
sdx_probe_install:
    signal_stack_check 96
    php
    sei
    sep #$20
.a8
    lda #0
    sta f:$00d40e
    rep #$20
.a16
    jsl sdx_rom_install
    cmp #0
    bne sdx_probe_install_return
    lda #.loword(sdx_probe_native_nmi)
    sta f:$000259
    sep #$20
.a8
    lda #^sdx_probe_native_nmi
    sta f:$00025b
    rep #$20
.a16
    lda #0
sdx_probe_install_return:
    pha
    sep #$20
.a8
    lda #$40
    sta f:$00d40e
    rep #$20
.a16
    pla
    jsl sdx_probe_installed
    plp
    rtl

sdx_probe_install_end:
sdx_probe_remove:
    signal_stack_check 96
    php
    sei
    sep #$20
.a8
    lda #0
    sta f:$00d40e
    rep #$20
.a16
    jsl sdx_rom_remove
    cmp #0
    bne sdx_probe_install_return
    lda #native_nmi
    sta f:$000259
    sep #$20
.a8
    lda #0
    sta f:$00025b
    rep #$20
.a16
    lda #0
    bra sdx_probe_install_return

sdx_probe_remove_end:
; Run(CARD slot): native v2 ABI, returns guest event 1 or 2 in A16.
; Requires an IRQ-enabled native Task caller; slot ownership is caller-held.
; Four private saved bytes remain on this Task's stack while its guest runs.
sdx_probe_run:
    signal_stack_check 96
    php
    sei
    phb
    phd
    lda 8,s
    xba
    asl a
    tax
    tsc
    sta f:SR_NATIVE_S,x
    tdc
    sta f:SR_NATIVE_D,x
sdx_probe_resume:
    sei
    rep #$30
    lda 8,s
    pha
    inc a
    sta f:SR_OWNER              ; native NMI can now only acknowledge/latch
    pla
    xba
    asl a
    tax
    txa
    sta f:SR_INDEX
.if SDX_ENABLED
    ; No guest runs during this native prefix. Once OWNER is published, NMI
    ; only latches and the scheduler cannot change these jump operands.
    sep #$20
    lda f:SR_BANK,x
    sta f:sr_jump_zero+3
    sta f:sr_jump_one+3
    rep #$20
.endif
    lda #0
    sta f:SR_EVENT,x
    pea 0
    plb
    plb
    ldx #$fe
sr_save_host:
    lda a:$0100,x
    sta f:SR_HOST,x
    dex
    dex
    sr_copy_checkpoint
    txa
    bpl sr_save_host
    lda f:SR_INDEX
    tax
    ldy #$00fe
    txa
    clc
    adc #$fe
    tax
sr_acquire:
    ; X indexes the selected guest record; Y indexes physical page one.
    lda f:SR_CONTEXT,x
    sta a:$0100,y
    dex
    dex
    dey
    dey
    sr_copy_checkpoint
    tya
    bpl sr_acquire
    ; A copy poll can have queued a completion without another IRQ edge.
    jsl native_work_pending
    jcs sr_irq_work
    lda f:T_WAKE_PENDING
    and #$ff
    jne sr_irq_work
    lda f:SR_INDEX
    tax
    lda f:SR_GUEST_S,x
    tcs
sr_restore:
    ; The NMI interceptor owns the interval from this last pending check
    ; through the final native XCE. It can rebuild any partially popped frame.
    lda f:SR_PENDING
.if SDX_RETURN_PROBE = 1
sr_pause_check:
    wai
.endif
sr_restore_checked:
    bne sr_restore_pending
    ; Select guest bank while registers remain saved; the far trampoline is
    ; chosen before restoring hidden B, DBR and D. Each branch restores itself.
    lda f:SR_INDEX
    beq sr_restore_zero
sr_restore_one:
    sr_test_restore sr_pause_one
sr_jump_one:
    jml $31f080
sr_restore_zero:
    sr_test_restore sr_pause_zero
sr_jump_zero:
    jml $30f080
sr_restore_end:
sr_restore_pending:
    lda #0
    sta f:SR_ROUTE
    jmp sr_capture

sdx_probe_run_end:
.a8
.i8
sdx_probe_emulation_nmi:
    save_full
    cld
    lda f:SR_OWNER
    jeq sr_chain_emulation_nmi
    sr_test_guest_pause 12
    lda 12,s
    cmp #sdx_probe_nmi_stub
    bcc sr_guest_nmi
    cmp #sdx_probe_stubs_end
    bcs sr_guest_nmi
    lda #1
    sta f:SR_PENDING
    sta f:SR_EARLY
    lda f:SR_DEFERRED
    inc a
    sta f:SR_DEFERRED
    sep #$20
.a8
    lda #0
    sta f:$00d40f
    restore_full
    jml sdx_probe_emulation_return
sr_guest_nmi:
    lda #1
    sta f:SR_PENDING
    lda f:SR_NMIS
    inc a
    sta f:SR_NMIS
    sep #$20
.a8
    lda #0
    sta f:$00d40f
    rep #$20
.a16
    lda #0
    sta f:SR_ROUTE
    jmp sr_capture
sr_chain_emulation_nmi:
    jml sdx_probe_chain_nmi

.a16
.i16

sdx_probe_emulation_irq:
    save_full
    cld
    lda f:SR_OWNER
    jeq sr_chain_emulation_irq
    lda f:SR_INDEX
    tax
    tsc
    sta f:SR_GUEST_S,x
    lda f:SR_NATIVE_S,x
    tcs
    lda #0
    tcd
    pea 0
    plb
    plb
    sep #$20
.a8
    lda f:$00d20e
    eor #$ff
    and f:$000010
    and #$38                    ; real enabled serial RX/TX/complete edges
    beq :+
    rep #$20
    lda f:SR_SERIAL_IRQS
    inc a
    sta f:SR_SERIAL_IRQS
    sep #$20
:
    jsl signal_route
    rep #$20
.a16
    bcc sr_unowned_irq
    lda f:SR_IRQS
    inc a
    sta f:SR_IRQS
    lda f:SR_PENDING
    bne sr_irq_nmi
    jsl native_work_pending
    bcs sr_irq_work
    lda f:T_WAKE_PENDING
    and #$ff
    bne sr_irq_work
    lda f:SR_INDEX
    tax
    lda f:SR_GUEST_S,x
    tcs
    jmp sr_restore
sr_irq_work:
    lda #2
    sta f:SR_ROUTE
    lda f:SR_WORK
    inc a
    sta f:SR_WORK
    jmp sr_detach
sr_unowned_irq:
    lda #1
    sta f:SR_ROUTE
    jmp sr_detach
sr_irq_nmi:
    lda #0
    sta f:SR_ROUTE
    jmp sr_detach
sr_chain_emulation_irq:
    jml sdx_probe_chain_irq

.a16
.i16
; The guest-local veneer supplies A=event after saving the standard 13 bytes.
; It enters E=0 before the cross-bank jump, and keeps the JSR return in page one.
sdx_probe_service:
    cld
    pha
    lda f:SR_INDEX
    tax
    pla
    sta f:SR_EVENT,x
    tsc
    tax
    lda f:$00000c,x             ; JSR saved PC needs the increment RTI omits
    inc a
    sta f:$00000c,x
sr_capture:
    lda f:SR_INDEX
    tax
    tsc
    sta f:SR_GUEST_S,x
sr_detach:
    lda f:SR_INDEX
    tax
    lda f:SR_NATIVE_S,x
    tcs
    lda f:SR_NATIVE_D,x
    tcd
    pea 0
    plb
    plb
    ldy #$fe
    txa
    clc
    adc #$fe
    tax
sr_release:
    lda a:$0100,y
    sta f:SR_CONTEXT,x
    dex
    dex
    dey
    dey
    sr_copy_checkpoint
    tya
    bpl sr_release
    ldx #$fe
sr_restore_host:
    lda f:SR_HOST,x
    sta a:$0100,x
    dex
    dex
    sr_copy_checkpoint
    txa
    bpl sr_restore_host
    lda #0
    sta f:SR_OWNER              ; OS/page-one work may now run normally
    lda f:SR_INDEX
    tax
    lda f:SR_EVENT,x
    bne sr_deliver_event
    lda f:SR_PENDING
    bne sr_deliver_nmi
    lda f:SR_ROUTE
    bne sr_deliver_irq
sr_deliver_nmi:
    lda #0
    sta f:SR_PENDING
    phk
    pea .loword(sdx_probe_resume)
    sep #$20
.a8
    lda #0                     ; ordinary IRQ-enabled native Task continuation
    pha
    rep #$30
.a16
.i16
    jml native_nmi              ; OS VBI retires before standard frame validation
sr_deliver_irq:
    cmp #2
    beq sr_deliver_owned
    phk
    pea .loword(sdx_probe_resume)
    sep #$20
.a8
    lda #0
    pha
    rep #$30
.a16
.i16
    jml native_irq
sr_deliver_owned:
    ; The raw owned handler has retired. Admit its work using the same full
    ; native frame and scheduling tail as an ordinary owned native IRQ.
    ; Do not route the already-acknowledged hardware edge a second time.
    phk
    pea .loword(sdx_probe_resume)
    sep #$20
.a8
    lda #0
    pha
    rep #$30
.a16
.i16
    save_full
    lda #0
    tcd
    jml interrupt_schedule
sr_deliver_event:
    lda f:SR_PENDING
    beq sdx_probe_service_return
    lda #0
    sta f:SR_PENDING
    phk
    pea .loword(sdx_probe_service_return)
    sep #$20
.a8
    lda #0
    pha
    rep #$30
.a16
.i16
    jml native_nmi
sdx_probe_service_return:
    ; Recover slot from this Task's private continuation after any scheduling.
    lda 8,s
    xba
    asl a
    tax
    lda f:SR_EVENT,x
    pld
    plb
    plp
    rtl

sdx_probe_native_nmi:
    save_full
    cld
    lda f:SR_OWNER
    jeq sr_chain_native_nmi
    lda #1
    sta f:SR_PENDING
    lda f:SR_DEFERRED
    inc a
    sta f:SR_DEFERRED
    sep #$20
.a8
    lda #0
    sta f:$00d40f
    rep #$20
.a16
    .if SDX_RETURN_PROBE >= 8
        sr_test_guest_pause 11
    .elseif SDX_RETURN_PROBE > 0
        lda 13,s
        and #$ff
        cmp #^sr_restore
        bne sr_pause_done
        lda 11,s
        .if SDX_RETURN_PROBE = 1
            cmp #.loword(sr_pause_check+1)
            bne sr_pause_done
            lda f:sr_pause_check
            and #$ff
            cmp #$cb
            bne sr_pause_done
            sep #$20
            lda #$ea
            sta f:sr_pause_check
        .else
            cmp #.loword(sr_pause_one+1)
            bne :+
            lda f:sr_pause_one
            and #$ff
            cmp #$cb
            bne sr_pause_done
            sep #$20
            lda #$ea
            sta f:sr_pause_one
            bra :++
:
.a16
            cmp #.loword(sr_pause_zero+1)
            bne sr_pause_done
            lda f:sr_pause_zero
            and #$ff
            cmp #$cb
            bne sr_pause_done
            sep #$20
            lda #$ea
            sta f:sr_pause_zero
:
        .endif
        rep #$20
        lda f:SR_FORCED
        inc a
        sta f:SR_FORCED
sr_pause_done:
    .endif
    ; Native NMI supplies its own PBR, even during the last guest-bank SEC
    ; and XCE. After XCE, the ordinary E=1 path captures that continuation.
    lda 13,s
    and #$ff
    cmp #^sr_restore
    beq sr_intercept_restore
    .if SDX_ENABLED
        ; The saved PBR must match the retained owner's actual private bank.
        pha
        lda f:SR_INDEX
        tax
        pla
        cmp f:SR_BANK,x
        jne sr_native_nmi_return
    .else
        cmp #$30
        jcc sr_native_nmi_return
        cmp #$32
        jcs sr_native_nmi_return
    .endif
    lda 11,s
    cmp #$f080
    jcc sr_native_nmi_return
    cmp #$f084
    jcs sr_native_nmi_return
    lda #9
    bra sr_rebuild_frame
sr_intercept_restore:
    lda 11,s
    cmp #.loword(sr_restore)
    bcc sr_native_nmi_return
    cmp #.loword(sr_restore_end)
    bcs sr_native_nmi_return
    cmp #.loword(sr_restore_one)
    bcc sr_rebuild_zero
    cmp #.loword(sr_restore_zero)
    bcc sr_intercept_one
    .if SDX_RETURN_PROBE >= 2 .and SDX_RETURN_PROBE <= 7
        cmp #.loword(sr_pause_zero+1)
        bcc :+
        dec a
:
    .endif
    sec
    sbc #.loword(sr_restore_zero)
    bra sr_intercept_popped
sr_intercept_one:
    .if SDX_RETURN_PROBE >= 2 .and SDX_RETURN_PROBE <= 7
        cmp #.loword(sr_pause_one+1)
        bcc :+
        dec a
:
    .endif
    sec
    sbc #.loword(sr_restore_one)
sr_intercept_popped:
    ; REP / PLB / PLD / PLY / PLX / PLA / JML: only the registers
    ; already popped are live in this NMI's saved register prefix.
    cmp #3
    bcc sr_rebuild_zero
    sec
    sbc #3
    asl a
    inc a
    bra sr_rebuild_frame
sr_rebuild_zero:
    lda #0
sr_rebuild_frame:
    sta f:SR_POPPED
    lda f:SR_REWINDS
    inc a
    sta f:SR_REWINDS
    pea 0
    plb
    plb
    tsc
    clc
    adc f:SR_POPPED
    tay                         ; last live register byte in the nested frame
    lda f:SR_INDEX
    tax
    lda f:SR_GUEST_S,x
    tcd                         ; temporary native D = original full guest frame
    lda f:SR_POPPED
    tax
    beq sr_rebuild_done
    sep #$20
.a8
sr_rebuild_copy:
    ; Destination is above source, and can overlap it. Copy backwards.
    lda a:0,y
    sta 0,x
    dey
    dex
    bne sr_rebuild_copy
    rep #$20
.a16
sr_rebuild_done:
    tdc
    tcs                         ; discard the retired nested native activation
    jmp sr_restore_pending      ; detach before entering the OS or scheduler
sr_native_nmi_return:
    restore_full
    rti
sr_chain_native_nmi:
    restore_full
    jml native_nmi

.a16
.i16
sr_copy_irq:
    sep #$20
.a8
    lda f:$00d20e
    eor #$ff
    and f:$000010
    beq sr_copy_quiet
    phx
    phy
    phd
    phb
    rep #$20
.a16
    lda #0
    tcd
    pea 0
    plb
    plb
    lda f:SR_COPY_IRQS
    inc a
    sta f:SR_COPY_IRQS
    sep #$20
.a8
    jsl signal_route             ; raw handler only, with ownership still held
    rep #$30
.a16
.i16
    plb
    pld
    ply
    plx
    rts
.a8
sr_copy_quiet:
    rep #$20
.a16
    rts
