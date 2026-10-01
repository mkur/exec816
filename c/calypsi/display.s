              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"

              .extern ExecDisplayEntries
              .section farcode,text
              .public _DisplayCall
; simple_call: table offset in A16, packet pointer in 4..7,S.
; Native calls require an even entry S, unlike arbitrary C frames. Save the
; original S on the aligned stack so a blocking DOS call retains no shared
; scratch state. Action! and the kernel preserve Calypsi's lower DP registers.
_DisplayCall:
              tax
              tsc
              tay
              and ##0xfffe
              tcs
              phy
              tsc
              sec
              sbc ##7
              tcs
              lda ##0
              sta 1,s
              sep #0x20
              sta 7,s
              rep #0x20
; Copy a full C address and kind; native wrappers validate before narrowing.
              lda 4,y
              sta dp:0x80
              lda 6,y
              sta dp:0x82
              ldy ##0
              lda [0x80],y
              sta 1,s
              iny
              iny
              lda [0x80],y
              sta 3,s
              iny
              iny
              lda [0x80],y
              sta 5,s
display_ready:
              jsl display_dispatch
; Both native pointer and LONG results are already in Calypsi's A/X pair.
              tay
              tsc
              clc
              adc ##7
              tcs
              pla
              tcs
              tya
              rtl

; A synthesized RTL reaches an upper-bank native entry without a fixed
; bank-zero vector. Its normal RTL returns to the JSL continuation above.
display_dispatch:
              sep #0x20
              lda long:ExecDisplayEntries+2,x
              pha
              rep #0x20
              lda long:ExecDisplayEntries,x
              dec a
              pha
              rtl
