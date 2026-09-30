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
    bne loader_done
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
    lda #1
    sta M_ENTERED
    jmp HOST_START
incomplete:
    lda #M_BOOT_ERROR_INCOMPLETE
    sta loader_error
    ldx loader_initialized
    beq loader_done
    sta M_ERROR
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
    jsr copy_record
return_host:
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
    ; All checks precede writes, including checks of index, offset and end.
    lda M_NEXT+1
    jne bad_record
    lda M_NEXT
    cmp #IMAGE_EXTENTS
    jcs bad_record
    cmp M_STAGE
    jne bad_record
    lda M_STAGE+M_RECORD_EXTENT+1
    ora M_STAGE+M_RECORD_RESERVED
    jne bad_record
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
    lda M_STAGE+M_RECORD_COUNT
    sta M_LEFT
    lda M_STAGE+M_RECORD_COUNT+1
    sta M_LEFT+1
.if LOADER_PROBE
    ; Qualification only: a real VBI while this callback owns a live OS stack.
    lda $14
    sta M_WORK+8
wait_tick:
    wai
    lda $14
    cmp M_WORK+8
    beq wait_tick
    inc M_WORK+9
.endif
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
    stz M_STAGE+M_RECORD_COUNT
    stz M_STAGE+M_RECORD_COUNT+1
    rts
record_error:
    jmp bad_record
descriptor:
descriptor_read:
    lda f:$000000,x
    rts

expected_manifest:
    .incbin "manifest.bin"
