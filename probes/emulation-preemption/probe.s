; Disposable CPU/ROM experiment, not an Exec scheduler implementation.
.setcpu "65816"
.export start, done, guest_loop, guest_return, guest_end

STATE = $2000
SAVED = STATE                 ; 16-byte context, copied to LOG on each entry
COUNT = STATE+$10
NESTED = STATE+$12
WRAP = STATE+$14
COMPLETE = STATE+$16
NATIVE_OK = STATE+$18
GUEST_DP = $2200
SHADOW = $2300
NATIVE_DP = $2400
LOG = $2600
NMIEN = $d40e
NMIRES = $d40f
VVBLKI = $0222
VNMIN = $0259

.segment "CODE"
.a8
.i8
start:
    sei
    cld
    stz NMIEN
    clc
    xce
    rep #$30
.a16
.i16
    lda #$47ef
    tcs
    lda #0
    tcd
    phk
    plb
    ; All reservations must fit below the loader's screen allocation.
    lda $02e7
    cmp #STATE+1
    bcs bad_memory
    lda $02e5
    cmp #$4810
    bcs memory_ok
bad_memory:
    lda #$eeee
    sta COMPLETE
    jmp done
memory_ok:
    lda #0
    ldx #$003e
clear_state:
    sta STATE,x
    dex
    dex
    bpl clear_state
    sta NATIVE_DP
    ; Guard both DP pages and the shadow as one owned region.
    lda #$a5a5
    ldx #$031e
fill_pages:
    sta $21f0,x
    dex
    dex
    bpl fill_pages
    stz NATIVE_DP
    ldx #$010e
fill_stack:
    sta $4700,x
    dex
    dex
    bpl fill_stack
    ldx #$00fe
fill_page_one:
    sta $0100,x
    dex
    dex
    bpl fill_page_one
    ; The upper-bank payload is embedded immediately after bank-zero code.
    sep #$20
.a8
    ldx #0
copy_guest:
    lda $4000,x
    sta f:$023000,x
    inx
    cpx #guest_end-$023000
    bne copy_guest
    ; ROM E=1 NMI reads/writes DBR:$D40F before our VBI hook. DLI is off.
    lda #0
    sta f:$03d40f
    ; Deliberately different bytes distinguish wrapped and linear DP indexing.
    lda #$69
    sta GUEST_DP+$ba
    lda #$96
    sta GUEST_DP+$1ba
    rep #$20
.a16
    lda #vbi_hook
    sta VVBLKI
    lda #native_nmi
    sta VNMIN
    sep #$20
.a8
    stz VNMIN+2
    ; Enter the 6502 guest with a private aligned DP and upper data bank.
    rep #$20
.a16
    lda #GUEST_DP
    tcd
    lda #$01ef
    tcs
    sep #$20
.a8
    lda #3
    pha
    plb
    sep #$10
.i8
    ldx #$fe
    lda $bc,x
    sta f:WRAP+1                 ; same instruction in E=0 reads $23BA
    sec
    xce
.i8
    jml guest_start

; The unmodified ROM has pushed A8/X8/Y8 after the E=1 hardware frame.
; No pushes until S is moved: preserve the complete guest page-one image.
vbi_hook:
    clc
    xce
    rep #$30
.a16
.i16
    sta f:SAVED
    lda #0
    adc #0                       ; XCE returned the interrupted E bit
    sta f:SAVED+11
    txa
    sta f:SAVED+2
    tya
    sta f:SAVED+4
    tdc
    sta f:SAVED+8
    tsc
    tax
    clc
    adc #6
    sta f:SAVED+6
    lda f:$000005,x               ; interrupted PC, original PBR is NOT saved
    sta f:SAVED+13
    sep #$20
.a8
    lda f:$000004,x
    sta f:SAVED+12
    lda #0
    sta f:NMIRES                  ; acknowledge the real bank-zero ANTIC
    sta f:$03d40f                 ; keep ROM's next VBI/DLI test predictable
    rep #$20
.a16
    lda #$47ef
    tcs
    phb
    sep #$20
.a8
    pla
    sta f:SAVED+10
    phk
    plb
    rep #$20
.a16
    lda #NATIVE_DP
    tcd
    lda COUNT
    asl a
    asl a
    asl a
    asl a
    tax
    ldy #0
copy_context:
    lda SAVED,y
    sta LOG,x
    inx
    inx
    iny
    iny
    cpy #16
    bne copy_context
    lda COUNT
    cmp #64
    beq finish
    ldx #$00fe
save_page_one:
    lda $0100,x
    sta SHADOW,x
    dex
    dex
    bpl save_page_one
    jsr native_worker
    ldx #$00fe
restore_page_one:
    lda SHADOW,x
    sta $0100,x
    dex
    dex
    bpl restore_page_one
    ; Restore D/DBR/hidden B, then let E=1 pulls restore A/X/Y/P/PC.
    lda SAVED+8
    tcd
    sep #$20
.a8
    lda SAVED+10
    pha
    plb
    rep #$20
.a16
    lda f:SAVED+6
    sec
    sbc #6
    tcs
    lda f:SAVED
    sec
    xce
.a8
.i8
    jml guest_return             ; E=1 RTI itself cannot restore PBR

.a16
.i16
finish:
    sep #$20
.a8
    stz NMIEN
    lda #$ff
    sta COMPLETE
done:
    bra done

.a16
.i16
native_worker:
    ; A distinct native DP and stack; deliberately destroy all guest stack RAM.
    lda #$5a5a
    ldx #$00fe
destroy_page_one:
    sta $0100,x
    dex
    dex
    bpl destroy_page_one
    lda $00
    clc
    adc #7
    sta $00
    inc COUNT
    lda COUNT
    cmp #1
    bne worker_done
    ; Exercise one real nested VBI while native, on the private native stack.
    lda #$abcd
    ldx #$1234
    ldy #$5678
    wai
    cmp #$abcd
    bne worker_done
    cpx #$1234
    bne worker_done
    cpy #$5678
    bne worker_done
    tdc
    cmp #NATIVE_DP
    bne worker_done
    tsc
    cmp #$47ed                    ; JSR return address occupies two bytes
    bne worker_done
    inc NATIVE_OK
worker_done:
    rts

; Native NMI has its own route: never treats a partial guest transition as
; another guest switch. It preserves the current native domain and only ticks.
native_nmi:
    rep #$30
    pha
    phx
    phy
    phd
    phb
    cld
    phk
    plb
    sep #$20
.a8
    lda #0
    sta NMIRES
    rep #$20
.a16
    inc NESTED
    plb
    pld
    ply
    plx
    pla
    rti

.segment "GUEST"
.a8
.i8
guest_start:
    sei
    ldx #$fe
    lda $bc,x                    ; aligned E=1 DP: $2200 + (($BC+$FE)&$FF)
    sta f:WRAP
    ; Keep live values on page one across every interruption.
    lda #$12
    pha
    lda #$34
    pha
    ; The hidden B register survives E=1 and must survive the native worker.
    lda #$ab
    xba
    lda #$fd                     ; N/V/D/I/C set, Z clear; E=1 M/X forced
    pha
    lda #$cd
    ldx #$5a
    ldy #$a6
    plp
guest_loop:
    jmp .loword(guest_loop)       ; plain 6502 loop: no calls/yields/cooperation
guest_return:
    ply
    plx
    pla
    rti
guest_end:
