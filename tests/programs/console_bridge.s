; Fixture-only native/C register and lower-DP probe. Two real emitted calls
; deliberately put the inner bridge on opposite stack parities.
; The indirect dispatch leaves A=bridge low word-1 and P=0 at actual entry;
; X/Y hold full-width sentinels. Capture these entry values exactly.
              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
              .extern ConsoleProbeNative,ConsoleProbeResults,ConsoleProbeCase
              .section farcode,text
              .public ConsoleBridgeProbe
ConsoleBridgeProbe:
              lda ##0
              sta long:ConsoleProbeCase
              lda ##23040
              sta dp:0
              lda ##23041
              sta dp:2
              lda ##23042
              sta dp:4
              lda ##23043
              sta dp:6
              lda ##23044
              sta dp:8
              lda ##23045
              sta dp:10
              lda ##23046
              sta dp:12
              lda ##23047
              sta dp:14
              lda ##23048
              sta dp:16
              lda ##23049
              sta dp:18
              sep #0x20
              lda #0x0c
              pha
              rep #0x20
              lda ##(.word0 ConsoleProbeClobber)
              pha
              tsc
              sta long:ConsoleProbeResults+32
              tdc
              sta long:ConsoleProbeResults+34
              clc
              clv
              lda ##0x1234
              ldx ##0x5678
              ldy ##0x9abc
              jsl ConsoleProbeDispatch
              php
              sta long:ConsoleProbeResults+0
              txa
              sta long:ConsoleProbeResults+2
              tya
              sta long:ConsoleProbeResults+4
              tsc
              inc a
              sta long:ConsoleProbeResults+6
              tdc
              sta long:ConsoleProbeResults+8
              sep #0x20
              pla
              sta long:ConsoleProbeResults+10
              phb
              pla
              sta long:ConsoleProbeResults+11
              rep #0x20
              lda dp:0
              sta long:ConsoleProbeResults+12
              lda dp:2
              sta long:ConsoleProbeResults+14
              lda dp:4
              sta long:ConsoleProbeResults+16
              lda dp:6
              sta long:ConsoleProbeResults+18
              lda dp:8
              sta long:ConsoleProbeResults+20
              lda dp:10
              sta long:ConsoleProbeResults+22
              lda dp:12
              sta long:ConsoleProbeResults+24
              lda dp:14
              sta long:ConsoleProbeResults+26
              lda dp:16
              sta long:ConsoleProbeResults+28
              lda dp:18
              sta long:ConsoleProbeResults+30
              tsc
              clc
              adc ##3
              tcs
              sep #0x20
              pha
              rep #0x20
              lda ##1
              sta long:ConsoleProbeCase
              lda ##23040
              sta dp:0
              lda ##23041
              sta dp:2
              lda ##23042
              sta dp:4
              lda ##23043
              sta dp:6
              lda ##23044
              sta dp:8
              lda ##23045
              sta dp:10
              lda ##23046
              sta dp:12
              lda ##23047
              sta dp:14
              lda ##23048
              sta dp:16
              lda ##23049
              sta dp:18
              sep #0x20
              lda #0x0c
              pha
              rep #0x20
              lda ##(.word0 ConsoleProbeClobber)
              pha
              tsc
              sta long:ConsoleProbeResults+72
              tdc
              sta long:ConsoleProbeResults+74
              clc
              clv
              lda ##0x1234
              ldx ##0x5678
              ldy ##0x9abc
              jsl ConsoleProbeDispatch
              php
              sta long:ConsoleProbeResults+40
              txa
              sta long:ConsoleProbeResults+42
              tya
              sta long:ConsoleProbeResults+44
              tsc
              inc a
              sta long:ConsoleProbeResults+46
              tdc
              sta long:ConsoleProbeResults+48
              sep #0x20
              pla
              sta long:ConsoleProbeResults+50
              phb
              pla
              sta long:ConsoleProbeResults+51
              rep #0x20
              lda dp:0
              sta long:ConsoleProbeResults+52
              lda dp:2
              sta long:ConsoleProbeResults+54
              lda dp:4
              sta long:ConsoleProbeResults+56
              lda dp:6
              sta long:ConsoleProbeResults+58
              lda dp:8
              sta long:ConsoleProbeResults+60
              lda dp:10
              sta long:ConsoleProbeResults+62
              lda dp:12
              sta long:ConsoleProbeResults+64
              lda dp:14
              sta long:ConsoleProbeResults+66
              lda dp:16
              sta long:ConsoleProbeResults+68
              lda dp:18
              sta long:ConsoleProbeResults+70
              tsc
              clc
              adc ##4
              tcs
              rtl
ConsoleProbeDispatch:
              sep #0x20
              lda long:ConsoleProbeNative+2
              pha
              rep #0x20
              lda long:ConsoleProbeNative
              dec a
              pha
              rtl
ConsoleProbeClobber:
              lda ##42240
              sta dp:0
              lda ##42241
              sta dp:2
              lda ##42242
              sta dp:4
              lda ##42243
              sta dp:6
              lda ##42244
              sta dp:8
              lda ##42245
              sta dp:10
              lda ##42246
              sta dp:12
              lda ##42247
              sta dp:14
              lda ##42248
              sta dp:16
              lda ##42249
              sta dp:18
              ldx ##3
ConsoleProbeWait:
              ldy ##65535
ConsoleProbeSpin:
              dey
              bne ConsoleProbeSpin
              dex
              bne ConsoleProbeWait
              sep #0x20
              lda #0x34
              pha
              plb
              rep #0x20
              lda ##0xaaaa
              ldx ##0xbbbb
              ldy ##0xcccc
              sec
              rtl
