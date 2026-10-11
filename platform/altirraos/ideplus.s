; Native PBI transactions. IRQ excludes ROM PBI dispatch; SWITCHING excludes
; Task transitions. The pinned VBI chain never accesses IDE registers/latches.
; It still runs and records ticks. Preserve selection and its OS shadow.
.include "ideplus.inc"
.include "ideplus-storage.inc"
.segment "SIGNAL_CODE"
.a16
.i16
.export ideplus_read_register,ideplus_read_register_end
.export ideplus_write_register,ideplus_write_register_end
.export ideplus_read_words,ideplus_read_words_end
.export ideplus_write_words,ideplus_write_words_end

; DP $80..$87 is the caller's call-clobbered workspace, never global storage.
IP_POINTER = $80
IP_VALUE = $84
IP_SELECTED = $85
IP_RESULT = $86

; Diagnostic-only instruction boundaries. No production code or reservation.
.macro ideplus_checkpoint point
    .if HEAP_PROBE
        .ident(.sprintf("ideplus_probe_%u", point)):
        .export .ident(.sprintf("ideplus_probe_%u", point))
        .repeat 4
            nop
        .endrepeat
    .endif
.endmacro

ideplus_enter:
    sep #$20
    lda #1
    sta f:E816_SWITCHING
    lda f:$0247
    sta IP_SELECTED
    lda #1                      ; configured initial PBI ID 0
    ideplus_checkpoint 1
    sta f:$0247
    ideplus_checkpoint 2
    sta f:$d1ff
    ideplus_checkpoint 3
    rts
ideplus_leave:
    lda IP_SELECTED
    sta f:$0247
    ideplus_checkpoint 6
    sta f:$d1ff
    ideplus_checkpoint 7
    lda #0
    sta f:E816_SWITCHING
    rep #$20
    rts

.a16
ideplus_read_register:
    signal_stack_check 9
    jsr io_context
    lda 4,s
    tax
    .if HEAP_PROBE
        ; Inject bounded BSY delays for a selected active-request phase.
        ; The worker still uses its real clock, timer and scheduling path.
        cpx #IP_REG_ALTSTATUS
        bne ideplus_real_register
        sep #$20
        lda f:IP_PROBE+2
        beq ideplus_real_register8
        cmp f:IP_META_BUS+10
        bne ideplus_real_register8
        rep #$20
        lda f:IP_PROBE
        beq ideplus_real_register
        dec a
        sta f:IP_PROBE
        lda #$80
        rtl
ideplus_real_register8:
        rep #$20
ideplus_real_register:
    .endif
    php
    sei
    jsr ideplus_enter
    lda f:$00d100,x
    sta IP_RESULT
    jsr ideplus_leave
    plp
    lda IP_RESULT
    and #$ff
    rtl
ideplus_read_register_end:

.a16
ideplus_write_register:
    signal_stack_check 9
    jsr io_context
    lda 4,s
    tax
    lda 6,s
    sep #$20
    sta IP_VALUE
    rep #$20
    php
    sei
    jsr ideplus_enter
    lda IP_VALUE
    sta f:$00d100,x
    jsr ideplus_leave
    plp
    rtl
ideplus_write_register_end:

.a16
ideplus_read_words:
    signal_stack_check 9
    jsr io_context
    lda 4,s
    sta IP_POINTER
    sep #$20
    lda 6,s
    sta IP_POINTER+2
    rep #$20
    ldy #0
ideplus_read_pair:
    php
    sei
    jsr ideplus_enter
    lda f:$00d110
    sta [IP_POINTER],y
    iny
    ideplus_checkpoint 4
    lda f:$00d100
    sta [IP_POINTER],y
    iny
    jsr ideplus_leave
    plp
    cpy #512
    bcc ideplus_read_pair
    rtl
ideplus_read_words_end:

.a16
ideplus_write_words:
    signal_stack_check 9
    jsr io_context
    lda 4,s
    sta IP_POINTER
    sep #$20
    lda 6,s
    sta IP_POINTER+2
    rep #$20
    ldy #0
ideplus_write_pair:
    php
    sei
    jsr ideplus_enter
    iny
    lda [IP_POINTER],y
    sta f:$00d100
    ideplus_checkpoint 5
    dey
    lda [IP_POINTER],y
    sta f:$00d110
    iny
    iny
    jsr ideplus_leave
    plp
    cpy #512
    bcc ideplus_write_pair
    rtl
ideplus_write_words_end:

.if HEAP_PROBE
.export ideplus_probe_wait
; Patched into one four-NOP boundary by the host. Await one real VBI, once.
; Preserve the exact interrupted widths, flags, A, X and Y.
ideplus_probe_wait:
    php
    rep #$30
    pha
    phx
    phy
    lda f:IP_PROBE+4
    bne ideplus_probe_wait_done
    inc a
    sta f:IP_PROBE+4
    lda f:NMI_COUNT
:
    cmp f:NMI_COUNT
    beq :-
ideplus_probe_wait_done:
    ply
    plx
    pla
    plp
    rtl

.endif
