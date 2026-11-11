; Included only by the pointer fixture. Exercise the production Service and
; Boundary bodies with deterministic normalized arrivals and real Exec signals.
PUBLIC CARD boundaryChecks
BYTE boundaryTesting,boundaryStage
CARD boundaryQueued,boundaryReads,boundaryFreshCount,boundaryReplay,boundaryApplied

PROC BoundaryRequire(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($fcd0+boundaryChecks)
  FI
  boundaryChecks==+1

RETURN

PROC BoundarySignal()

  LET desktop=DESKSTATE.Get()
  EXEC.Signal(desktop.owner,wakeMask)

RETURN

PROC BoundaryHook(BYTE stage)

  IF boundaryTesting<>0 AND boundaryStage=stage THEN
    boundaryStage=0
    boundaryQueued==+1
    BoundarySignal()
  FI

RETURN

CARD FUNC BoundaryTake(INPUT.Lease POINTER source INPUT.Event POINTER target)

  IF boundaryTesting=0 THEN
    RETURN(INPUT.Take(source,target))
  FI
  boundaryReads==+1
  IF boundaryQueued=0 THEN
    RETURN(INPUT.EMPTY)
  FI
  boundaryQueued==-1
  A816MEMORY.Clear(BYTE POINTER(target),INPUT.EVENT_BYTES)
  target.kind=INPUT.EVENT_POINTER
  target.flags=INPUT.RELATIVE
  target.x=1

RETURN(INPUT.OK)

PROC BoundaryApply(INPUT.Event POINTER target)

  IF boundaryTesting<>0 THEN
    boundaryApplied==+1
  FI
  DESKMOUSE.Apply(target)

RETURN

PROC BoundaryFresh(INPUT.Event POINTER sample)

  IF boundaryTesting<>0 THEN
    boundaryFreshCount==+1
  ELSE
    Fresh(sample)
  FI

RETURN

PROC BoundaryConsume(INPUT.Event POINTER sample)

  IF boundaryTesting<>0 THEN
    boundaryReplay==+1
  ELSE
    Consume(sample)
  FI

RETURN

PUBLIC PROC CheckBoundaries()
  INPUT.Event sample
  BYTE index
  LONGCARD ignored

  EXEC.Forbid()
  LET desktop=DESKSTATE.Get()
  LET owner=desktop.owner
  LET aes=AESSTATE.Get()
  BoundaryRequire(acquired<>0 AND aes.mouseOwner=0)
  BoundaryRequire(AESINPUT.Pending()=0)
  ignored=EXEC.SetSignal(0,wakeMask)
  boundaryTesting=1
  pending=0
  FOR index=0 TO 7 DO
    Boundary()
  OD
  BoundaryRequire(boundaryReads=0)

  ; Arrives after a false signal hint. The next boundary sees the durable bit.
  boundaryStage=1
  Boundary()
  BoundaryRequire(boundaryReads=0 AND boundaryQueued=1)
  BoundaryRequire((owner.tc_SigRecvd & wakeMask)<>0)
  Boundary()
  BoundaryRequire(boundaryReads=2 AND boundaryFreshCount=1 AND pending=0)
  BoundaryRequire((owner.tc_SigRecvd & wakeMask)=0)

  ; Arrival during drain is consumed in order; its signal is not cleared by
  ; the later empty result. One following acknowledgement settles the notice.
  boundaryQueued=1
  boundaryStage=2
  BoundarySignal()
  Boundary()
  BoundaryRequire(boundaryQueued=0 AND boundaryFreshCount=3 AND pending=0)
  BoundaryRequire((owner.tc_SigRecvd & wakeMask)<>0)
  Boundary()
  BoundaryRequire(boundaryReads=6 AND pending=0)

  ; Arrives after an empty observation, before Wait. Wait must return at once.
  boundaryStage=3
  BoundarySignal()
  Boundary()
  BoundaryRequire(boundaryQueued=1 AND pending=0)
  BoundaryRequire(EXEC.Wait(wakeMask)=wakeMask)
  Service(wakeMask)
  BoundaryRequire(boundaryQueued=0 AND pending=0 AND boundaryFreshCount=4)

  ; Exhausting sixteen records retains work without requiring another signal.
  boundaryQueued=20
  BoundarySignal()
  Boundary()
  BoundaryRequire(boundaryQueued=4 AND pending<>0)
  BoundaryRequire((owner.tc_SigRecvd & wakeMask)=0)
  Boundary()
  BoundaryRequire(boundaryQueued=0 AND pending=0 AND boundaryFreshCount=24)
  BoundaryRequire(boundaryApplied=boundaryFreshCount)

  ; AES replay becomes eligible after mouse control is released, independently
  ; of a fresh hardware signal. It must not apply relative acceleration twice.
  sample.flags=0
  sample.x=73
  AESINPUT.Push(@sample)
  aes.mouseOwner=1
  Boundary()
  BoundaryRequire(AESINPUT.Pending()<>0 AND boundaryReplay=0)
  aes.mouseOwner=0
  Boundary()
  BoundaryRequire(AESINPUT.Pending()=0 AND boundaryReplay=1)
  BoundaryRequire(boundaryApplied=24 AND boundaryFreshCount=24)
  BoundaryRequire((owner.tc_SigRecvd & wakeMask)=0)

  ; Native keys retained during a scene pause stay runnable without another
  ; hardware edge. Overflow retires the incomplete stream before replay.
  BoundaryRequire(keyCount=0 AND keyLost=0)
  sample.kind=INPUT.EVENT_KEY
  FOR index=0 TO CONSOLETYPES.RAW_SLOTS-1 DO
    sample.code=CARD(index)
    DeferKey(@sample)
  OD
  BoundaryRequire(keyCount=CONSOLETYPES.RAW_SLOTS AND keyLost=0
      AND deferredKeys(0).code=0
      AND deferredKeys(CONSOLETYPES.RAW_SLOTS-1).code=
        CARD(CONSOLETYPES.RAW_SLOTS-1) AND Runnable()<>0)
  DeferKey(@sample)
  BoundaryRequire(keyCount=CONSOLETYPES.RAW_SLOTS AND keyLost<>0)
  ReplayKeys()
  BoundaryRequire(keyCount=0 AND keyLost=0)

  boundaryTesting=0
  pending=1
  DESKMOUSE.Start(cursorX,cursorY,DESKMOUSECONFIG.DEFAULT)
  EXEC.Permit()

RETURN
