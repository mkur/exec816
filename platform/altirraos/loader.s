; Fixed-image XEX bootstrap. INITAD executes in emulation mode on the host's
; live stack. No direct-page scratch, native mode transition or Exec service.
.setcpu "65816"
.macpack longbranch
.include "memory.inc"
.include "boot-config.inc"
.include "loader-image.inc"
.segment "LOADER"
.a8
.i8
.export loader_start, loader_init, loader_done, loader_error, loader_copy
.export loader_initialized, expected_manifest
.export loader_return, loader_payload_begin
.export loader_of_begin, loader_progress_add, loader_progress_finish
.export loader_progress_bytes, loader_progress_stage

.macro increment operand
    .local done
    inc a:operand+1
    bne done
    inc a:operand+2
    bne done
    inc a:operand+3
done:
.endmacro

; First XEX segment address is also the safe default RUNAD address.
loader_start:
    lda loader_error
    bne load_failed
    lda loader_initialized
    cmp #1
    bne incomplete
    lda M_NEXT
    cmp #<IMAGE_EXTENTS
    bne incomplete
    lda M_NEXT+1
    cmp #>IMAGE_EXTENTS
    bne incomplete
    lda M_OFFSET
    ora M_OFFSET+1
    bne incomplete
    lda lz4_active
    bne incomplete
    lda #1
    sta M_ENTERED
    jsr loader_progress_finish
    jmp HOST_START
incomplete:
    lda #M_BOOT_ERROR_INCOMPLETE
    sta loader_error
    ldx loader_initialized
    beq load_failed
    sta M_ERROR
load_failed:
    jsr progress_failed
loader_done:
    jmp loader_done                 ; retain the OS's working E=1 environment

loader_error:       .byte 0          ; always initialized by the first segment
loader_initialized: .byte 0

loader_init:
    php
    pha
    phx
    phy
    phb
    cld
    phk
    plb
    lda loader_error
    bne return_host
    lda loader_initialized
    bne consume
    jsr setup
    lda loader_error
    bne return_host
consume:
    inc M_CALLS
    bne :+
    inc M_CALLS+1
:
    lda M_STAGE+M_RECORD_COUNT
    ora M_STAGE+M_RECORD_COUNT+1
    beq return_host
    jsr progress_exec_begin
    jsr copy_record
return_host:
loader_return:
    lda loader_error
    beq :+
    jsr progress_failed
:
    plb
    ply
    plx
    pla
    plp
    rts

setup:
    ; The bootstrap/manifest region is safe by the cold-launch profile. Check
    ; host bounds before touching the separately reserved table and work area.
    lda $02e8
    cmp #>M_MEMLO_LIMIT
    bcc memlo_ok
    jne bounds_error
    lda $02e7
    cmp #<M_MEMLO_LIMIT
    bcc memlo_ok
    jne bounds_error
memlo_ok:
    lda $02e6
    cmp #>M_MEMTOP_REQUIRED
    jcc bounds_error
    bne bounds_ok
    lda $02e5
    cmp #<M_MEMTOP_REQUIRED
    jcc bounds_error
bounds_ok:
    ldx #0
    lda #0
clear_boot:
    sta M_READY,x
    inx
    bne clear_boot
    lda #<B_MAGIC
    sta B_ADDRESS+B_FIELD_MAGIC
    lda #>B_MAGIC
    sta B_ADDRESS+B_FIELD_MAGIC+1
    lda #B_VERSION
    sta B_ADDRESS+B_FIELD_VERSION
    lda #B_SIZE
    sta B_ADDRESS+B_FIELD_SIZE
    lda #<B_DEFAULT_BLOCKS
    sta B_ADDRESS+B_FIELD_CACHE_BLOCKS
    lda #>B_DEFAULT_BLOCKS
    sta B_ADDRESS+B_FIELD_CACHE_BLOCKS+1
    lda #B_DEFAULT_DRIVE
    sta B_ADDRESS+B_FIELD_SYSTEM_DRIVE
    lda $02e7
    sta M_OLD_MEMLO
    lda $02e8
    sta M_OLD_MEMLO+1
    ; Exact comparison against the manifest compiled into this bootstrap is the
    ; runtime preflight for this fixed linked image. The host validator proved
    ; all ranges/claims against the generated map before either was emitted.
    lda #<IMAGE_MANIFEST_SIZE
    sta M_LEFT
    lda #>IMAGE_MANIFEST_SIZE
    sta M_LEFT+1
manifest_compare:
manifest_read:
    lda f:M_MANIFEST
manifest_expected:
    cmp f:expected_manifest
    bne manifest_error
    increment manifest_read
    increment manifest_expected
    jsr decrement_left
    bne manifest_compare
    ; No table write occurs until the entire manifest has matched.
    lda #<M_TABLE_BYTES
    sta M_LEFT
    lda #>M_TABLE_BYTES
    sta M_LEFT+1
seed_loop:
seed_read:
    lda f:expected_manifest+M_HEADER_BYTES
seed_write:
    sta f:M_TABLE
    increment seed_read
    increment seed_write
    jsr decrement_left
    bne seed_loop
    ldx #15
copy_identity:
    lda expected_manifest+M_HEADER_IDENTITY,x
    sta M_ID,x
    dex
    bpl copy_identity
    lda #<M_MEMTOP_REQUIRED
    sta $02e7
    lda #>M_MEMTOP_REQUIRED
    sta $02e8
    lda #1
    sta M_READY
    sta loader_initialized
    ldx #<boot_banner
    ldy #>boot_banner
    jsr progress_text
    rts
bounds_error:
    lda #M_BOOT_ERROR_BOUNDS
    sta loader_error
    rts
manifest_error:
    lda #M_BOOT_ERROR_MANIFEST
    sta loader_error
    sta M_ERROR
    rts

decrement_left:
    lda M_LEFT
    bne :+
    dec M_LEFT+1
:
    dec M_LEFT
    lda M_LEFT
    ora M_LEFT+1
    rts

bad_record:
    lda #M_BOOT_ERROR_RECORD
    sta loader_error
    sta M_ERROR
    rts

copy_record:
loader_payload_begin:
    ; Admit the record/descriptor before writes. Malformed compressed input
    ; may leave partial output inside its admitted block, but cannot enter Exec.
    lda M_NEXT+1
    jne bad_record
    lda M_NEXT
    cmp #IMAGE_EXTENTS
    jcs bad_record
    cmp M_STAGE
    jne bad_record
    lda M_STAGE+M_RECORD_EXTENT+1
    jne bad_record
    lda M_STAGE+M_RECORD_ENCODING
    cmp #M_ENCODING_LZ4_CONTINUE+1
    jcs bad_record
    lda M_OFFSET
    cmp M_STAGE+M_RECORD_OFFSET
    jne bad_record
    lda M_OFFSET+1
    cmp M_STAGE+M_RECORD_OFFSET+1
    jne bad_record
    lda M_STAGE+M_RECORD_COUNT+1
    cmp #>M_CHUNK
    bcc count_ok
    jne bad_record
    lda M_STAGE+M_RECORD_COUNT
    cmp #<M_CHUNK
    beq count_ok
    jcs bad_record
count_ok:
    ; Descriptor pointer = compiled descriptors + 8*index (16-bit arithmetic).
    lda #0
    sta M_WORK+1
    lda M_NEXT
    asl a
    rol M_WORK+1
    asl a
    rol M_WORK+1
    asl a
    rol M_WORK+1
    clc
    adc #<(expected_manifest+M_HEADER_BYTES+M_TABLE_BYTES)
    sta descriptor_read+1
    lda M_WORK+1
    adc #>(expected_manifest+M_HEADER_BYTES+M_TABLE_BYTES)
    sta descriptor_read+2
    ldx #3
    jsr descriptor
    cmp M_STAGE+M_RECORD_KIND
    jne bad_record
.if LOADER_PROBE
    lda $14
    sta M_WORK+8
wait_tick:
    wai
    lda $14
    cmp M_WORK+8
    beq wait_tick
    inc M_WORK+9
.endif
    lda M_STAGE+M_RECORD_ENCODING
    jne lz4_record
    lda lz4_active
    jne bad_record
    clc
    lda M_OFFSET
    adc M_STAGE+M_RECORD_COUNT
    sta M_WORK+2
    lda M_OFFSET+1
    adc M_STAGE+M_RECORD_COUNT+1
    sta M_WORK+3
    jcs record_error
    ldx #5
    jsr descriptor
    cmp M_WORK+3
    jcc record_error
    bne end_ok
    dex
    jsr descriptor
    cmp M_WORK+2
    jcc record_error
end_ok:
    jsr prepare_destination
    lda M_STAGE+M_RECORD_COUNT
    sta M_LEFT
    lda M_STAGE+M_RECORD_COUNT+1
    sta M_LEFT+1
loader_copy:
    lda M_STAGE+M_RECORD_KIND
    cmp #1
    beq zero_byte
source:
    lda f:M_PAYLOAD
    bra store_byte
zero_byte:
    lda #0
store_byte:
destination:
    sta f:$000000
    increment source
    increment destination
    jsr decrement_left
    bne loader_copy
record_committed:
    lda M_WORK+2
    sta M_OFFSET
    lda M_WORK+3
    sta M_OFFSET+1
    ldx #4
    jsr descriptor
    cmp M_OFFSET
    bne consumed
    inx
    jsr descriptor
    cmp M_OFFSET+1
    bne consumed
    stz M_OFFSET
    stz M_OFFSET+1
    inc M_NEXT
consumed:
    lda M_STAGE+M_RECORD_ENCODING
    beq @raw
    lda lz4_output_size
    ldx lz4_output_size+1
    bra @progress
@raw:
    lda M_STAGE+M_RECORD_COUNT
    ldx M_STAGE+M_RECORD_COUNT+1
@progress:
    jsr loader_progress_add
record_pending:
    stz M_STAGE+M_RECORD_COUNT
    stz M_STAGE+M_RECORD_COUNT+1
    rts
record_error:
    jmp bad_record
descriptor:
descriptor_read:
    lda f:$000000,x
    rts

prepare_destination:
    ldx #0
    jsr descriptor
    clc
    adc M_OFFSET
    sta destination+1
    inx
    jsr descriptor
    adc M_OFFSET+1
    sta destination+2
    inx
    jsr descriptor
    adc #0
    sta destination+3
    lda #<M_PAYLOAD
    sta source+1
    lda #>M_PAYLOAD
    sta source+2
    rts

.include "lz4.s"

; Boot-only E: output. Each public callback preserves the host context; the
; character helper also preserves hidden B, D and the whole borrowed IOCB0.
.macro progress_save
    php
    pha
    phx
    phy
    phb
    cld
    phk
    plb
.endmacro
.macro progress_return
    plb
    ply
    plx
    pla
    plp
    rts
.endmacro

loader_of_begin:
    progress_save
    lda loader_error
    bne @done
    lda #1
    sta loader_progress_stage
    ldx #<of_message
    ldy #>of_message
    jsr progress_text
@done:
    progress_return

progress_exec_begin:
    lda loader_progress_stage
    bne @done
    lda #2
    sta loader_progress_stage
    ldx #<exec_message
    ldy #>exec_message
    jsr progress_text
@done:
    rts

; A/X contain the low/high byte count, at most one 32 KiB output block.
loader_progress_add:
    progress_save
    clc
    adc loader_progress_bytes
    sta loader_progress_bytes
    txa
    adc loader_progress_bytes+1
    sta loader_progress_bytes+1
@dots:
    cmp #$40
    bcc @done
    sbc #$40
    sta loader_progress_bytes+1
    lda #'.'
    jsr progress_putchar
    lda loader_progress_bytes+1
    bra @dots
@done:
    progress_return

loader_progress_finish:
    progress_save
    lda loader_progress_stage
    beq @done
    lda loader_progress_bytes
    ora loader_progress_bytes+1
    beq @newline
    lda #'.'
    jsr progress_putchar
@newline:
    lda #$9b
    jsr progress_putchar
    stz loader_progress_stage
    stz loader_progress_bytes
    stz loader_progress_bytes+1
@done:
    progress_return

progress_failed:
    lda progress_error_printed
    bne @done
    inc progress_error_printed
    lda #$9b
    jsr progress_putchar
    ldx #<failure_message
    ldy #>failure_message
    jsr progress_text
@done:
    rts

progress_text:
    stx @read+1
    sty @read+2
@read:
    lda a:$ffff
    beq @done
    jsr progress_putchar
    inc @read+1
    bne @read
    inc @read+2
    bra @read
@done:
    rts

progress_putchar:
    sta f:progress_character
    php
    pha
    xba
    pha
    phx
    phy
    phb
    phd
    cld
    phk
    plb
    lda #0
    xba
    lda #0
    tcd
    ldx #0
@save:
    lda $0340,x
    pha
    inx
    cpx #16
    bne @save
    lda #11
    sta $0342
    lda #<progress_character
    sta $0344
    lda #>progress_character
    sta $0345
    lda #1
    sta $0348
    lda #0
    sta $0349
    ldx #0
    jsr $e456
    ; Output status has no effect on image validation or the boot record.
    ldx #15
@restore:
    pla
    sta $0340,x
    dex
    bpl @restore
    pld
    plb
    ply
    plx
    pla
    xba
    pla
    plp
    rts

boot_banner: .byte "Exec816 boot",$9b,0
of_message: .byte "Loading OF816 ",0
exec_message: .byte "Loading Exec816 ",0
failure_message: .byte "Exec816 load failed",$9b,0
loader_progress_bytes: .word 0
loader_progress_stage: .byte 0
progress_character: .byte 0
progress_error_printed: .byte 0

expected_manifest:
    .incbin "manifest.bin"
