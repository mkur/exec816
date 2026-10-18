.setcpu "6502"
.include "calls.inc"
.segment "CODE"
.export MAIN, patch_irq, dp_arg_digest, dp_arg_pointer
.macro import_word symbol, addend
    .export .ident(.sprintf("import_%s_%u", .string(symbol), call_index))
.ident(.sprintf("import_%s_%u", .string(symbol), call_index)):
    .word addend
call_index .set call_index+1
.endmacro
.macro load_pointer symbol
    .byte $ad
    near_word symbol
    .byte $ae
    near_word symbol+1
.endmacro
MAIN:
patch_irq:
    sei
    lda #$ab
    .byte $eb                   ; admitted XBA: seed hidden B for service checks
    lda #'q'
    ldx #$5a
    ldy #$a6
    sdx_call TOUPPER
    sta $0500
    stx $0501
    sty $0502
    php
    pla
    sta $0503
    load_pointer option_pointer
    ldy #4
    sdx_call U_SLASH
    sta $0504
    .byte $ad
    near_word options
    sta $0505
    .byte $ad
    near_word options+2
    sta $0506
    lda #$a0
    sdx_call U_GETATR
    .byte $ad
    import_word COMTAB,$1a
    sta $0507
    ; Read FILE_P through its imported address, proving variable indirection.
    .byte $ad
    import_word FILE_P,0
    sta $0524
    .byte $ad
    import_word FILE_P,1
    sta $0525
    lda #4
    sta $0778
    sdx_call FOPEN
    lda $0760
    sta $0508
    lda #$a0
    sdx_call U_GETATR
    sdx_call FOPEN
    lda $0760
    sta $0509
    load_pointer handles_full_pointer
    sdx_call U_SFAIL
    sdx_call FOPEN              ; a third simultaneous handle must fail
    lda #$ee
    sta $0527
    rts
handles_full:
    sta $0528
    lda $0508
    sta $0760
    ldy #$a6
    sdx_call FGETC
    sta $050a
    stx $050b
    sty $0526
    lda $0509
    sta $0760
    lda #0
    sta $0782
    sta $0786
    sta $0787
    lda #$38
    sta $0783
    lda #6
    sta $0785
    sdx_call FREAD
    stx $050c
    php
    pla
    sta $050d
    lda $0785
    sta $050e
    sdx_call FGETC
    sta $051c
    stx $051d
    sdx_call FCLOSE
    load_pointer outer_pointer
    sdx_call U_SFAIL
    load_pointer inner_pointer
    sdx_call U_SFAIL
    .byte $20
    near_word deeper
    lda #$ee                    ; a nonlocal trap must skip this continuation
    sta $050f
    rts
deeper:
    pha
    pha
    lda #170
    sdx_call U_FAIL
    lda #$ee
    sta $050f
    rts
inner:
    sta $0510
    php
    pla
    sta $051e
    lda $0508
    sta $0760
    sdx_call FGETC               ; the first file survives a caught error
    sta $0511
    stx $051f
    php
    pla
    sta $0520
    lda #$35
    ldx #$5a
    ldy #$a6
    sec
    sdx_call U_XFAIL
    sta $0512
    stx $0513
    sty $0514
    php
    pla
    sta $0515
    sdx_call FCLOSEAL
    ldy #10
install_traps:
    load_pointer traps_full_pointer
    sdx_call U_SFAIL
    dey
    bne install_traps
    sdx_call U_SFAIL            ; the eleventh install delivers to the tenth
    lda #$ee
    sta $0529
    rts
traps_full:
    sta $052a
    ldy #9
remove_traps:
    sdx_call U_XFAIL
    dey
    bne remove_traps
    lda #5
    sta $80
    lda #0
    sta $81
    sta $82
    lda #7
    sta a:$0080                 ; poison the upper-bank low-page alias
    load_pointer text_pointer
    sta $90
    stx $91
    .align 256,$ea
    .res 244,$ea
    lda #$35
    ldx #$5a
    ldy #$a6
    sdx_call PRINTF
    .byte "MD5 %02x %s %p %d %%",$9b,0
dp_arg_digest:
    .word $80
    near_word text_ok
dp_arg_pointer:
    .word $90
    near_word value_word
    sta $0516
    stx $0517
    sty $0518
    .byte $eb
    sta $0519
    .byte $eb
    lda #0
    rts
outer:
    lda #$ee
    sta $051a
    rts
option_pointer:
    near_word options
outer_pointer:
    near_word outer
inner_pointer:
    near_word inner
handles_full_pointer:
    near_word handles_full
traps_full_pointer:
    near_word traps_full
text_pointer:
    near_word text_done
options:
    .byte 0,'C',0,'X'
text_ok:
    .byte "ok",0
text_done:
    .byte "DONE",$9b
value_word:
    .word 258
