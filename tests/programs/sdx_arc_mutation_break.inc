CARD breakTicks,breakEvent
VOLATILE BYTE clockLow=$14,clockHigh=$13

CARD FUNC Clock()
  BYTE high,low

  DO
    high=clockHigh
    low=clockLow
    IF high=clockHigh THEN
      RETURN((CARD(high) LSH 8) OR CARD(low))
    FI
  OD

RETURN(0)

PROC BreakRun()
  PROGRAMIMAGE.Image POINTER image
  SDXSTATE.Session POINTER state
  DOS.FileHandle POINTER output,previous
  PROCESS.Result result
  LONGCARD identity,attempt
  CARD started
  BYTE ready

  image=PROGRAMFILE.Load(BYTE POINTER(c"RAM:ARC.COM"))
  Require(image<>NULL)
  state=SDXSTATE.Session POINTER(image.extension)
  output=DOS.Open(BYTE POINTER(c"RAM:BREAKOUT"),DOS.MODE_NEWFILE)
  Require(output<>NULL)
  previous=DOS.SelectOutput(output)
  identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),
      BYTE POINTER(c"A NEW.ARC BIG.BIN"),17)
  Require(identity<>0)
  DOS.SelectOutput(previous)
  ready=0
  attempt=0
  WHILE ready=0 AND attempt<LONGCARD(500000) DO
    EXEC.Yield()
    EXEC.Forbid()
    breakEvent=SDXSTATE.ReadWord(state.context,SDXABI.FIELDS_EVENT)
    ready=state.tempOwned<>0 AND breakEvent=SDXABI.CALL_FWRITE
    IF ready<>0 THEN
      started=Clock()
      Require(PROCESS.RequestBreak(identity)<>0)
    FI
    EXEC.Permit()
    attempt==+1
  OD
  Require(ready<>0)
  Require(PROCESS.Wait(identity,@result)<>0)
  breakTicks=Clock()-started
  primary=result.primary
  secondary=result.secondary
  Require(primary=20 AND secondary=304)
  Require(breakTicks<250)
  Require(state.handles(0)=NULL AND state.handles(1)=NULL AND
      state.handles(2)=NULL AND state.handles(3)=NULL AND
      state.enumeration=NULL AND state.writeSlot=0 AND state.trapCount=0)
  Require(state.overlayActive=0 AND state.tempOwned=0 AND state.backupOwned=0)
  PROGRAM.Unload(image)
  Require(DOS.Close(output)<>0)
  SDXSTATE.Guards()

RETURN
