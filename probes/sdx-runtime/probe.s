; P2 early-entry development fixture. Uses the real ROM VBI and Timer 1 IRQ.
; No Task scheduling or SDX binary is admitted by this standalone fixture.
.setcpu "65816"
.macpack longbranch
.export start, done, installed, removed, guest_loop, guest_return, guest_end
.export emulation_nmi, emulation_irq, native_nmi, phase_wait
.export guest_saved, guest_restore, fast_irq, native_vbi_return
STATE = $2000
OWNER = STATE
PENDING = STATE+2
GUEST_S = STATE+4
VBI_COUNT = STATE+6
IRQ_COUNT = STATE+8
DEFERRED = STATE+10
COMPLETE = STATE+12
OLD_IRQ = STATE+14
OLD_NMI = STATE+16
PORT_SAVE = STATE+19
PHASE_ONCE = STATE+20
NATIVE_SP = $47ef
SDX_ROM_IMAGE = $050000
SDX_ROM_BACKUP = $054000
SDX_ROM_STATE = $057800
SDX_ROM_NMI = emulation_nmi
SDX_ROM_CHAIN_NMI = emulation_nmi_chain_target+1
SDX_ROM_IRQ = emulation_irq
GUEST_PAGE = $057900
HOST_PAGE = $057a00
LOG = $2600

.macro save_full
    rep #$30
.a16
.i16
    pha
    phx
    phy
    phd
    phb
.endmacro
.macro restore_full
    rep #$30
.a16
.i16
    plb
    pld
    ply
    plx
    pla
.endmacro
.macro phase number
    .if PHASE = number
        jsl phase_wait
    .endif
.endmacro

.segment "CODE"
.a8
.i8
start:
    sei
    cld
    stz $d40e
    clc
    xce
    rep #$30
.a16
.i16
    lda #NATIVE_SP
    tcs
    lda #0
    tcd
    phk
    plb
    lda $02e7
    cmp #STATE+1
    jcs failed
    lda $02e5
    cmp #$9000
    jcc failed
    lda #0
    ldx #$3e
clear:
    sta STATE,x
    dex
    dex
    bpl clear
    sta f:SDX_ROM_STATE
    lda $0259
    sta OLD_NMI
    sep #$20
.a8
    lda $025b
    sta OLD_NMI+2
    lda $d301
    sta PORT_SAVE
    rep #$20
.a16
    lda $0216
    sta OLD_IRQ
    lda #$a5a5
    ldx #$11e
guard_dp:
    sta GUEST_DP-$10,x
    sta $23f0,x
    sta $46f0,x
    dex
    dex
    bpl guard_dp
    ldx #$fe
initial_page:
    sta $0100,x
    dex
    dex
    bpl initial_page
    ldx #$3ffe
copy_rom:
    lda $5000,x
    sta f:SDX_ROM_IMAGE,x
    dex
    dex
    bpl copy_rom
    ldx #guest_end-(GUEST_BANK*$10000+$3000)-1
    sep #$20
.a8
copy_guest:
    lda $4000,x
    sta f:GUEST_BANK*$10000+$3000,x
    dex
    bpl copy_guest
    ; Hostile private-bank I/O aliases: old ROM entry would dispatch a DLI.
    lda #$ff
    sta f:GUEST_BANK*$10000+$d40f
    sta f:GUEST_BANK*$10000+$d20e
    ; Known underlying RAM, including vector bytes, tests full restoration.
    lda PORT_SAVE
    and #$fe
    sta $d301
    rep #$20
.a16
    ldx #$0ffe
seed_low:
    txa
    eor #$5aa5
    sta f:$00c000,x
    dex
    dex
    bpl seed_low
    ldx #$27fe
seed_high:
    txa
    eor #$a55a
    sta f:$00d800,x
    dex
    dex
    bpl seed_high
    sep #$20
.a8
    lda PORT_SAVE
    sta $d301
    rep #$20
.a16
    ; Corrupt expected image: fail before changing mapping or taking ownership.
    lda f:SDX_ROM_IMAGE+$0123
    eor #1
    sta f:SDX_ROM_IMAGE+$0123
    jsl sdx_rom_identify
    cmp #2
    jne failed
    lda f:SDX_ROM_IMAGE+$0123
    eor #1
    sta f:SDX_ROM_IMAGE+$0123
    ; An unknown fingerprint must fail the actual install before mapping.
    .repeat 3, profile
        lda f:sdx_rom_profiles+2+profile*10
        eor #1
        sta f:sdx_rom_profiles+2+profile*10
    .endrepeat
    jsl sdx_rom_install
    cmp #2
    jne failed
    lda f:SDX_ROM_STATE
    and #$ff
    jne failed
    sep #$20
.a8
    lda $d301
    cmp PORT_SAVE
    jne failed
    rep #$20
.a16
    .repeat 3, profile
        lda f:sdx_rom_profiles+2+profile*10
        eor #1
        sta f:sdx_rom_profiles+2+profile*10
    .endrepeat
    jsl sdx_rom_install
    cmp #0
    jne failed
    jsl sdx_rom_install
    cmp #3
    jne failed
    ; Foreign PORTB ownership: refuse removal, then restore the owned mapping.
    sep #$20
.a8
    lda $d301
    eor #2
    sta $d301
    rep #$20
.a16
    jsl sdx_rom_remove
    cmp #1
    jne failed
    sep #$20
.a8
    lda $d301
    eor #2
    sta $d301
    rep #$20
.a16
installed:
    lda #native_nmi
    sta $0259
    sep #$20
.a8
    stz $025b
    ; Disable OS IRQ sources. Only real POKEY Timer 1 is owned by the fixture.
    lda #0
    sta $d20e
    sta $10
    sta $d208
    lda #3
    sta $d20f
    lda #15
    sta $d200
    lda #0
    sta $d201
    sta $d209
    lda #$40
    sta $d40e
    rep #$20
.a16
    ; Construct the first saved context in the guest's upper stack image.
    lda #$a5a5
    ldx #$fe
init_guest_page:
    sta f:GUEST_PAGE,x
    dex
    dex
    bpl init_guest_page
    lda #$01e0
    sta GUEST_S
    lda #GUEST_DP
    sta f:GUEST_PAGE+$e2
    lda #$00a6
    sta f:GUEST_PAGE+$e4
    lda #$005a
    sta f:GUEST_PAGE+$e6
    lda #ACCUMULATOR
    sta f:GUEST_PAGE+$e8
    lda #.loword(guest_loop)
    sta f:GUEST_PAGE+$ec
    sep #$20
.a8
    lda #GUEST_BANK
    sta f:GUEST_PAGE+$e1
    lda #GUEST_FLAGS
    sta f:GUEST_PAGE+$ea       ; hook PHP, ignored by the final hardware RTI
    sta f:GUEST_PAGE+$eb       ; hardware status
    .if (GUEST_FLAGS & 4) = 0
        lda #1
        sta $10
        sta $d20e
    .endif
    rep #$20
.a16
    jmp acquire

; Called on a native stack with ownership asserted: a real VBI must defer.
phase_wait:
    php
    save_full
    cld
    lda f:PHASE_ONCE
    bne phase_complete
    inc a
    sta f:PHASE_ONCE
    lda f:DEFERRED
phase_loop:
    cmp f:DEFERRED
    beq phase_loop
phase_complete:
    restore_full
    plp
    rtl

; Native-mode NMI may interrupt page copies, a fast IRQ, or a mode transition.
; It can only acknowledge and latch while physical page one belongs to us.
native_nmi:
    save_full
    cld
    lda f:OWNER
    beq native_chain
    lda #1
    sta f:PENDING
    lda f:DEFERRED
    inc a
    sta f:DEFERRED
    sep #$20
.a8
    lda #0
    sta f:$00d40f
    restore_full
    rti
native_chain:
    restore_full
    jmp [OLD_NMI]

.a8
.i8
emulation_nmi:
    php
    clc
    xce
    save_full
    cld
    lda f:OWNER
    jeq emulation_nmi_chain
    lda 12,s
    cmp #emulation_irq
    bcc :+
    cmp #emulation_irq+3
    bcc nested_entry
:
    cmp #emulation_nmi
    bcc guest_nmi
    cmp #emulation_nmi+3
    bcs guest_nmi
nested_entry:
    lda #1
    sta f:PENDING
    lda f:DEFERRED
    inc a
    sta f:DEFERRED
    sep #$20
.a8
    lda #0
    sta f:$00d40f
    restore_full
    sec
    xce
.a8
.i8
    plp
    rti
.a16
.i16
guest_nmi:
    tsc
    sta f:GUEST_S
    sep #$20
.a8
    lda #0
    sta f:$00d40f
    rep #$20
.a16
    lda #1
    sta f:PENDING
    jmp detach
emulation_nmi_chain:
    restore_full
    sec
    xce
.a8
.i8
    plp
emulation_nmi_chain_target:
    jml $000000

emulation_irq:
    php
    clc
    xce
    save_full
    cld
    lda f:OWNER
    beq emulation_irq_chain
    tsc
    sta f:GUEST_S
    lda #NATIVE_SP
    tcs
    lda #$2400
    tcd
    pea 0
    plb
    plb
fast_irq:
    phase 2
    inc IRQ_COUNT
    sep #$20
.a8
    lda #0
    sta f:$00d20e
    lda #1
    sta f:$00d20e
    rep #$20
.a16
    lda PENDING
    jne detach
    lda GUEST_S
    tcs
    jmp guest_restore
emulation_irq_chain:
    restore_full
    sec
    xce
.a8
.i8
    plp
    jmp (OLD_IRQ)

.a16
.i16
detach:
    lda #NATIVE_SP
    tcs
    lda #$2400
    tcd
    pea 0
    plb
    plb
    phase 3
    ldx #$fe
release_page:
    lda f:$000100,x
    sta f:GUEST_PAGE,x
    lda f:HOST_PAGE,x
    sta f:$000100,x
    dex
    dex
    bpl release_page
    stz OWNER
    ; Copy full saved frame (hidden B, D, DBR, X/Y, P and PC) to an audit log.
    lda VBI_COUNT
    asl a
    asl a
    asl a
    asl a
    tax
    lda GUEST_S
    and #$00ff
    tay
    ; Use sixteen bytes including unused context tail for a fixed record.
    txa
    tay
    lda GUEST_S
    and #$00ff
    tax
    .repeat 13, i
        sep #$20
.a8
        lda f:GUEST_PAGE+1+i,x
        sta LOG+i,y
    .endrepeat
    rep #$20
.a16
    lda GUEST_S
    sta LOG+13,y
    ; The normal OS handler owns page one until its native RTI has retired.
    stz PENDING
    lda #$01ff
    tcs
    phk
    pea native_vbi_return
    sep #$20
.a8
    lda #0
    pha
    rep #$30
.a16
.i16
    jmp [OLD_NMI]
native_vbi_return:
    sei
    rep #$30
    lda #NATIVE_SP
    tcs
    lda #$2400
    tcd
    pea 0
    plb
    plb
    inc VBI_COUNT
    lda VBI_COUNT
    cmp #32
    beq finish
acquire:
    lda #1
    sta OWNER
    phase 1
    ldx #$fe
acquire_page:
    lda f:$000100,x
    sta f:HOST_PAGE,x
    lda f:GUEST_PAGE,x
    sta f:$000100,x
    dex
    dex
    bpl acquire_page
guest_saved:
    phase 4
    lda GUEST_S
    tcs
guest_restore:
    restore_full
    ; Remain native through the long jump: emulation RTI cannot restore PBR.
    jml guest_return

.a16
.i16
finish:
    sep #$20
.a8
    lda #0
    sta $d40e
    sta $d20e
    sta $10
    rep #$20
.a16
    lda OLD_NMI
    sta $0259
    lda OLD_IRQ
    sta $0216
    sep #$20
.a8
    lda OLD_NMI+2
    sta $025b
    rep #$20
.a16
    jsl sdx_rom_remove
    cmp #0
    bne failed
    jsl sdx_rom_remove
    cmp #3
    bne failed
removed:
    lda #$00ff
    sta COMPLETE
done:
    bra done
failed:
    lda #$eeee
    sta f:COMPLETE
    bra done

.include "sdx-rom-shadow.s"

.segment "GUEST"
.a8
.i8
guest_loop:
    jmp guest_loop
guest_return:
    sec
    xce
    plp
    rti
guest_end:
