; Shared demo lifetime and presentation; the shell remains a single implementation.
USE CONSOLE
USE EXECTASKS
INCLUDE "shell/shell-session.inc"
INCLUDE "shell/shell-boot.inc"

LONGCARD demoShellUnit,demoPrimeUnit,demoChild
LONGCARD demoPass,demoFrames
LONGCARD ARRAY demoPowers=[1000000000 100000000 10000000 1000000 100000 10000 1000 100 10 1]
CARD demoCandidate,demoCount,demoLatest,demoWidth,demoShellRows
BYTE demoStop,demoHidden
BYTE ARRAY demoShellName(13),demoPrimeName(13)
BYTE ARRAY demoNil=[78 73 76 58 0]
BYTE POINTER demoFrame,demoComposite
; A full-width separator wraps directly onto the title row.
BYTE ARRAY demoTitle="PRIME SEARCH\{$0A}Primes: "
BYTE ARRAY demoLatestLabel="   Latest: "
BYTE ARRAY demoPassLabel="\{$0A}Pass: "
BYTE ARRAY demoTaskName=[112 114 105 109 101 115 0]
DOS.FileHandle POINTER demoNull,demoOutput

; Build the public console name for a dynamically assigned window unit.
PROC DemoName(BYTE POINTER target LONGCARD unit)
  BYTE index,digit

  target(0)=67
  target(1)=79
  target(2)=78
  target(3)=58
  FOR index=0 TO 7 DO
    digit=BYTE((unit RSH (CARD(7-index)*4)) & 15)
    IF digit<10 THEN
      digit==+48
    ELSE
      digit==+55
    FI

    target(index+4)=digit
  OD

  target(12)=0

RETURN

; Append display text to the worker's output frame.
CARD FUNC DemoText(BYTE POINTER text CARD used)
  CARD index

  FOR index=1 TO CARD(text(0)) DO
    demoFrame(used)=text(index)
    used==+1
  OD

RETURN(used)

; Append a decimal counter without requiring a formatting library.
CARD FUNC DemoNumber(LONGCARD value CARD used)
  CARD index
  BYTE digit,started

  started=0
  FOR index=0 TO 9 DO
    digit=0
    WHILE value>=demoPowers(index) DO
      value==-demoPowers(index)
      digit==+1
    OD

    IF digit<>0 OR started<>0 OR index=9 THEN
      demoFrame(used)=digit+48
      used==+1
      started=1
    FI
  OD

RETURN(used)

; Ascending sieve, one bit per candidate, bounded to 10,000.
BYTE FUNC DemoPrime(CARD value)
  CARD multiple
  BYTE mask

  IF value<2 THEN
    RETURN(0)
  FI

  mask=BYTE(CARD(1) LSH (value & 7))
  IF (demoComposite(value RSH 3) & mask)<>0 THEN
    RETURN(0)
  FI

  IF value<=100 THEN
    multiple=value*value
    WHILE multiple<=10000 DO
      mask=BYTE(CARD(1) LSH (multiple & 7))
      demoComposite(multiple RSH 3)=demoComposite(multiple RSH 3) OR mask
      multiple==+value
    OD
  FI

RETURN(1)

; Keep prime calculation running while the foreground shell remains
; interactive.
LONGINT FUNC DemoCompute()
  CARD batch,used,tick
  LONGCARD slept
  LONGINT written
  EXEC.Task POINTER self

  self=EXEC.FindTask(BYTE POINTER(0))
  EXEC.Forbid()
  self.tc_Node.ln_Name=demoTaskName
  EXEC.Permit()
  FOR batch=0 TO 1250 DO
    demoComposite(batch)=0
  OD

  demoCandidate=2
  demoPass=1
  WHILE demoStop=0 DO
    FOR batch=1 TO 100 DO
      IF demoStop<>0 THEN
        EXIT
      FI

      IF DemoPrime(demoCandidate)<>0 THEN
        demoCount==+1
        demoLatest=demoCandidate
      FI

      IF demoCandidate=10000 THEN
        demoCandidate=2
        demoCount=0
        demoLatest=0
        FOR tick=0 TO 1250 DO
          demoComposite(tick)=0
        OD

        IF demoPass=$ffffffff THEN
          demoPass=1
        ELSE
          demoPass==+1
        FI
      ELSE
        demoCandidate==+1
      FI
    OD

    IF demoStop<>0 THEN
      EXIT
    FI

    demoFrame(0)=12
    FOR used=1 TO demoWidth DO
      demoFrame(used)=45
    OD

    used=DemoText(demoTitle,demoWidth+1)
    used=DemoNumber(LONGCARD(demoCount),used)
    used=DemoText(demoLatestLabel,used)
    used=DemoNumber(LONGCARD(demoLatest),used)
    used=DemoText(demoPassLabel,used)
    used=DemoNumber(demoPass,used)
    written=DOS.Write(DOS.Output(),demoFrame,LONGINT(used))
    IF written<>LONGINT(used) THEN
      RETURN(PROCESS.RETURN_ERROR)
    FI

    demoFrames==+1
    FOR tick=1 TO 50 DO
      IF demoStop<>0 THEN
        EXIT
      FI

      slept=EXECTASKS.Sleep(1)
    OD
  OD

RETURN(PROCESS.RETURN_OK)

; Create the computation window and process before entering the shared shell.
BYTE FUNC DemoStart()
  DOS.FileHandle POINTER oldInput,oldOutput,ignored

  demoStop=0
  demoFrames=0
  demoCount=0
  demoLatest=0
  demoWidth=CONSOLE.ScreenWidth()
  demoShellRows=CONSOLE.ScreenHeight()
  IF demoWidth=0 OR demoShellRows<=6 THEN
    RETURN(0)
  FI

  demoShellRows==-6
  demoShellUnit=CONSOLE.Create(demoWidth,demoShellRows)
  IF demoShellUnit=0 THEN
    RETURN(0)
  FI

  demoPrimeUnit=CONSOLE.Create(demoWidth,6)
  IF demoPrimeUnit=0 THEN
    RETURN(0)
  FI

  demoFrame=EXEC.AllocMem(1416,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR)
  IF demoFrame=BYTE POINTER(0) THEN
    RETURN(0)
  FI

  demoComposite=demoFrame+SIZE(160)
  IF CONSOLE.Hide(0)=0 THEN
    RETURN(0)
  FI

  demoHidden=1
  IF CONSOLE.Show(demoShellUnit,0,0)=0 OR CONSOLE.Show(demoPrimeUnit,0,demoShellRows)=0 THEN
    RETURN(0)
  FI

  IF CONSOLE.Focus(demoShellUnit)=0 THEN
    RETURN(0)
  FI

  DemoName(demoShellName,demoShellUnit)
  DemoName(demoPrimeName,demoPrimeUnit)
  IF ShellBootStart(demoShellName)=0 THEN
    RETURN(0)
  FI

  demoNull=DOS.Open(demoNil,DOS.MODE_OLDFILE)
  demoOutput=DOS.Open(demoPrimeName,DOS.MODE_NEWFILE)
  IF demoNull=DOS.FileHandle POINTER(0) OR demoOutput=DOS.FileHandle POINTER(0) THEN
    RETURN(0)
  FI

  oldInput=DOS.SelectInput(demoNull)
  oldOutput=DOS.SelectOutput(demoOutput)
  demoChild=PROCESS.Start(@DemoCompute,BYTE POINTER(0),0)
  ignored=DOS.SelectInput(oldInput)
  ignored=DOS.SelectOutput(oldOutput)
  IF demoChild=0 THEN
    RETURN(0)
  FI

  IF DOS.Close(demoNull)=0 THEN
    RETURN(0)
  FI

  demoNull=DOS.FileHandle POINTER(0)
  IF DOS.Close(demoOutput)=0 THEN
    RETURN(0)
  FI

  demoOutput=DOS.FileHandle POINTER(0)

RETURN(1)

; Stop the background computation and release its process and window
; ownership.
LONGINT FUNC DemoFinish()
  PROCESS.Result outcome
  LONGINT result,shellResult

  result=0
  demoStop=1
  IF demoChild<>0 THEN
    IF PROCESS.Wait(demoChild,@outcome)=0 THEN
      RETURN(20)
    FI

    result=outcome.primary
    demoChild=0
  FI

  IF demoNull<>DOS.FileHandle POINTER(0) THEN
    IF DOS.Close(demoNull)=0 THEN
      RETURN(20)
    FI

    demoNull=DOS.FileHandle POINTER(0)
  FI

  IF demoOutput<>DOS.FileHandle POINTER(0) THEN
    IF DOS.Close(demoOutput)=0 THEN
      RETURN(20)
    FI

    demoOutput=DOS.FileHandle POINTER(0)
  FI

  IF demoFrame<>BYTE POINTER(0) THEN
    EXEC.FreeMem(demoFrame,1416)
    demoFrame=BYTE POINTER(0)
    demoComposite=BYTE POINTER(0)
  FI

  IF shell<>ShellState POINTER(0) THEN
    shellResult=ShellFinish()
    IF result=0 THEN
      result=shellResult
    FI

    IF shell<>ShellState POINTER(0) THEN
      RETURN(20)
    FI
  FI

  IF demoPrimeUnit<>0 THEN
    IF CONSOLE.Destroy(demoPrimeUnit)=0 THEN
      RETURN(20)
    FI

    demoPrimeUnit=0
  FI

  IF demoShellUnit<>0 THEN
    IF CONSOLE.Destroy(demoShellUnit)=0 THEN
      RETURN(20)
    FI

    demoShellUnit=0
  FI

  IF demoHidden<>0 THEN
    IF CONSOLE.Show(0,0,0)=0 THEN
      RETURN(20)
    FI

    demoHidden=0
  FI

RETURN(result)
