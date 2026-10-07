; OF816 hosted by the same pinned AltirraOS 65816 ROM as Exec816.
; All storage here is boot-only; Exec later initializes the root and kernel pools.
.setcpu "65816"
.smart
.include "boot-layout.inc"
.import _Forth_initialize, _Forth_ui, of_system_interface
.export of_start, of_handoff, of_park, of_load, of_target, of_count
.export of_putchar, of_getchar, of_key_ready, of_nmi, of_irq
.export of_wait_key, of_keys, of_phase, of_io_status
.export of_saved_vectors, of_saved_iocb, of_saved_nmien
.export of_nmis, of_irqs
.export of_autoboot, of_autoboot_wait, of_seconds
.export of_os_stack, of_return

CIOV = $e456
NMIEN = $d40e
NMIST = $d40f
RTCLOK_LOW = $0014
CH = $02fc
BRKKEY = $0011
SKSTAT = $d20f
AUTOBOOT_SECONDS = 5
TICKS_PER_SECOND = 50         ; pinned PAL profile, independent of CPU multiplier

.segment "BOOT"
.a8
.i8

; XEX INITAD callback. Stay in emulation mode on the loader's OS stack.
; Each record copies 1..256 bytes; zero count denotes a complete 256-byte page.
of_load:
    php
    pha
    phx
    ldx #0
of_copy:
    lda f:OF_STAGE,x
    .byte $9f                 ; STA long,X; operand supplied by XEX record
of_target:
    .faraddr $ffffff
    inx
    cpx of_count
    bne of_copy
    lda of_count
    ldx #0
    cmp #0
    bne :+
    inx                      ; zero denotes a full 256-byte page
:
    jsr EXEC_PROGRESS_ADD
    plx
    pla
    plp
    rts
of_count: .byte 0

of_start:
    ; INITAD owns a live emulation-mode loader frame. Keep it on page one,
    ; with all ROM activations below this saved context, until the final RTS.
    php
    sei
    pha
    xba
    pha
    phx
    phy
    phb
    phd
    phk
    plb
    jsr EXEC_PROGRESS_FINISH
    lda EXEC_LOADER_ERROR
    beq :+
    jmp EXEC_LOADER           ; failed bootstrap never starts the monitor
:
    cld
    lda #0
    sta NMIEN
    clc
    xce
    rep #$30
    tsc
    sta of_os_stack
    lda #0
    tcd
    phk
    plb
    ; Vectors stay masked until the whole pair has been replaced.
    ldx #4
@vectors:
    lda $0259,x
    sta of_saved_vectors,x
    dex
    dex
    bpl @vectors
    ldx #31
@iocb:
    sep #$20
    lda $0340,x
    sta of_saved_iocb,x
    dex
    bpl @iocb
    lda $0350
    cmp #$ff
    beq @available
    jmp of_leave             ; fixed IOCB1 must be free before taking it
@available:
    rep #$20
    lda #of_nmi
    sta $0259
    lda #of_irq
    sta $025c
    sep #$20
    lda #0
    sta $025b
    sta $025e
    rep #$20
    lda #$a5a5
    ldx #14
@guards:
    sta OF_STACK-16,x
    sta OF_STACK+1536,x
    sta OF_STACK+512,x
    sta OF_ADAPTER-16,x
    sta OF_ADAPTER+1536,x
    sta OF_ADAPTER+$4f0,x
    dex
    dex
    bpl @guards
    ldx #1534
@return_stack:
    sta OF_STACK,x
    dex
    dex
    bpl @return_stack
    ldx #254
@caller_stack:
    sta OF_ADAPTER+$500,x
    dex
    dex
    bpl @caller_stack
    lda #0
    ldx #254
@dp:
    sta OF_DP,x
    dex
    dex
    bpl @dp
    ; OF816 data-space guards lie outside its supplied usable range.
    lda #$a5a5
    ldx #14
@upper:
    sta f:OF_DATA,x
    sta f:OF_DATA+$fff0,x
    dex
    dex
    bpl @upper
    ; Keyboard input uses K:; OF816 handles editing and echo itself.
    lda #keyboard_name
    sta $0354
    lda #0
    sta $0358
    sep #$20
    lda #3
    sta $0352
    lda #4
    sta $035a
    lda #0
    sta $035b
    sta of_keys
    sta of_keys+1
    sta NMIST
    lda #$40
    sta of_saved_nmien        ; the qualified profile enables VBI, no DLI
    sta NMIEN
    rep #$20
    ldx #16
    jsr cio
    lda of_io_status
    and #$0080
    beq @opened
    jmp of_bye
@opened:
    ; OF saves its caller S while using its own return stack. Keep the caller
    ; frame off page one, which CIO and native interrupt entry reuse.
    lda #OF_ADAPTER+$5ff
    tcs
    lda #OF_DP
    tcd
    pea .hiword(OF_DATA+$fff0)
    pea .loword(OF_DATA+$fff0)
    pea .hiword(OF_DATA+16)
    pea .loword(OF_DATA+16)
    pea OF_STACK+512-OF_DP
    pea OF_STACK-OF_DP
    pea OF_STACK+1535
    pea .hiword(of_system_interface)
    pea .loword(of_system_interface)
    jsl _Forth_initialize
    lda #1
    sta f:of_phase
    cli
    ldx #boot_hint
    jsr print_hint
    lda #AUTOBOOT_SECONDS
    sta f:of_seconds
    lda f:RTCLOK_LOW
    and #$ff
    sta f:of_clock
of_autoboot:
    lda f:of_seconds
    clc
    adc #'0'
    jsl of_putchar
    lda #' '
    jsl of_putchar
of_autoboot_wait:
    jsl of_key_ready
    bne @cancel
    lda f:BRKKEY
    and #$ff
    beq @cancel
    ; Modulo subtraction survives the low clock byte wrapping. Advance the
    ; deadline, rather than restarting it after the countdown's console output.
    lda f:RTCLOK_LOW
    sec
    sbc f:of_clock
    and #$ff
    cmp #TICKS_PER_SECOND
    bcc of_autoboot_wait
    lda f:of_clock
    clc
    adc #TICKS_PER_SECOND
    and #$ff
    sta f:of_clock
    lda f:of_seconds
    dec a
    sta f:of_seconds
    bne of_autoboot
    lda #10
    jsl of_putchar
    jmp of_handoff
@cancel:
    ; Wait for release before clearing the pending key, including repeats.
    ; Do not call K: here: modifier/lock keys need not produce a character.
    lda f:SKSTAT
    and #4
    beq @cancel
    sep #$20
    lda #$ff
    sta f:CH
    sta f:BRKKEY
    rep #$20
    ldx #forth_hint
    jsr print_hint
@ui:
    jsl _Forth_ui
    jmp of_bye

print_hint:
    lda f:0,x
    and #$ff
    beq @done
    jsl of_putchar
    inx
    bra print_hint
@done:
    rts

; Native context is saved before touching D or using shared OS memory. An NMI
; inside CIO/IRQ keeps the live page-one S, preserving that nested activation.
.macro interrupt vector, count
    .local already_os, returned
    rep #$30
    pha
    phx
    phy
    phd
    phb
    cld
    tsc
    tax
    and #$ff00
    cmp #$0100
    beq already_os
    lda f:of_os_stack
    tcs
already_os:
    phx
    lda #0
    tcd
    phk
    plb
    inc count
    phk
    pea returned
    sep #$20
    lda f:10,x               ; interrupted P, below the nine saved bytes
    and #4
    pha
    rep #$20
    jmp [vector]
returned:
    sei
    rep #$30
    pla
    tcs
    plb
    pld
    ply
    plx
    pla
    rti
.endmacro

of_nmi:
    interrupt of_saved_vectors, of_nmis
of_irq:
    interrupt of_saved_vectors+3, of_irqs

; Serialize CIO in this single-threaded monitor. The saved native S lives on
; the OS stack so nested NMI/IRQ frames cannot overwrite it.
cio:
    php
    rep #$30
    pha
    phx
    phy
    phd
    phb
    sei
    tsc
    tay
    and #$ff00
    cmp #$0100
    beq @on_os_stack
    lda f:of_os_stack
    tcs
@on_os_stack:
    phy
    lda #0
    tcd
    phk
    plb
    pea CIOV
    cli
    cop $00
    rep #$30
    pla
    tya
    sta f:of_io_status
    sei
    pla
    tcs
    plb
    pld
    ply
    plx
    pla
    plp
    rts

of_putchar:
    phx
    and #$00ff
    cmp #13
    beq @done                 ; CR/LF becomes a single ATASCII end of line
    cmp #10
    bne @backspace
    lda #$9b
@backspace:
    cmp #8
    bne @store
    lda #$7e
@store:
    sta f:of_character
    lda #of_character
    sta f:$0344
    lda #1
    sta f:$0348
    sep #$20
    lda #11
    sta f:$0342
    rep #$20
    ldx #0
    jsr cio
@done:
    plx
    rtl

of_key_ready:
    lda f:CH
    and #$00ff
    cmp #$ff
    beq @no
    lda #$ffff
    rtl
@no:
    lda #0
    rtl

of_getchar:
    phx
of_wait_key:
    lda #of_character
    sta f:$0354
    lda #1
    sta f:$0358
    sep #$20
    lda #7
    sta f:$0352
    rep #$20
    ldx #16
    jsr cio
    ; Returned bytes are ASCII to the Forth core, ATASCII only at this edge.
    lda f:of_character
    and #$00ff
    cmp #$9b
    bne @delete
    lda #13
@delete:
    cmp #$7e
    bne @return
    lda #8
@return:
    pha
    lda f:of_keys
    inc a
    sta f:of_keys
    pla
    plx
    rtl

; Retire Forth and return to the paused INITAD reader. Mask NMI as well as IRQ
; across the stack/mode transition; the caller's complete frame stays live.
of_handoff:
    sei
    rep #$30
    sep #$20
    lda #0
    sta f:NMIEN
    rep #$20
    lda f:of_os_stack
    tcs
    lda #0
    tcd
    phk
    plb
    lda #2
    sta of_phase
    jsr release_keyboard
    jsr restore_vectors
    sep #$30
    sec
    xce
of_return:
    ; The OS now sees E=1 and a valid page-one stack before VBI is enabled.
    lda #$40
    sta NMIEN
    pld
    plb
    ply
    plx
    pla
    xba
    pla
    plp
    rts

of_bye:
    sei
    rep #$30
    sep #$20
    lda #0
    sta f:NMIEN
    rep #$20
    lda f:of_os_stack
    tcs
    lda #0
    tcd
    phk
    plb
    jsr release_keyboard
of_leave:
    rep #$30
    jsr restore_vectors
    lda EXEC_OLD_MEMLO
    sta $02e7
    sep #$30
    sec
    xce
    cld
    lda #$40
    sta NMIEN
    cli
of_park:
    jmp of_park

.a16
.i16
release_keyboard:
    sep #$20
    lda #12
    sta $0352
    rep #$20
    ldx #16
    jsr cio
    ldx #31
@restore:
    sep #$20
    lda of_saved_iocb,x
    sta $0340,x
    dex
    bpl @restore
    rep #$20
    rts

restore_vectors:
    sei
    sep #$20
    lda #0
    sta NMIEN
    rep #$20
    ldx #4
@restore:
    lda of_saved_vectors,x
    sta $0259,x
    dex
    dex
    bpl @restore
    sep #$20
    lda #0
    sta NMIST
    rep #$20
    rts

keyboard_name: .byte "K:",$9b
boot_hint: .byte "Press a key for Forth.",10,"Exec816 in: ",0
forth_hint: .byte 10,"Type EXEC816 to start Exec816.",10,0
of_seconds: .word 0
of_clock: .word 0
of_character: .word 0
of_io_status: .word 0
of_phase: .word 0
of_keys: .word 0
of_nmis: .word 0
of_irqs: .word 0
of_saved_nmien: .byte $40
of_saved_vectors: .res 6,0
of_saved_iocb: .res 32,0
of_os_stack: .word 0
