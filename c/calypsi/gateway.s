              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"

#include "gateway.inc"

; simple_call: selector in A16, pointer in 4..7,S. Packets are on the
; caller's stack in bank zero. COP preserves the lower DP workspace and D/DBR.
              .section farcode,text
              .public _ExecPacket
_ExecPacket:
              pha
              lda 6,s
              tax
              ldy ##EXEC_PROFILE_TAG
              pla
              cop #EXEC_COP
              rtl

; Direct-pointer services use X=low16, Y=profile tag | bank8.
              .section farcode,text
              .public _ExecPointer
_ExecPointer:
              pha
              lda 6,s
              tax
              lda 8,s
              and ##255
              ora ##EXEC_PROFILE_TAG
              tay
              pla
              cop #EXEC_COP
              rtl
