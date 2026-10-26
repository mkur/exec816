; Disposable ROM characterization. Native VBI must preserve private D/DBR,
; hidden accumulator B, register widths/status and the relocated native stack.
; COP $00 calls an ordinary bank-zero RTS target and restores that domain.
; This fixture has no Exec Tasks and never returns to its binary loader.
.setcpu "65816"
.macpack longbranch
.export start, done, after_wait
.segment "CODE"
.a8
.i8
start:
 sei
 cld
 stz $d40e
 clc
 xce
 rep #$30
.a16
.i16
 lda #$47ef
 tcs
 lda #0
 tcd
 phk
 plb
 lda #0
 ldx #62
clear:
 sta $2000,x
 dex
 dex
 bpl clear
 lda #$a5a5
 ldx #$10e
seed:
 sta $4700,x
 dex
 dex
 bpl seed
 lda #$a5a5
 ldx #$11e
guards:
 sta $21f0,x
 dex
 dex
 bpl guards
 ; A high native stack is intentional. The production adapter uses page one.
 lda #$2200
 tcd
 sep #$20
.a8
 lda #$12
 pha
 plb
 .if CASE = 1
  rep #$30
.a16
  pea target
  ldx #$a6
  ldy #$5a
  lda #$abcd
  cop $00
  rep #$30
  pla
 .else
  lda #$40
  sta f:$d40e
  lda #FLAGS
  pha
  rep #$30
.a16
.i16
  lda #$abcd
  ldx #$1234
  ldy #$5678
  plp
  wai
after_wait:
 .endif
 php
 rep #$30
.a16
.i16
 sta f:$2000
 txa
 sta f:$2002
 tya
 sta f:$2004
 tsc
 inc a
 sta f:$2006
 tdc
 sta f:$2008
 phb
 sep #$20
.a8
 pla
 sta f:$200a
 pla
 sta f:$200b
 clc
 xce
 lda #0
 rol a
 sta f:$200c
 sei
 lda #0
 sta f:$d40e
 lda #$ff
 sta f:$203f
done:
 bra done
 .if CASE = 1
after_wait:
 .endif
.a8
.i8
target:
 lda #$5a
 sta f:$2020
 ldx #$34
 ldy #$78
 rts
