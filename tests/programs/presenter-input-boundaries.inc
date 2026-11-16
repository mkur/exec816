; Fixture-only probes of copied capture and retained manager replay. Capture
; runs once in input.device; Service never takes from the physical source.
PUBLIC CARD boundaryChecks
BYTE boundaryTesting,boundaryBlocked
CARD boundaryFreshCount,boundaryReplay,boundaryApplied

PROC BoundaryRequire(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($fcd0+boundaryChecks)
  FI
  boundaryChecks==+1

RETURN

PROC BoundaryApply(INPUT.Event POINTER target)

  IF boundaryTesting<>0 THEN
    boundaryApplied==+1
  FI
  DESKMOUSE.Apply(target)

RETURN

PROC BoundaryFresh(INPUT.Event POINTER sample)

  IF boundaryTesting<>0 THEN
    boundaryFreshCount==+1
  FI
  Fresh(sample)

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
  BoundaryRequire(acquired<>0 AND AESINPUT.Pending()=0)
  ignored=EXEC.SetSignal(0,wakeMask)
  boundaryTesting=1
  A816MEMORY.Clear(BYTE POINTER(@sample),INPUT.EVENT_BYTES)
  sample.kind=INPUT.EVENT_POINTER
  sample.flags=INPUT.RELATIVE
  sample.x=1
  boundaryBlocked=1
  CapturePointer(0,@sample)
  BoundaryRequire(boundaryApplied=1 AND boundaryFreshCount=1
      AND AESINPUT.Pending()<>0)
  FOR index=0 TO 7 DO
    Boundary()
  OD
  BoundaryRequire(boundaryReplay=0 AND boundaryApplied=1)
  boundaryBlocked=0
  Boundary()
  BoundaryRequire(AESINPUT.Pending()=0 AND boundaryReplay=1)
  BoundaryRequire(boundaryApplied=1 AND boundaryFreshCount=1)
  LET desktop=DESKSTATE.Get()
  BoundaryRequire((desktop.owner.tc_SigRecvd & wakeMask)=0)

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
  DESKMOUSE.Start(cursorX,cursorY,DESKMOUSECONFIG.DEFAULT)
  EXEC.Permit()

RETURN
