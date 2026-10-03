              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
              .section farcode,text
              .public _VbxeMap, VbxeMapDisabled, VbxeMapBank, VbxeMapControl, VbxeMapCommitted
; simple_call A/X = huge pointer to four upper-RAM shadow bytes. No stack/DP
; switch, no shared scratch, no interrupt masking. Every asynchronous user is
; forbidden from touching MEMAC/the aperture/the pending or committed shadow.
_VbxeMap:
              sta dp:0x80
              stx dp:0x82
              php
              sep #0x20
              lda #0
              sta long:0xd65e
VbxeMapDisabled:
              ldy ##0
              lda [0x80],y
              sta long:0xd65f
VbxeMapBank:
              iny
              lda [0x80],y
              sta long:0xd65e
VbxeMapControl:
              ldy ##0
              rep #0x20
              lda [0x80],y
              iny
              iny
              sta [0x80],y
VbxeMapCommitted:
              plp
              rtl

; Private checked-list upload. simple_call A/X points to a six-byte packet:
; huge source pointer, then UWORD count (1..64). Indexed-long reads carry across
; CPU bank boundaries. The destination is the already mapped 4 KiB arena.
; Patch only the chain bit. No second buffer, DP reservation or IRQ masking.
              .public _VbxeUpload
_VbxeUpload:
              php
              rep #0x30
              sta dp:0x80
              stx dp:0x82
              ldy ##4
              lda [0x80],y
              sta dp:0x84
              ldy ##2
              lda [0x80],y
              pha
              ldy ##0
              lda [0x80],y
              sta dp:0x80
              pla
              sta dp:0x82
              ldx ##0
_upload_record:
              lda ##10
              sta dp:0x86
_upload_words:
              lda [0x80],y
              sta long:0x8000,x
              iny
              iny
              inx
              inx
              dec dp:0x86
              bne _upload_words
              dec dp:0x84
              sep #0x20
              lda [0x80],y
              pha
              lda dp:0x84
              beq _upload_last
              pla
              ora #8
              bra _upload_mode
_upload_last:
              pla
_upload_mode:
              sta long:0x8000,x
              iny
              inx
              rep #0x20
              lda dp:0x84
              bne _upload_record
              plp
              rtl
