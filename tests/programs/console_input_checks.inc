; Controlled stream fixtures: no hardware owner is active here. Real matrix
; IRQ qualification runs afterward, with a separate waiting consumer.
PROC TranslationChecks()

  Require(CONSOLEINPUT.Decode(instance,$0001003f)=97)
  Require(CONSOLEINPUT.Decode(instance,$0001003f)=$ffff)
  Require(CONSOLEINPUT.Decode(instance,$0002003f)=97)
  Require(CONSOLEINPUT.Decode(instance,$0003007f)=65)
  Require(CONSOLEINPUT.Decode(instance,$000400bf)=1)
  Require(CONSOLEINPUT.Decode(instance,$000501ff)=3)
  Require(CONSOLEINPUT.Decode(instance,$0006003c)=$ffff)
  Require(CONSOLEINPUT.Decode(instance,$0007003f)=65)
  Require(CONSOLEINPUT.Decode(instance,$0008007f)=97)
  Require(CONSOLEINPUT.Decode(instance,$0009003c)=$ffff)
  Require(CONSOLEINPUT.Decode(instance,$000a000c)=10)
  Require(CONSOLEINPUT.Decode(instance,$000b0034)=8)
  Require(CONSOLEINPUT.Decode(instance,$000c002c)=9)
  Require(CONSOLEINPUT.Decode(instance,$000d001c)=27)
  Require(CONSOLEINPUT.Decode(instance,$000e00a1)=0)
  Require(CONSOLEINPUT.Decode(instance,$ffff003f)=97)
  Require(CONSOLEINPUT.Decode(instance,$0000003f)=97)

RETURN

; Exercise translated input across FIFO wraparound and bounded reads.
PROC FifoChecks()
  CARD index,count

  FOR index=1 TO 128 DO
    CONSOLEINPUT.Deliver(instance,(LONGCARD(index) LSH 16) OR $3f)
  OD

  Require(instance.inputCount=128 AND instance.inputLost=0)
  count=CONSOLEINPUT.Read(instance,translated,64)
  Require(count=64)
  FOR index=0 TO 63 DO
    Require(translated(index)=97)
  OD

  FOR index=129 TO 192 DO
    CONSOLEINPUT.Deliver(instance,(LONGCARD(index) LSH 16) OR $15)
  OD

  count=CONSOLEINPUT.Read(instance,translated,64)
  Require(count=64)
  FOR index=0 TO 63 DO
    Require(translated(index)=97)
  OD

  count=CONSOLEINPUT.Read(instance,translated,64)
  Require(count=64)
  FOR index=0 TO 63 DO
    Require(translated(index)=98)
  OD

RETURN

; Require one recoverable input-loss indication with no stale payload
; delivery.
PROC LossChecks()
  CARD index,count

  FOR index=193 TO 321 DO
    CONSOLEINPUT.Deliver(instance,(LONGCARD(index) LSH 16) OR $3f)
  OD

  Require(instance.inputCount=0 AND instance.inputLost=1)
  count=CONSOLEINPUT.Read(instance,translated,0)
  Require(count=0 AND instance.inputLost=1)
  count=CONSOLEINPUT.Read(instance,translated,64)
  Require(count=$ffff AND instance.inputLost=0)
  count=CONSOLEINPUT.Read(instance,translated,64)
  Require(count=0)
  instance.open=0
  CONSOLEINPUT.Deliver(instance,$0142003f)
  Require(instance.inputCount=0)
  instance.open=1
  CONSOLEINPUT.Deliver(instance,$0143003f)
  Require(instance.inputCount=1)
  CONSOLEINPUT.Clear(instance)
  Require(instance.inputCount=0)

RETURN

; Check captured-event ownership and overflow before involving real hardware
; input.
PROC RingChecks()
  INPUTNATIVE.Capture POINTER capture
  CARD index
  BYTE turn
  LONGCARD event

  capture=INPUTNATIVE.Capture POINTER($0f0c00)
  ; Two complete rings, including byte-counter wrap at 255 -> 0. Unlike the
  ; throwaway probe, all 64 slots are usable without sacrificing one slot.
  FOR turn=0 TO 1 DO
    FOR index=0 TO 63 DO
      capture.events(index).key=BYTE(index)
      capture.events(index).kind=0
      capture.events(index).tick=$ffc0+index
      capture.events(index).route=LONGCARD(index)+$12345600
    OD

    IF turn=0 THEN
      capture.tail=0
      capture.head=64
    ELSE
      capture.tail=192
      capture.head=0
    FI

    FOR index=0 TO 63 DO
      event=INPUTCAPTURE.Take()
      Require(BYTE(event)=BYTE(index) AND CARD(event RSH 16)=$ffc0+index)
      Require(capture.takenRoute=LONGCARD(index)+$12345600)
    OD

    Require(INPUTCAPTURE.Take()=LONGCARD($ffffffff))
  OD

  capture.head=20
  capture.tail=1
  capture.lost=1
  capture.lostMask=CARD(1) LSH CARD(window.route & 15)
  Require(INPUTCAPTURE.Take()=LONGCARD($fffffffe))
  Require(capture.tail=1 AND capture.lost=0 AND capture.takenRoute=window.route)
  INPUTCAPTURE.ResetInput()
  Require(INPUTCAPTURE.Take()=LONGCARD($ffffffff))

RETURN
