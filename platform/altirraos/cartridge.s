; Atarimax 8 Mbit cold-boot wrapper for an unchanged Exec816 XEX.
; Both power-on banks contain the same ROM stub. The reader runs in RAM,
; outside the Exec loading arenas and below the cartridge-era E: screen.
; No direct-page storage is borrowed. IRQ and NMI are masked while the cart
; is mapped; INITAD callbacks run with it disabled and the OS interlock set.
.setcpu "6502"
.macpack longbranch
.include "cartridge.inc"
.export cart_start, cart_init, cart_loader, cart_loaded, cart_failed
.export cart_calls, cart_segments, cart_remaining, cart_bank, cart_loader_end

RUNAD = $02e0
INITAD = $02e2
GINTLK = $03fa
TRIG3 = $d013
NMIEN = $d40e

.segment "STUB"
cart_init:
    rts
cart_start:
    sei
    cld
    lda #0
    sta NMIEN
    lda $d301                    ; cart boot can leave BASIC enabled underneath
    ora #2
    sta $d301
    lda #1
    sta $03f8                    ; BASICF: keep BASIC disabled on OS warm start
    lda $02e6                    ; MEMTOP must leave room below E: storage
    cmp #$94
    bcs :+
@no_room:
    jmp @no_room
:
    ldx #0
copy_stub:
    .repeat 4, page
    lda $ba00+page*$100,x
    sta $9000+page*$100,x
    .endrepeat
    inx
    bne copy_stub
    jmp cart_loader

.segment "LOADER"
cart_loader:
    lda #1
    sta cart_bank
    ldx cart_bank
    sta $d500,x
    lda #0
    sta RUNAD
    sta RUNAD+1
    sta cart_calls
    sta cart_calls+1
    sta cart_segments
    sta cart_segments+1
    jsr required_byte
    cmp #$ff
    jne cart_failed
    jsr required_byte
    cmp #$ff
    jne cart_failed
next_segment:
    jsr read_byte
    jcs cart_loaded
    sta write_byte+1
    jsr required_byte
    sta write_byte+2
    and write_byte+1
    cmp #$ff
    beq next_segment              ; optional repeated XEX marker
    jsr required_byte
    sta segment_end
    jsr required_byte
    sta segment_end+1
    lda #0
    sta INITAD
    sta INITAD+1
copy_segment:
    jsr required_byte
write_byte:
    sta $ffff
    lda write_byte+1
    cmp segment_end
    bne @advance
    lda write_byte+2
    cmp segment_end+1
    beq @finished
@advance:
    inc write_byte+1
    bne copy_segment
    inc write_byte+2
    jmp copy_segment
@finished:
    inc cart_segments
    bne :+
    inc cart_segments+1
:
    lda INITAD
    ora INITAD+1
    beq next_segment
    jsr disable_cart
    inc cart_calls
    bne :+
    inc cart_calls+1
:
    jsr call_init
    sei
    lda #0
    sta NMIEN
    sta GINTLK
    ldx cart_bank
    sta $d500,x
    jmp next_segment

cart_failed:
    jsr disable_cart
    lda #$34
    sta $02c8                    ; visible failure, no partial program entry
@park:
    jmp @park

cart_loaded:
    jsr disable_cart
    lda RUNAD
    ora RUNAD+1
    beq cart_failed
    jmp (RUNAD)

call_init:
    jmp (INITAD)

disable_cart:
    sta $d580                    ; writes work on hardware and the pinned emulator
    lda TRIG3                    ; OS interlock must match the disabled cartridge
    sta GINTLK
    lda #$40
    sta NMIEN
    cli
    rts

required_byte:
    jsr read_byte
    bcs cart_failed
    rts

; Carry denotes the exact end of the embedded XEX, including across banks.
read_byte:
    lda cart_remaining
    ora cart_remaining+1
    ora cart_remaining+2
    beq read_eof
    lda cart_remaining
    bne @decrement_low
    lda cart_remaining+1
    bne @decrement_middle
    dec cart_remaining+2
@decrement_middle:
    dec cart_remaining+1
@decrement_low:
    dec cart_remaining
source_byte:
    lda $a000
    inc source_byte+1
    bne @done
    inc source_byte+2
    ldx source_byte+2
    cpx #$c0
    bne @done
    pha
    lda #$a0
    sta source_byte+2
    inc cart_bank
    ldx cart_bank
    cpx #127
    bcs cart_failed
    sta $d500,x
    pla
@done:
    clc
    rts
read_eof:
    sec
    rts

segment_end: .word 0
cart_bank: .byte 1
cart_calls: .word 0
cart_segments: .word 0
cart_remaining: .faraddr XEX_BYTES
cart_loader_end:
