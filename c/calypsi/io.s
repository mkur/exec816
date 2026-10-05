              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
              .extern ExecIOEntry
              .section farcode,text
              .public _IOCall
; Operation in A16, pointer to four ULONGs at 4..7,S. Each blocking call
; retains its own aligned native argument area and original C stack pointer.
_IOCall:
              tax
              tsc
              tay
              and ##0xfffe
              tcs
              phy
              tsc
              sec
              sbc ##21
              tcs
              txa
              sta 1,s
              lda ##0
              sta 3,s
              sep #0x20
              sta 21,s
              rep #0x20
              lda 4,y
              sta dp:0x80
              lda 6,y
              sta dp:0x82
              ldy ##0
              lda [0x80],y
              sta 5,s
              iny
              iny
              lda [0x80],y
              sta 7,s
              iny
              iny
              lda [0x80],y
              sta 9,s
              iny
              iny
              lda [0x80],y
              sta 11,s
              iny
              iny
              lda [0x80],y
              sta 13,s
              iny
              iny
              lda [0x80],y
              sta 15,s
              iny
              iny
              lda [0x80],y
              sta 17,s
              iny
              iny
              lda [0x80],y
              sta 19,s
              jsl io_dispatch
              tay
              tsc
              clc
              adc ##21
              tcs
              pla
              tcs
              tya
              rtl
io_dispatch:
              sep #0x20
              lda long:ExecIOEntry+2
              pha
              rep #0x20
              lda long:ExecIOEntry
              dec a
              pha
              rtl
