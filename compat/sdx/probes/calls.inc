; Synthetic audited SDX records. Export operand sites for the host packager.
call_index .set 0
reloc_index .set 0
.macro sdx_call symbol
    .byte $20
    .export .ident(.sprintf("import_%s_%u", .string(symbol), call_index))
.ident(.sprintf("import_%s_%u", .string(symbol), call_index)):
    .word 0
call_index .set call_index+1
.endmacro
.macro near_word symbol
    .export .ident(.sprintf("reloc_%u", reloc_index))
.ident(.sprintf("reloc_%u", reloc_index)):
    .word symbol
reloc_index .set reloc_index+1
.endmacro
