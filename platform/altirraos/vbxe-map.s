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

; Checked opaque even-X 8x8 text. The C driver validates the complete atlas,
; source string and destination before mapping. Generate one fill followed by
; 1..32 glyphs directly in the arena. All fixed fields are written every time;
; arbitrary glyph bytes cannot change stride, mode, chaining or raster bounds.
; No shared scratch: $80-$99 are the caller's ABI call-clobbered DP workspace.
; Native interrupts preserve D and never access this mapping or command arena.
              .public _VbxeTextUpload
_VbxeTextUpload:
              php
              rep #0x30
              sta dp:0x80
              stx dp:0x82
              ldy ##0
              lda [0x80],y
              sta dp:0x84
              iny
              iny
              lda [0x80],y
              sta dp:0x86
              iny
              iny
              lda [0x80],y
              sta dp:0x88
              iny
              iny
              lda [0x80],y
              sta dp:0x8a
              iny
              iny
              lda [0x80],y
              sta dp:0x8c
              iny
              iny
              lda [0x80],y
              sta dp:0x8e
              iny
              iny
              lda [0x80],y
              sta dp:0x90
              iny
              iny
              lda [0x80],y
              sta dp:0x92
              and ##0x00ff
              beq _text_zero_ink
              xba
              ora ##7
              sta dp:0x94
              lda ##0
              sta dp:0x96
              lda ##6
              bra _text_mode
_text_zero_ink:
              lda ##0xff07
              sta dp:0x94
              lda ##255
              sta dp:0x96
              lda ##4
_text_mode:
              sta dp:0x98
; Leading background fill. Source address zero is valid with AND mask zero.
              lda ##0
              sta long:0x8000
              sta long:0x8002
              sta long:0x8012
              lda ##0x0100
              sta long:0x8004
              lda dp:0x8c
              sta long:0x8006
              lda dp:0x8e
              ora ##0x4000
              sta long:0x8008
              lda ##0x0101
              sta long:0x800a
              lda dp:0x90
              asl a
              asl a
              dec a
              sta long:0x800c
              lda ##7
              sta long:0x800e
              lda dp:0x92
              xba
              and ##0x00ff
              sta long:0x8010
              sep #0x20
              lda #8
              sta long:0x8014
              rep #0x20
              ldx ##21
              ldy ##0
_text_record:
              sep #0x20
              lda [0x84],y
              rep #0x20
              and ##0x00ff
              asl a
              asl a
              clc
              adc dp:0x88
              sta long:0x8000,x
              lda dp:0x8a
              adc ##0
              sta long:0x8002,x
              lda ##0x0104
              sta long:0x8004,x
              lda dp:0x8c
              sta long:0x8006,x
              lda dp:0x8e
              ora ##0x4000
              sta long:0x8008,x
              lda ##0x0101
              sta long:0x800a,x
              lda ##3
              sta long:0x800c,x
              lda dp:0x94
              sta long:0x800e,x
              lda dp:0x96
              sta long:0x8010,x
              lda ##0
              sta long:0x8012,x
              dec dp:0x90
              beq _text_last
              sep #0x20
              lda dp:0x98
              ora #8
              sta long:0x8014,x
              rep #0x20
              lda dp:0x8c
              clc
              adc ##4
              sta dp:0x8c
              lda dp:0x8e
              adc ##0
              sta dp:0x8e
              txa
              clc
              adc ##21
              tax
              iny
              brl _text_record
_text_last:
              sep #0x20
              lda dp:0x98
              sta long:0x8014,x
              plp
              rtl
