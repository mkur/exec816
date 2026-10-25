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
SR_CONTEXT = SDX_CONTEXT_BASE
SR_NATIVE_S = SR_CONTEXT+SDX_FIELDS_NATIVE_S
SR_NATIVE_D = SR_CONTEXT+SDX_FIELDS_NATIVE_D
SR_GUEST_S = SR_CONTEXT+SDX_FIELDS_GUEST_S
SR_EVENT = SR_CONTEXT+SDX_FIELDS_EVENT
SR_BANK = SR_CONTEXT+SDX_FIELDS_BANK

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
; A nested CIO VBI already owns page one and a complete saved context. Enter
; the ROM's emulation dispatcher directly, avoiding a second native wrapper.
sdx_probe_nested_vbi:
    sec
    xce
    jml $00c17b
sdx_probe_nested_emulation_return:
    clc
    xce
    rep #$30
    jml sr_rom_emulation_return
sdx_probe_nested_native_return:
    clc
    xce
    rep #$30
    jml sr_rom_native_return
sdx_probe_stubs_end:
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
.segment "CONSOLE"
sdx_probe_installed:
    rtl                         ; bank-zero rendezvous in existing console padding
.if SDX_ENABLED
    .segment "SDX_WORK"
.else
    .segment "NATIVE_WORK"
.endif
; All hosted callers are bank zero and supply X=their saved native S. Keep the
; shared selector in upper RAM. Its three-byte return is reconstructed below
; the selected S; the caller clears GATE only after RTL has retired it.
sdx_os_stack_enter:
    lda #1
    sta f:SDX_STATE_GATE
    .if SDX_STACK_PROBE = 1
        wai
    .endif
    lda 1,s
    tay
    lda f:SDX_STATE_ROM_DEPTH
    bne sr_os_nested
    lda f:SDX_STATE_LEASE
    beq sr_os_normal
    lda f:SDX_STATE_ANCHOR
    beq sr_os_normal            ; lease acquired, no physical frame constructed
    cmp #SDX_STACK_FLOOR+SDX_ROM_RESERVE
    bcc sr_os_failed
    lda #1
    sta f:SDX_STATE_ROM_DEPTH
    lda f:SDX_STATE_ANCHOR
    bra sr_os_selected
sr_os_nested:
    inc a
    sta f:SDX_STATE_ROM_DEPTH
    bra sr_os_current
sr_os_normal:
    txa
    and #$ff00
    cmp #$0100
    beq sr_os_current
    lda #OS_STACK_TOP
    bra sr_os_selected
sr_os_current:
    txa
sr_os_selected:
    tcs
    .if SDX_STACK_PROBE = 2
        wai
    .endif
    sep #$20
    lda #0
    pha
    rep #$20
    phy
    rtl
sr_os_failed:
    lda #SDX_ROM_RESERVE
    jml stack_overflow

.export sdx_probe_acquire, sdx_probe_release, sdx_probe_enter, sdx_probe_moveframe
.export sdx_probe_acquire_end, sdx_probe_release_end
.export sdx_probe_enter_end, sdx_probe_moveframe_end
.export sdx_probe_bind, sdx_probe_bind_end, sdx_probe_unbind, sdx_probe_unbind_end
; Caller has filled the unpublished upper record. Publish ownership last.
sdx_probe_bind:
    signal_stack_check 8
    php
    sei
    lda 5,s
    inc a
    cmp f:SDX_STATE_LEASE
    jne sr_bind_failed
    lda #0
    sta f:SDX_BINDING_BASE+SDX_BINDING_OWNER
.if SDX_ENABLED
    sta f:SDX_BINDING_BASE+SDX_BINDING_ZERO
    lda f:SDX_BINDING_BASE+SDX_BINDING_SCREEN
    sta f:sr_cell_read+1
    sta f:sr_cell_compare+1
    sta f:sr_cell_write+1
    sep #$20
    lda f:SDX_BINDING_BASE+SDX_BINDING_SCREEN+2
    sta f:sr_cell_read+3
    sta f:sr_cell_compare+3
    sta f:sr_cell_write+3
    rep #$20
    lda f:SDX_BINDING_BASE+SDX_BINDING_FIRST
    sta f:sr_cell_first_compare+1
    sta f:sr_cell_first_write+1
    sep #$20
    lda f:SDX_BINDING_BASE+SDX_BINDING_FIRST+2
    sta f:sr_cell_first_compare+3
    sta f:sr_cell_first_write+3
    rep #$20
    lda f:SDX_BINDING_BASE+SDX_BINDING_END
    sta f:sr_cell_end_compare+1
    sta f:sr_cell_end_write+1
    sep #$20
    lda f:SDX_BINDING_BASE+SDX_BINDING_END+2
    sta f:sr_cell_end_compare+3
    sta f:sr_cell_end_write+3
    rep #$20
    lda f:SDX_BINDING_BASE+SDX_BINDING_PENDING
    sta f:sr_cell_break+1
    sep #$20
    lda f:SDX_BINDING_BASE+SDX_BINDING_PENDING+2
    sta f:sr_cell_break+3
    rep #$20
    lda f:SDX_BINDING_BASE+SDX_BINDING_PENDING
    ora f:SDX_BINDING_BASE+SDX_BINDING_PENDING+1
    bne :+
    lda #.loword(SDX_BINDING_BASE+SDX_BINDING_ZERO)
    sta f:sr_cell_break+1
    sep #$20
    lda #^SDX_BINDING_BASE
    sta f:sr_cell_break+3
    rep #$20
:
    lda 5,s
    asl a
    asl a
    asl a
    asl a
    clc
    adc #.loword(SR_EVENT)
    sta f:sr_cell_event+1
    sta f:sr_cell_event_clear+1
    .if SDX_STACK_PROBE = 8
        wai
    .endif
.endif
    lda 5,s
    inc a
    sta f:SDX_BINDING_BASE+SDX_BINDING_OWNER
    lda #1
    plp
    rtl
sr_bind_failed:
    lda #0
    plp
    rtl
sdx_probe_bind_end:

; A parked interpreter must not unpublish another Image's live screen.
sdx_probe_unbind:
    signal_stack_check 8
    php
    sei
    lda 5,s
    inc a
    cmp f:SDX_BINDING_BASE+SDX_BINDING_OWNER
    bne sr_unbind_done
    lda #0
    sta f:SDX_BINDING_BASE+SDX_BINDING_OWNER
sr_unbind_done:
    plp
    rtl
sdx_probe_unbind_end:

; Lease admission is a normal operational failure. IRQ masking excludes Task
; dispatch; NMI may run ROM because no frame exists yet and ANCHOR remains zero.
sdx_probe_acquire:
    signal_stack_check 8
    php
    sei
    lda f:SDX_STATE_LEASE
    bne sr_lease_busy
    lda 5,s
    inc a
    sta f:SDX_STATE_LEASE
    lda #1
    plp
    rtl
sr_lease_busy:
    lda #0
    plp
    rtl
sdx_probe_acquire_end:

; Construct the small physical frame with IRQs masked only for these stores.
; Private bank/DP initialization has already completed on the native stack.
sdx_probe_enter:
    signal_stack_check 8
    php
    sei
    lda #1
    sta f:SDX_STATE_GATE
    lda 5,s
    asl a
    asl a
    asl a
    asl a
    tax
    lda #SDX_INITIAL_S
    sta f:SR_GUEST_S,x
    sta f:SDX_STATE_ANCHOR
    sep #$20
    lda f:SR_BANK,x
    sta f:SDX_INITIAL_S+SDX_FRAME_DBR
    rep #$20
    lda f:SR_CONTEXT+SDX_FIELDS_DP,x
    sta f:SDX_INITIAL_S+SDX_FRAME_D
    .if SDX_STACK_PROBE = 5
        wai
    .endif
    lda #0
    sta f:SDX_INITIAL_S+SDX_FRAME_Y
    sta f:SDX_INITIAL_S+SDX_FRAME_X
    sta f:SDX_INITIAL_S+SDX_FRAME_A
    lda #$2020
    sta f:SDX_INITIAL_S+SDX_FRAME_VENEER_P
    lda f:SR_CONTEXT+SDX_FIELDS_ENTRY,x
    sta f:SDX_INITIAL_S+SDX_FRAME_PC
    lda #SDX_EXIT_PC-1
    sta f:$0001ee
    lda #SDX_PHASES_SERVICE
    sta f:SDX_STATE_PHASE
    lda #0
    sta f:SDX_STATE_GATE
    plp
    rtl
sdx_probe_enter_end:

; Relocate one complete frame under the same IRQ/NMI gate. Slot and target
; are caller-owned; only physical stack-domain bounds are checked here.
sdx_probe_moveframe:
    signal_stack_check 8
    php
    sei
    phb
    lda #1
    sta f:SDX_STATE_GATE
    lda 6,s
    asl a
    asl a
    asl a
    asl a
    tax
    lda f:SR_GUEST_S,x
    phx
    tax
    lda 10,s
    tay
    cpy #SDX_MINIMUM_S
    jcc sr_frame_bad
    cpy #$1f0
    jcs sr_frame_bad
    pea 0
    plb
    plb
    tya
    phx
    cmp 1,s
    plx
    bcc sr_frame_down
    sep #$20
    .repeat 13, byte
        lda a:13-byte,x
        sta a:13-byte,y
    .endrepeat
    bra sr_frame_moved
sr_frame_down:
    sep #$20
    .repeat 13, byte
        lda a:1+byte,x
        sta a:1+byte,y
        .if SDX_STACK_PROBE = 6 .and byte = 6
            wai
        .endif
    .endrepeat
sr_frame_moved:
    rep #$20
    plx
    tya
    sta f:SR_GUEST_S,x
    sta f:SDX_STATE_ANCHOR
    lda #0
    sta f:SDX_STATE_GATE
    plb
    plp
    rtl
sr_frame_bad:
    tsc
    tax
    lda #13
    jml stack_overflow
sdx_probe_moveframe_end:

; All native I/O and guest continuations have retired before this call.
sdx_probe_release:
    signal_stack_check 96
    php
    sei
    lda #1
    sta f:SDX_STATE_GATE
    lda #0
    sta f:SR_OWNER
    sta f:SDX_BINDING_BASE+SDX_BINDING_OWNER
    sta f:SDX_STATE_ANCHOR
    .if SDX_STACK_PROBE = 7
        wai
    .endif
    sta f:SDX_STATE_PHASE
    sta f:SDX_STATE_LEASE
    sta f:SDX_STATE_GATE
    lda f:SR_PENDING
    beq sr_release_return
    lda #0
    sta f:SR_PENDING
    phk
    pea .loword(sr_release_return)
    sep #$20
    lda #0
    pha
    rep #$30
    jml native_nmi
sr_release_return:
    plp
    rtl
sdx_probe_release_end:

.if SDX_ENABLED
.export sdx_probe_guards, sdx_probe_guards_end
; Check the same 32 fixed DP-guard bytes on every boundary. Word loads remove
; the interpreter/compiler loop overhead without reducing guard coverage.
sdx_probe_guards:
    signal_stack_check 8
    .repeat SDX_DP_GUARD_BYTES/2, word
        lda f:SDX_DP_BASE-SDX_DP_GUARD_BYTES+word*2
        cmp #$a5a5
        jne sr_guards_bad
        lda f:SDX_DP_BASE+SDX_DP_SLOTS*256+word*2
        cmp #$a5a5
        jne sr_guards_bad
    .endrepeat
    lda #1
    rtl
sr_guards_bad:
    lda #0
    rtl
sdx_probe_guards_end:
.endif

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
    asl a
    asl a
    asl a
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
    asl a
    asl a
    asl a
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
    lda f:SR_GUEST_S,x
    sta f:SDX_STATE_ANCHOR
    lda #SDX_PHASES_GUEST
    sta f:SDX_STATE_PHASE
    lda f:SR_GUEST_S,x
    tcs
sr_restore:
.export sdx_probe_guest_restore
sdx_probe_guest_restore:
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
sr_capture:
    lda f:SR_INDEX
    tax
    jmp sr_capture_context

sdx_probe_run_end:
.a8
.i8
sdx_probe_emulation_nmi:
    save_full
    cld
    lda f:SDX_STATE_GATE
    jne sr_rom_emulation_nmi
    lda f:SDX_STATE_ROM_DEPTH
    beq sr_emulation_not_rom
    cmp #1
    jne sr_rom_emulation_nmi
    lda f:OS_BUSY
    and #$ff
    jeq sr_rom_emulation_nmi
    tsc
    and #$ff00
    cmp #$0100
    jne sr_rom_emulation_nmi
    ; CIO may wait for RTCLOK during fine scrolling. Run one ordinary VBI on
    ; this activation's current page-one S; OS_BUSY excludes Task dispatch.
    ; A deeper VBI only acknowledges/latches, bounding recursive ROM entry.
    lda #2
    sta f:SDX_STATE_ROM_DEPTH
    lda #0
    tcd
    pea 0
    plb
    plb
    pea sdx_probe_nested_emulation_return
    sep #$20
    lda #0
    pha
    jml sdx_probe_nested_vbi
sr_rom_emulation_return:
    restore_full
    pha
    lda #1
    sta f:SDX_STATE_ROM_DEPTH
    pla
    jml sdx_probe_emulation_return
sr_emulation_not_rom:
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
sr_rom_emulation_nmi:
    lda f:SDX_STATE_ROM_NMIS
    inc a
    sta f:SDX_STATE_ROM_NMIS
    lda #1
    sta f:SR_PENDING
    sep #$20
    lda #0
    sta f:$00d40f
    restore_full
    jml sdx_probe_emulation_return

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
    tay
    lda f:SR_INDEX
    tax
    tya
    sta f:SR_EVENT,x
    lda SDX_FRAME_PC,s          ; JSR saved PC needs the increment RTI omits
    inc a
    sta SDX_FRAME_PC,s
sr_capture_context:
    tsc
    sta f:SR_GUEST_S,x
.if SDX_ENABLED
    .if SDX_STACK_PROBE = 9
        wai
    .endif
    ; Complete frame and corrected PC are now stable. Successful bound cells
    ; never return to the Action! service loop. All failures detach normally.
    lda f:SR_EVENT,x
    cmp #SDX_RAWCON_EVENT+3
    beq sr_cell_candidate
    cmp #SDX_RAWCON_EVENT+4
    jne sr_detach
sr_cell_candidate:
    lda f:SDX_BINDING_BASE+SDX_BINDING_OWNER
    jeq sr_detach
    cmp f:SR_OWNER
    jne sr_detach
    tsc
    cmp #SDX_MINIMUM_S
    jcc sr_detach
    cmp #$1f0
    jcs sr_detach
    ; Only native detachment publishes a ROM-borrowable anchor. OWNER/GATE
    ; exclude borrowing throughout this leaf and the common guest restore.
    lda #1
    sta f:SDX_STATE_GATE
    lda #SDX_PHASES_FAST_CELL
    sta f:SDX_STATE_PHASE
    pea 0
    plb
    plb
    ; No Task stack checker is legal with S in page one. This leaf has only
    ; four saved DP bytes plus the 13-byte acknowledge-only native NMI frame.
    .repeat SDX_DP_GUARD_BYTES/4, word
        lda a:SDX_DP_BASE-SDX_DP_GUARD_BYTES+word*2
        cmp #$a5a5
        bne sr_cell_guard_failed
        lda a:SDX_DP_BASE+SDX_DP_SLOTS*256+word*2
        cmp #$a5a5
        bne sr_cell_guard_failed
    .endrepeat
    bra sr_cell_guard_tail
sr_cell_guard_failed:
    jmp sr_cell_detach
sr_cell_guard_tail:
    .repeat SDX_DP_GUARD_BYTES/4, word
        lda a:SDX_DP_BASE-SDX_DP_GUARD_BYTES+SDX_DP_GUARD_BYTES/2+word*2
        cmp #$a5a5
        bne sr_cell_guard_failed
        lda a:SDX_DP_BASE+SDX_DP_SLOTS*256+SDX_DP_GUARD_BYTES/2+word*2
        cmp #$a5a5
        bne sr_cell_guard_failed
    .endrepeat
    lda f:SR_NATIVE_D,x
    tcd
    lda SDX_CELL_SCRATCH_DP
    pha
    lda SDX_CELL_SCRATCH_DP+2
    pha
    .if SDX_STACK_PROBE = 10
        wai
    .endif
    ; Bind patched these operands before publishing owner. A NULL foreground
    ; pointer selects the binding's immutable zero word. There is no repeated
    ; pointer assembly or lookup while the physical stack is active.
sr_cell_break:
    lda f:$000000
    and #$ff
    jne sr_cell_failed
sr_cell_coordinates:
    lda f:SR_CONTEXT+SDX_FIELDS_DP,x
    tax
    lda a:$0054,x               ; row low, column high in private guest DP
    tay
    and #$ff
    cmp f:SDX_BINDING_BASE+SDX_BINDING_HEIGHT
    jcs sr_cell_failed
    sta SDX_CELL_SCRATCH_DP      ; CARD row
    asl a
    tax
    tya
    xba
    and #$ff
    cmp f:SDX_BINDING_BASE+SDX_BINDING_WIDTH
    jcs sr_cell_failed
    sta SDX_CELL_SCRATCH_DP+2    ; CARD column
    clc
    adc f:SDX_BINDING_BASE+SDX_BINDING_ROWS,x
    tax
sr_cell_event:
    lda f:SR_EVENT              ; operand names this binding's context slot
    lsr a                      ; only admitted events 43 (get) / 44 (put)
    bcs sr_cell_get
.export sdx_probe_cell_put
sdx_probe_cell_put:
    sep #$20
    lda SDX_FRAME_A+SDX_CELL_SCRATCH_SAVED_BYTES,s
sr_cell_compare:
    cmp f:$000000,x
    jeq sr_cell_done8
sr_cell_write:
    sta f:$000000,x
    .if SDX_STACK_PROBE = 11
        wai
    .endif
    ldx SDX_CELL_SCRATCH_DP
    lda SDX_CELL_SCRATCH_DP+2
sr_cell_first_compare:
    cmp f:$000000,x
    bcs :+
sr_cell_first_write:
    sta f:$000000,x
:
    inc a
sr_cell_end_compare:
    cmp f:$000000,x
    bcc sr_cell_done8
sr_cell_end_write:
    sta f:$000000,x
    bra sr_cell_done8
sr_cell_get:
.export sdx_probe_cell_get
sdx_probe_cell_get:
    sep #$20
sr_cell_read:
    lda f:$000000,x
    sta SDX_FRAME_A+SDX_CELL_SCRATCH_SAVED_BYTES,s
    ; Only low A and its emulation N/Z change; hidden B and every other flag
    ; come from the original complete frame.
    cmp #0
    beq sr_cell_zero
    and #$80
    bra sr_cell_flags
sr_cell_zero:
    lda #2
sr_cell_flags:
    sta SDX_CELL_SCRATCH_DP
    lda SDX_FRAME_P+SDX_CELL_SCRATCH_SAVED_BYTES,s
    and #$7d
    ora SDX_CELL_SCRATCH_DP
    sta SDX_FRAME_P+SDX_CELL_SCRATCH_SAVED_BYTES,s
sr_cell_done8:
.export sdx_probe_cell_committed
sdx_probe_cell_committed:
    rep #$20
    lda #0
sr_cell_event_clear:
    sta f:SR_EVENT            ; consumed exactly once, even if VBI is pending
    pla
    sta SDX_CELL_SCRATCH_DP+2
    pla
    sta SDX_CELL_SCRATCH_DP
    .if SDX_STACK_PROBE = 12
        wai
    .endif
    lda #SDX_PHASES_GUEST
    sta f:SDX_STATE_PHASE
    lda #0
    sta f:SDX_STATE_GATE
    .if SDX_STACK_PROBE = 13
        wai
    .endif
    ; The physical complete S is restored; sr_restore drains pending VBI via
    ; sr_capture/sr_detach before the next guest instruction. Never enter the
    ; native-call prologue at sdx_probe_resume from this physical S.
    jmp sr_restore
sr_cell_failed:
    rep #$20
    pla
    sta SDX_CELL_SCRATCH_DP+2
    pla
    sta SDX_CELL_SCRATCH_DP
sr_cell_detach:
    lda #0
    sta f:SDX_STATE_GATE
.endif
sr_detach:
.export sdx_probe_detach
sdx_probe_detach:
    lda f:SR_INDEX
    tax
    lda f:SR_NATIVE_S,x
    tcs
    lda f:SR_NATIVE_D,x
    tcd
    pea 0
    plb
    plb
    lda f:SR_GUEST_S,x
    sta f:SDX_STATE_ANCHOR
    lda #SDX_PHASES_SERVICE
    sta f:SDX_STATE_PHASE
    lda #0
    sta f:SR_OWNER              ; native Tasks/ROM may borrow below ANCHOR
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
    asl a
    asl a
    asl a
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
    lda f:SDX_STATE_GATE
    jne sr_rom_native_nmi
    lda f:SDX_STATE_ROM_DEPTH
    beq sr_native_not_rom
    cmp #1
    jne sr_rom_native_nmi
    lda f:OS_BUSY
    and #$ff
    jeq sr_rom_native_nmi
    tsc
    and #$ff00
    cmp #$0100
    jne sr_rom_native_nmi
    lda #2
    sta f:SDX_STATE_ROM_DEPTH
    lda #0
    tcd
    pea 0
    plb
    plb
    pea sdx_probe_nested_native_return
    sep #$20
    lda #0
    pha
    jml sdx_probe_nested_vbi
sr_rom_native_return:
    restore_full
    pha
    lda #1
    sta f:SDX_STATE_ROM_DEPTH
    pla
    rti
sr_native_not_rom:
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
sr_rom_native_nmi:
    lda f:SDX_STATE_ROM_NMIS
    inc a
    sta f:SDX_STATE_ROM_NMIS
    lda #1
    sta f:SR_PENDING
    sep #$20
    lda #0
    sta f:$00d40f
    restore_full
    rti
sr_chain_native_nmi:
    restore_full
    jml native_nmi
