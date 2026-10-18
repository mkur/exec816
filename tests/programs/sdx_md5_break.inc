; Test-only inspection identifies the interrupted phase; cancellation itself
; always uses the public owning-Process API. No guest bytes are modified.
USE PROCESSSTATE
USE DOSBREAKTYPES
USE DOSCLIENT
USE FSOPERATION
USE SDXABI

CARD ARRAY breakTicks(4),breakPC(4),breakPhase(4),pcSample(16)
CARD sampleCount
VOLATILE BYTE tick=$14

PROCESSSTATE.Entry POINTER FUNC FindProcess(LONGCARD identity)
  PROCESSSTATE.Table POINTER table
  CARD index

  table=PROCESSSTATE.Registry()
  FOR index=0 TO PROCESSSTATE.CAPACITY-1 DO
    IF table.entries(index).identity=identity THEN
      RETURN(@table.entries(index))
    FI
  OD

RETURN(NULL)

PROC BreakRun(BYTE mode)
  PROGRAMIMAGE.Image POINTER image
  SDXSTATE.Session POINTER state
  PROCESSSTATE.Entry POINTER childRecord
  DOSBREAKTYPES.Scope POINTER scope
  DOSCLIENT.ClientContext POINTER client
  FSOPERATION.WirePacket POINTER packet
  EXEC.Task POINTER task
  DOS.FileHandle POINTER output,previous
  DOS.PipePair pipe
  PROCESS.Result result
  LONGCARD identity,attempt
  CARD pc,event
  BYTE ready,started

  currentCase=200+mode
  image=PROGRAMFILE.Load(BYTE POINTER(c"RAM:MD5"))
  Require(image<>NULL)
  state=SDXSTATE.Session POINTER(image.extension)
  IF mode=3 THEN
    Require(DOS.Pipe(@pipe)<>0)
    Require(DOS.Write(pipe.writer,BYTE POINTER(ADDRESS($300000)),DOS.PIPE_BUFFER_BYTES)=DOS.PIPE_BUFFER_BYTES)
    output=pipe.writer
  ELSE
    output=DOS.Open(BYTE POINTER(c"RAM:BREAKOUT"),DOS.MODE_NEWFILE)
    Require(output<>NULL)
  FI
  previous=DOS.SelectOutput(output)
  EXEC.Forbid()
  identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),BYTE POINTER(c"BIG.BIN"),7)
  Require(identity<>0)
  IF mode=0 THEN
    started=tick
    Require(PROCESS.RequestBreak(identity)<>0)
  FI
  EXEC.Permit()
  DOS.SelectOutput(previous)
  IF mode<>0 THEN
    ready=0
    attempt=0
    WHILE ready=0 AND attempt<LONGCARD(500000) DO
      EXEC.Yield()
      EXEC.Forbid()
      childRecord=FindProcess(identity)
      IF childRecord=NULL OR childRecord.state<>PROCESSSTATE.STATE_RUNNING THEN
        Require(0)
      FI
      event=SDXSTATE.ReadWord(state.context,SDXABI.FIELDS_EVENT)
      pc=SDXSTATE.ReadWord(SDXSTATE.GetFrame(state),SDXABI.FRAME_PC)
      IF sampleCount=0 OR pc<>pcSample((sampleCount-1) & 15) THEN
        pcSample(sampleCount & 15)=pc
        sampleCount==+1
      FI
      IF mode=1 THEN
        ; Only NMI/IRQ capture can suspend inside these compression rounds.
        ready=pc>=$341b AND pc<$3965
      ELSE
        scope=DOSBREAKTYPES.Scope POINTER(childRecord.breakScope)
        IF scope<>NULL THEN
          client=DOSCLIENT.ClientContext POINTER(scope.client)
          task=EXEC.Task POINTER(@childRecord.task(0))
          IF mode=2 AND scope.opState=FSOPERATION.ACTIVE THEN
            packet=FSOPERATION.WirePacket POINTER(scope.packet)
            ready=packet.sp_Pkt.dp_Type=82 AND event=SDXABI.CALL_FREAD
          ELSEIF mode=3 THEN
            ready=event=SDXABI.CALL_PRINTF AND client.busy<>0 AND task.tc_State=EXEC.TS_WAIT
          FI
        FI
      FI
      IF ready<>0 THEN
        breakPC(mode)=pc
        breakPhase(mode)=event
        started=tick
        Require(PROCESS.RequestBreak(identity)<>0)
      FI
      EXEC.Permit()
      attempt==+1
    OD
    Require(ready<>0)
  FI
  Require(PROCESS.Wait(identity,@result)<>0)
  breakTicks(mode)=BYTE(tick-started)
  primary=result.primary
  secondary=result.secondary
  Require(primary=20 AND secondary=304)
  Require(breakTicks(mode)<100)
  Require(state.handles(0)=NULL AND state.handles(1)=NULL AND state.trapCount=0)
  PROGRAM.Unload(image)
  Require(DOS.Close(output)<>0)
  IF mode=3 THEN
    Require(DOS.Close(pipe.reader)<>0)
  FI
  SDXSTATE.Guards()
  Recover()

RETURN
