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
              ldy ##4
              lda [0x80],y
              tax
              sep #0x20
              lda #0
              sta long:0xd65e,x
VbxeMapDisabled:
              ldy ##0
              lda [0x80],y
              sta long:0xd65f,x
VbxeMapBank:
              iny
              lda [0x80],y
              sta long:0xd65e,x
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

; Checked opaque 8x8 text at either X parity. The C driver validates the complete atlas,
; source string and destination before mapping. Generate background records and
; 1..80 glyphs and an optional final fill directly in the arena.
; All fixed fields are written every time;
; arbitrary glyph bytes cannot change stride, mode, chaining or raster bounds.
; No shared scratch: $80-$a9 are the caller's ABI call-clobbered DP workspace.
; Odd background helpers add three stack bytes while called; P is saved once.
; Native interrupts preserve D and never access this mapping or command arena.
              .public _VbxeTextUpload
_VbxeTextUpload:
              php
              rep #0x30
              sta dp:0x80
              stx dp:0x82
              ldy ##26
              lda [0x80],y
              xba
              pha
              and ##0xff00
              sta dp:0xa6
              pla
              and ##0x00ff
              ora ##0x0100
              sta dp:0xa8
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
              ldy ##25
              sep #0x20
              lda [0x80],y
              rep #0x20
              and ##255
              beq _text_even
              brl _text_odd
_text_even:
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
              ora dp:0xa6
              sta long:0x8008
              lda dp:0xa8
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
              ora dp:0xa6
              sta long:0x8008,x
              lda dp:0xa8
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
              ldy ##22
              lda [0x80],y
              bne _text_fill
              sep #0x20
              lda dp:0x98
              sta long:0x8014,x
              plp
              rtl
; The C driver validates the complete trailing fill before drawing any text.
; Append it to this list, replacing the last glyph's chain terminator.
_text_fill:
              dec a
              sta dp:0x90
              sep #0x20
              lda dp:0x98
              ora #8
              sta long:0x8014,x
              rep #0x20
              txa
              clc
              adc ##21
              tax
              lda ##0
              sta long:0x8000,x
              sta long:0x8002,x
              sta long:0x8012,x
              lda ##0x0100
              sta long:0x8004,x
              ldy ##16
              lda [0x80],y
              sta long:0x8006,x
              iny
              iny
              lda [0x80],y
              ora dp:0xa6
              sta long:0x8008,x
              lda dp:0xa8
              sta long:0x800a,x
              ldy ##20
              lda [0x80],y
              dec a
              sta long:0x800c,x
              lda dp:0x90
              sta long:0x800e,x
              lda ##0
              sta long:0x8010,x
              sep #0x20
              ldy ##24
              lda [0x80],y
              sta long:0x8010,x
              lda #0
              sta long:0x8014,x
              plp
              rtl

; Shifted atlas: five source bytes per glyph, stride 1280; destination cells
; still advance four bytes. Clear only the run's pixels before painting ink.
_text_odd:
              lda dp:0x8c
              clc
              adc ##1
              sta dp:0x9a
              lda dp:0x8e
              adc ##0
              sta dp:0x9c
              lda dp:0x90
              asl a
              asl a
              dec a
              dec a
              sta dp:0x9e
              lda ##7
              sta dp:0xa0
              lda dp:0x92
              xba
              and ##255
              sta dp:0xa2
              lda ##8
              sta dp:0xa4
              ldx ##0
              jsl _text_background
; Left edge: keep the high nibble; clear and colour the low nibble.
              lda dp:0x8c
              sta dp:0x9a
              lda dp:0x8e
              sta dp:0x9c
              stz dp:0x9e
              lda ##0xf0
              sta dp:0xa2
              lda ##12
              sta dp:0xa4
              jsl _text_background
              lda dp:0x92
              xba
              and ##15
              sta dp:0xa2
              lda ##11
              sta dp:0xa4
              jsl _text_background
; Right edge: keep the low nibble; clear and colour the high nibble.
              lda dp:0x90
              asl a
              asl a
              clc
              adc dp:0x8c
              sta dp:0x9a
              lda dp:0x8e
              adc ##0
              sta dp:0x9c
              lda ##15
              sta dp:0xa2
              lda ##12
              sta dp:0xa4
              jsl _text_background
              lda dp:0x92
              xba
              and ##0xf0
              sta dp:0xa2
              lda ##11
              sta dp:0xa4
              jsl _text_background
              ldy ##0
_text_odd_record:
              sep #0x20
              lda [0x84],y
              rep #0x20
              and ##0x00ff
              sta dp:0x9a
              asl a
              asl a
              clc
              adc dp:0x9a
              clc
              adc dp:0x88
              sta long:0x8000,x
              lda dp:0x8a
              adc ##0
              sta long:0x8002,x
              lda ##0x0105
              sta long:0x8004,x
              lda dp:0x8c
              sta long:0x8006,x
              lda dp:0x8e
              ora dp:0xa6
              sta long:0x8008,x
              lda dp:0xa8
              sta long:0x800a,x
              lda ##4
              sta long:0x800c,x
              lda dp:0x94
              sta long:0x800e,x
              lda dp:0x96
              sta long:0x8010,x
              lda ##0
              sta long:0x8012,x
              dec dp:0x90
              bne _text_odd_more
              brl _text_last
_text_odd_more:
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
              brl _text_odd_record

; One constant-source chained background record. $9a/$9c destination,
; $9e width minus one, $a0 height/AND, $a2 XOR/collision, $a4 mode.
; All fields are written, including source, unused pattern and collision.
_text_background:
              lda ##0
              sta long:0x8000,x
              sta long:0x8002,x
              sta long:0x8012,x
              lda ##0x0100
              sta long:0x8004,x
              lda dp:0x9a
              sta long:0x8006,x
              lda dp:0x9c
              ora dp:0xa6
              sta long:0x8008,x
              lda dp:0xa8
              sta long:0x800a,x
              lda dp:0x9e
              sta long:0x800c,x
              lda dp:0xa0
              sta long:0x800e,x
              lda dp:0xa2
              sta long:0x8010,x
              sep #0x20
              lda dp:0xa4
              sta long:0x8014,x
              rep #0x20
              txa
              clc
              adc ##21
              tax
              rtl
