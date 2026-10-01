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
