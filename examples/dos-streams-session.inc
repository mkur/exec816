; Resident DOS stream client shared by the example and emitted fixtures.
; Handles/defaults belong to each Task. Read waits only for this stream's reply.
USE EXEC
USE EXECTASKS
USE EXECLISTS
USE TASKSTACKS
USE DOS
USE HEAPCORE
DOS.FileHandle POINTER consoleHandle,readerOutput
EXEC.Task readerTask
EXEC.Task POINTER consoleTask
PROC POINTER absent()
BYTE POINTER inputByte,readBuffer
TYPE ReaderState=[
  BYTE ready
  BYTE stop
  BYTE busy
  BYTE done
  BYTE active
  CARD wakes
  CARD reads
  LONGINT received
  LONGINT error
  DOS.FileHandle POINTER file
]

ReaderState reader
CARD typed,duringRead,redirected
LONGINT commandError
BYTE ARRAY rawName=[82 65 87 58 0]
BYTE ARRAY nilName=[78 73 76 58 0]
BYTE ARRAY readPath=[68 49 58 76 65 82 71 69 46 66 73 78 0]
BYTE ARRAY commandPath=[68 49 58 84 79 79 76 83 47 83 85 66 47 68 65 84 65 46 66 73 78 0]
BYTE ARRAY banner=[12 68 79 83 32 83 84 82 69 65 77 83 10]
BYTE ARRAY completion=[10 68 73 83 75 32 68 79 78 69 10]

; Stop the demonstration at the first broken ownership or I/O expectation.
PROC Check(BYTE good)

  IF good=0 THEN
    HEAPCORE.Abort($f790)
  FI

RETURN

; Write through the session's selected output while checking transfer
; completion.
PROC Print(BYTE POINTER bytes CARD count)

  Check(DOS.Write(DOS.Output(),bytes,LONGINT(count))=LONGINT(count))

RETURN

; Acquire the parent session's console handles before starting the reader.
PROC OpenConsole(BYTE unused)
  DOS.FileHandle POINTER previous

  consoleTask=EXEC.FindTask(BYTE POINTER(0))
  Check(EXEC.AllocSignal(16)=16)
  consoleHandle=DOS.Open(rawName,DOS.MODE_READWRITE)
  Check(consoleHandle<>DOS.FileHandle POINTER(0))
  previous=DOS.SelectInput(consoleHandle)
  Check(previous=DOS.FileHandle POINTER(0) AND DOS.IoErr()=0)
  previous=DOS.SelectOutput(consoleHandle)
  Check(previous=DOS.FileHandle POINTER(0) AND DOS.IoErr()=0)
  inputByte=EXEC.AllocMem(8,EXEC.MEMF_PUBLIC)
  Check(inputByte<>BYTE POINTER(0))

RETURN

; Allocate the independent input buffer retained by the reader Task.
PROC AllocateReader(BYTE unused)

  readBuffer=EXEC.AllocMem(70003,EXEC.MEMF_PUBLIC OR EXEC.MEMF_LINEAR)
  Check(readBuffer<>BYTE POINTER(0))

RETURN

; Acquire the child Task's own DOS input handle.
PROC ReaderOpen(BYTE unused)

  reader.file=DOS.Open(readPath,DOS.MODE_OLDFILE)
  reader.received=-1
  reader.error=DOS.IoErr()

RETURN

; Perform a blocking input request without blocking the parent session.
PROC ReaderTransfer(BYTE unused)

  reader.active=1
  reader.received=DOS.Read(reader.file,readBuffer,70003)
  reader.error=DOS.IoErr()
  reader.active=0

RETURN

; Release the child Task's input ownership before publishing completion.
PROC ReaderClose(BYTE unused)
  LONGINT okay

  IF reader.file<>DOS.FileHandle POINTER(0) THEN
    okay=DOS.Close(reader.file)
    reader.file=DOS.FileHandle POINTER(0)
    IF okay=0 THEN
      reader.error=DOS.IoErr()
    FI
  FI

RETURN

; Run the reader protocol using Task-local DOS state.
PROC ReaderEntry()
  LONGCARD bits
  DOS.FileHandle POINTER previous

  Check(EXEC.AllocSignal(16)=16)
  readerOutput=DOS.Open(rawName,DOS.MODE_NEWFILE)
  Check(readerOutput<>DOS.FileHandle POINTER(0))
  previous=DOS.SelectOutput(readerOutput)
  Check(previous=DOS.FileHandle POINTER(0) AND DOS.IoErr()=0)
  reader.ready=1
  DO
    bits=EXEC.Wait($10000)
    IF reader.stop<>0 THEN
      EXIT
    FI

    reader.wakes==+1
    ReaderOpen(0)
    IF reader.file<>DOS.FileHandle POINTER(0) THEN
      ReaderTransfer(0)
    FI

    ReaderClose(0)
    Check(reader.error=0 AND reader.received>=0)
    Check(DOS.Write(DOS.Output(),completion,11)=11)
    reader.reads==+1
    reader.busy=0
    reader.done=1
    EXEC.Signal(consoleTask,$10000)
  OD

  Check(DOS.Close(readerOutput)<>0 AND DOS.ReleaseContext()<>0)
  EXEC.FreeSignal(16)

RETURN

; Admit the reader Task with its own stack and memory-entry list.
PROC StartReader(BYTE unused)

  readerTask.tc_Node.ln_Type=EXEC.NT_TASK
  readerTask.tc_SPLower=ADDRESS(TASKSTACKS.StackLower(2))
  readerTask.tc_SPUpper=ADDRESS(TASKSTACKS.StackUpper(2))
  readerTask.tc_SPReg=readerTask.tc_SPUpper-SIZE(2)
  EXECLISTS.NewList(@readerTask.tc_MemEntry)
  Check(EXEC.AddTask(@readerTask,@ReaderEntry,absent)=@readerTask)
  WHILE reader.ready=0 DO
    EXEC.Yield()
  OD

RETURN

; A command borrows Input/Output. It does not close or retain either handle.
LONGINT FUNC CopyCommand(BYTE failing)
  LONGINT count

  IF failing<>0 THEN
    RETURN(DOS.Read(DOS.Input(),inputByte,-1))
  FI

  count=DOS.Read(DOS.Input(),inputByte,4)
  IF count<0 THEN
    RETURN(-1)
  FI

RETURN(DOS.Write(DOS.Output(),inputByte,count))

; Temporarily replace borrowed standard streams and restore them after the
; command.
LONGINT FUNC Redirect(BYTE failing)
  DOS.FileHandle POINTER source,sink,oldInput,oldOutput,ignored
  LONGINT result,closed

  source=DOS.Open(commandPath,DOS.MODE_OLDFILE)
  IF source=DOS.FileHandle POINTER(0) THEN
    commandError=DOS.IoErr()
    RETURN(-1)
  FI

  sink=DOS.Open(nilName,DOS.MODE_NEWFILE)
  IF sink=DOS.FileHandle POINTER(0) THEN
    commandError=DOS.IoErr()
    closed=DOS.Close(source)
    RETURN(-1)
  FI

  oldInput=DOS.SelectInput(source)
  Check(DOS.IoErr()=0)
  oldOutput=DOS.SelectOutput(sink)
  Check(DOS.IoErr()=0)
  result=CopyCommand(failing)
  commandError=DOS.IoErr()
  ; Selectors clear IoErr on success. Preserve the command error before restore.
  ignored=DOS.SelectInput(oldInput)
  Check(DOS.IoErr()=0)
  ignored=DOS.SelectOutput(oldOutput)
  Check(DOS.IoErr()=0)
  Check(DOS.Input()=oldInput AND DOS.Output()=oldOutput)
  Check(DOS.Close(source)<>0 AND DOS.Close(sink)<>0)
  redirected==+1

RETURN(result)

; Ask the existing reader Task to begin another input operation.
PROC BeginRead(BYTE unused)

  reader.busy=1
  reader.done=0
  EXEC.Signal(@readerTask,$10000)

RETURN

; Consume the reader's completed input and send it to the session output.
PROC ReadAndEcho(BYTE unused)

  Check(DOS.Read(DOS.Input(),inputByte,1)=1)
  typed==+1
  IF reader.active<>0 THEN
    duringRead==+1
  FI

  Print(inputByte,1)

RETURN

; Drive the interactive session while the separate reader waits for input.
PROC Session(BYTE unused)

  Print(banner,13)
  BeginRead(0)
  DO
    ReadAndEcho(0)
  UNTIL inputByte^=113
  OD

RETURN

; Wait for reader retirement before reclaiming its shared demonstration
; storage.
PROC JoinReader(BYTE unused)
  CARD ticks

  WHILE reader.busy<>0 DO
    ticks=EXECTASKS.Sleep(1)
  OD

  reader.stop=1
  EXEC.Signal(@readerTask,$10000)
  WHILE readerTask.tc_State<>EXEC.TS_REMOVED DO
    ticks=EXECTASKS.Sleep(1)
  OD

RETURN

; Restore selections and release the session's remaining owned resources.
PROC Cleanup(BYTE unused)

  Check(DOS.Close(consoleHandle)<>0 AND DOS.ReleaseContext()<>0)
  EXEC.FreeMem(inputByte,8)
  EXEC.FreeMem(readBuffer,70003)
  EXEC.FreeSignal(16)

RETURN
