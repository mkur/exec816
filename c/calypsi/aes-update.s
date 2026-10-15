              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
              .extern ExecAESUpdateEntry
              .section farcode,text
              .public _AESUpdateCall
; simple_call: huge request pointer in A/X. Native LONGCARD argument and
; alignment stay on this Task's stack across ordinary VBI preemption.
_AESUpdateCall:
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
              jsl aes_update_dispatch
              tay
              tsc
              clc
              adc ##5
              tcs
              pla
              tcs
              tya
              rtl
aes_update_dispatch:
              sep #0x20
              lda long:ExecAESUpdateEntry+2
              pha
              rep #0x20
              lda long:ExecAESUpdateEntry
              dec a
              pha
              rtl
