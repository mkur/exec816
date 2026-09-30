; ROM characterization, not the Exec interrupt or syscall adapter.
; CASE: 0=VBI/page-one, 1=VBI/private-stack (stop before unsafe unwind),
; 2=COP0 console/page-one, 3=COP0/private-stack (host stops after ROM XCE),
; 4=COP signature routing with harmless replacement service handlers.
.setcpu "65816"
.export start, done, after_wait, message, message_end

RESULT = $2000
OS_S = RESULT+16
OS_D = RESULT+18
OS_DBR = RESULT+20
OS_E = RESULT+21
VBI_COUNT = RESULT+22
ROUTE = RESULT+23
CIO_STATUS = RESULT+24
CLOCK_BEFORE = RESULT+25
CLOCK_AFTER = RESULT+26
OLD_VBI = RESULT+28
OLD_COP0 = RESULT+30
OLD_COPU = RESULT+33
COMPLETION = RESULT+63
MEMLO = $02e7
MEMTOP = $02e5
VVBLKI = $0222
VCOP0 = $0262
VCOPU = $0265
NMIEN = $d40e
CIOV = $e456

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
    ; The disposable XEX does not return to its loader. Use a known stack.
    lda #$01ef
    tcs
    phk
    plb
    lda #0
    tcd
    ldx #$003e
clear_result:
    sta RESULT,x
    dex
    dex
    bpl clear_result
    lda MEMLO
    cmp #RESULT
    bcc memlo_ok
    beq memlo_ok
    jmp bad_memory
memlo_ok:
    lda MEMTOP
    cmp #$4810
    bcs memory_ok
bad_memory:
    sep #$20
.a8
    lda #$ee
    sta COMPLETION
    jmp done
memory_ok:
.a16
    lda #$a5a5
    ldx #$011e
fill_dp:
    sta $21f0,x
    dex
    dex
    bpl fill_dp
    ldx #$010e
fill_stack:
    sta $4700,x
    dex
    dex
    bpl fill_stack
    ; Bottom-of-page guard only: do not overwrite the active stack.
    ldx #$000e
fill_os_guard:
    sta $0100,x
    dex
    dex
    bpl fill_os_guard
    lda VVBLKI
    sta OLD_VBI
    lda #vbi_hook
    sta VVBLKI
    lda VCOP0
    sta OLD_COP0
    lda VCOPU
    sta OLD_COPU
    sep #$20
.a8
    lda VCOP0+2
    sta OLD_COP0+2
    lda VCOPU+2
    sta OLD_COPU+2
    lda $14
    sta CLOCK_BEFORE

.if CASE = 4
    rep #$20
.a16
    lda #route_zero
    sta VCOP0
    lda #route_user
    sta VCOPU
    sep #$20
.a8
    stz VCOP0+2
    stz VCOPU+2
.endif

.if CASE = 2
    ; IOCB 0 is the OS's already-open screen editor. PUT RECORD, clear screen.
    lda #9
    sta $0342
    lda #<message
    sta $0344
    lda #>message
    sta $0345
    lda #<(message_end-message)
    sta $0348
    lda #>(message_end-message)
    sta $0349
.endif

    rep #$30
.a16
.i16
.if CASE = 1 .or CASE = 3
    lda #$47ef
    tcs
.endif
    lda #$2200
    tcd
    sep #$20
.a8
    lda #$12
    pha
    plb
    ; All subsequent probe state accesses explicitly use bank zero.
.if CASE = 0 .or CASE = 1
    lda #$40
    sta f:NMIEN
    lda #FLAGS
    pha
    rep #$30
.a16
.i16
    lda #$abcd
    ldx #$1234
    ldy #$5678
    plp
    wai
after_wait:
    jmp capture
.else
after_wait:
.if CASE = 2
    ; Native COP0 requires the target address on the caller's stack.
    ; IRQs remain available during this OS console call.
    lda #$40
    sta f:NMIEN
    cli
    rep #$30
.a16
.i16
    ldx #0
    ldy #0
    pea CIOV
    cop $00
    php
    rep #$30
    tya
    sep #$20
.a8
    sta f:CIO_STATUS
    plp
    rep #$30
.a16
    pla
.elseif CASE = 3
    rep #$30
.a16
.i16
    pea done
    tsc
    sta f:RESULT+6
    cop $00
.elseif CASE = 4
    rep #$30
.a16
.i16
    lda #$abcd
    ldx #$1234
    ldy #$5678
    cop SIGNATURE
.endif
    jmp capture
.endif

; Snapshot full native registers before changing them, including hidden B.
; Result: A/X/Y/S/D words, DBR/P/E bytes at offsets 0/2/4/6/8/10/11/12.
capture:
    php
    rep #$30
.a16
.i16
    sta f:RESULT
    txa
    sta f:RESULT+2
    tya
    sta f:RESULT+4
    tsc
    inc a                         ; account for PHP
    sta f:RESULT+6
    tdc
    sta f:RESULT+8
    phb
    sep #$20
.a8
    pla
    sta f:RESULT+10
    pla
    sta f:RESULT+11
    ; Observe old E in carry. Register snapshot is already complete.
    clc
    xce
    lda #0
    rol a
    sta f:RESULT+12
    sei
    cld
    lda #0
    sta f:NMIEN
    lda f:$14
    sta f:CLOCK_AFTER
    rep #$30
.a16
.i16
    lda #0
    tcd
    phk
    plb
    lda OLD_VBI
    sta VVBLKI
    lda OLD_COP0
    sta VCOP0
    lda OLD_COPU
    sta VCOPU
    sep #$20
.a8
    lda OLD_COP0+2
    sta VCOP0+2
    lda OLD_COPU+2
    sta VCOPU+2
    lda #$ff
    sta COMPLETION
done:
    ; Host breakpoint stops here. No ROM return is attempted by this XEX.
    bra done

; Called by the real ROM after its native -> emulation transition. Observe
; the domain, then either chain to the OS VBI or stop before an unsafe unwind.
.a8
.i8
vbi_hook:
    pha
    php
    phx
    phy
    clc
    xce
    rep #$30
.a16
.i16
    lda #0
    rol a                         ; carry was old E
    sep #$20
.a8
    sta f:OS_E
    rep #$20
.a16
    tsc
    sta f:OS_S
    tdc
    sta f:OS_D
    phb
    sep #$20
.a8
    pla
    sta f:OS_DBR
    lda f:VBI_COUNT
    inc a
    sta f:VBI_COUNT
.if CASE = 1
    lda #$ff
    sta f:COMPLETION
    jmp done
.else
    sep #$30
.i8
    sec
    xce
    ply
    plx
    plp
    pla
    jmp (OLD_VBI)
.endif

; Harmless callees test the untouched ROM's routing, avoiding execution of
; the real COP0 service with a signature that the ROM misroutes.
.a16
.i16
route_zero:
    pha
    lda #$0001
    sta f:ROUTE
    pla
    rtl
route_user:
    pha
    lda #$0002
    sta f:ROUTE
    pla
    rtl

message:
    .byte $7d, "EXEC816 OS BOUNDARY OK", $9b
message_end:
