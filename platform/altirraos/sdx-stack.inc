; ROM stack selection. A is scratch; X remains this activation's saved S.
; The resident descriptor is upper RAM, within the existing SDX reservation.
.ifndef SDX_STACK_PROBE
SDX_STACK_PROBE = 0
.endif
.if SDX_ENABLED .or SDX_RUNTIME_PROBE
    .include "generated/sdx.inc"
.endif

.macro os_stack_enter
    .local current, selected
    .if SDX_ENABLED .or SDX_RUNTIME_PROBE
        jsl sdx_os_stack_enter
        .if SDX_STACK_PROBE = 3
            wai
        .endif
        lda #0
        sta f:SDX_STATE_GATE
    .else
        txa
        and #$ff00
        cmp #$0100
        beq current
        lda #OS_STACK_TOP
        bra selected
current:
        txa
selected:
        tcs
    .endif
.endmacro

; Restore this activation's saved S before permitting another ROM entry.
.macro os_stack_leave
    .local done
    .if SDX_ENABLED .or SDX_RUNTIME_PROBE
        pha
        lda f:SDX_STATE_ROM_DEPTH
        beq done
        .if SDX_STACK_PROBE = 4
            wai
        .endif
        dec a
        sta f:SDX_STATE_ROM_DEPTH
done:
        pla
    .endif
.endmacro
