; SPDX-License-Identifier: MIT
; A source engine uses one interpreter activation, with an assembly caller.
.include "fastbasic.inc"
.include "source-run.inc"
.import parser_start, parser_resume, parser_alloc_init, interpreter_run, interpreter_resume
.import compiled_var_page, compiled_num_vars, var_page, parser_persistent, runtime_persistent, COMP_DIAG_ERROR, error_msg_list
.import __HEAP_RUN__, __CODE_RUN__, __CODE_SIZE__
.importzp buf_ptr, end_ptr, prog_ptr, reloc_addr, var_count, linenum, bmax
.importzp var_buf, label_buf, laddr_buf, mem_end, array_ptr
.importzp zp_clear_start, zp_clear_end, cptr, tmp2
.export source_entry, source_capability, bytecode_start
.segment "PREHEAD"
.byte "FB65"
.word FB_VERSION, FB_TARGET, FB_LOAD, __CODE_RUN__+__CODE_SIZE__
.word source_entry, FB_LIMIT
.segment "CODE"
source_entry:
    jmp source_begin
source_capability:
    .byte "FBI1"
    .word FBI_VERSION, FBI_CAP_BYTES
.ifdef FASTBASIC_FP
    .word FBI_VARIANT_FLOAT
.else
    .word FBI_VARIANT_INTEGER
.endif
    .word __HEAP_RUN__, linenum, bmax, COMP_DIAG_ERROR, error_msg_list
    .word source_workspace, 0
source_workspace:
    .word var_buf, var_count, label_buf, laddr_buf, mem_end, prog_ptr
    .word array_ptr, var_page
    .byte zp_clear_start, zp_clear_end
    .word cptr, tmp2
source_begin:
    lda #<source_capability
    ldx #>source_capability
    jsr FB_SERVICE_SOURCE
    ; Native admission returns the exclusive normalized source end in AX.
    pha
    txa
    tay
    pla
    jsr parser_alloc_init
    lda #<__HEAP_RUN__
    sta buf_ptr
    lda #>__HEAP_RUN__
    sta buf_ptr+1
    lda #0
    sta reloc_addr
    sta reloc_addr+1
    sta COMP_DIAG_ERROR
    ; Native PREPARE seeds the session's symbol table after the parser's usual
    ; transient state is cleared. One-shot engines still start with no symbols.
    lda #0
    ldx #zp_clear_end-zp_clear_start
source_clear:
    sta zp_clear_start,x
    dex
    bpl source_clear
    lda #FBI_PHASE_PREPARE
    ldx #0
    jsr FB_SERVICE_SOURCE_RESULT
    sta source_resident
    sta parser_persistent
    sta runtime_persistent
    jsr parser_resume
    bcc source_run
    lda #FBI_PHASE_PARSE
    ldx #0
    jsr FB_SERVICE_SOURCE_RESULT
    rts
source_run:
    ; The parser's final END fits its reserved output page. Variables begin
    ; on the following page; parser tables are no longer needed by execution.
    lda prog_ptr+1
    clc
    adc #1
    sta compiled_var_page
    lda var_count
    sta compiled_num_vars
    lda #FBI_PHASE_EXECUTE
    ldx #0
    jsr FB_SERVICE_SOURCE_RESULT
    lda end_ptr
    ldx end_ptr+1
    ldy source_resident
    beq source_once
    jsr interpreter_resume
    jmp source_complete
source_once:
    jsr interpreter_run
source_complete:
    lda #FBI_PHASE_COMPLETE
    ldx #0
    jsr FB_SERVICE_SOURCE_RESULT
    rts
; interpreter.asm exports its usual standalone entry, which is not the engine
; entry. Keep its bytecode reference valid without a BASIC bootstrap frontend.
bytecode_start:
    .byte 0
.segment "BSS"
source_resident: .res 1
.segment "HEAP"
    .res 0
