              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
              .extern ExecAESLocalEntry
              .section farcode,text
              .public _AESLocalCall
; simple_call: huge request pointer in A/X. Native LONGCARD argument and
; alignment stay on this Task's stack across ordinary VBI preemption.
_AESLocalCall:
              sta dp:0x80
              stx dp:0x82
              tsc
              tay
              and ##0xfffe
              tcs
              phy
              tsc
              sec
              sbc ##5
              tcs
              lda dp:0x80
              sta 1,s
              lda dp:0x82
              sta 3,s
              sep #0x20
              lda #0
              sta 5,s
              rep #0x20
              jsl aes_local_dispatch
              tay
              tsc
              clc
              adc ##5
              tcs
              pla
              tcs
              tya
              rtl
aes_local_dispatch:
              sep #0x20
              lda long:ExecAESLocalEntry+2
              pha
              rep #0x20
              lda long:ExecAESLocalEntry
              dec a
              pha
              rtl
