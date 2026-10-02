              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
              .extern ExecInputEntries
              .section farcode,text
              .public _InputCall
; simple_call: table offset in A16, packet pointer in 4..7,S. Preserve the
; original C stack alignment; every native wrapper receives three ULONGs.
_InputCall:
              tax
              tsc
              tay
              and ##0xfffe
              tcs
              phy
              tsc
              sec
              sbc ##13
              tcs
              sep #0x20
              lda #0
              sta 13,s
              rep #0x20
              lda 4,y
              sta dp:0x80
              lda 6,y
              sta dp:0x82
              ldy ##0
              lda [0x80],y
              sta 1,s
              ldy ##2
              lda [0x80],y
              sta 3,s
              ldy ##4
              lda [0x80],y
              sta 5,s
              ldy ##6
              lda [0x80],y
              sta 7,s
              ldy ##8
              lda [0x80],y
              sta 9,s
              ldy ##10
              lda [0x80],y
              sta 11,s
              jsl input_dispatch
              tay
              tsc
              clc
              adc ##13
              tcs
              pla
              tcs
              tya
              rtl
input_dispatch:
              sep #0x20
              lda long:ExecInputEntries+2,x
              pha
              rep #0x20
              lda long:ExecInputEntries,x
              dec a
              pha
              rtl
