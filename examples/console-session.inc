; A resident demonstration client. The reader is created once and reused.
; All line editing, command handling and file-text conversion live above Exec.
; Byte-argument helpers are excluded from the zero-argument Task entry table.
USE EXEC
USE EXECTASKS
USE EXECLISTS
USE TASKSTACKS
USE DOS
USE HEAPCORE
EXEC.MsgPort POINTER replies
EXEC.IOStdReq POINTER inputRequest,outputRequest
EXEC.Task readerTask
EXEC.Task POINTER consoleTask
PROC POINTER absent()
BYTE POINTER line,inputByte,readBuffer,textBuffer
TYPE EditorState=[
  BYTE lineLength
  BYTE quitting
  CARD typed
  CARD duringRead
  CARD lines
  CARD textReads
  CARD errors
]

EditorState editor
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
BYTE ARRAY consoleName=[99 111 110 115 111 108 101 46 100 101 118 105 99 101 0]
BYTE ARRAY readPath=[68 49 58 84 79 79 76 83 47 83 85 66 47 68 65 84 65 46 66 73 78 0]
BYTE ARRAY textPath=[68 49 58 84 69 88 84 46 84 88 84 0]
BYTE ARRAY missingPath=[68 49 58 65 66 83 69 78 84 0]

BYTE ARRAY words=[
  12 69 120 101 99 56 49 54 32 99 111 110 115 111 108 101 13 10 114 32
  114 101 97 100 44 32 116 32 116 101 120 116 44 32 101 32 101 114 114 111
  114 44 32 113 32 113 117 105 116 13 10 62 32 13 10 8 32 8 82 101
  97 100 32 99 111 109 112 108 101 116 101 13 10 70 105 108 101 32 101 114
  114 111 114 13 10 82 101 97 100 32 98 117 115 121 13 10
]

; Stop the demonstration at the first broken ownership or I/O expectation.
PROC Check(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($f780)
  FI

RETURN

; Write through the session's selected output while checking transfer
; completion.
PROC Print(BYTE POINTER bytes CARD count)
  INT error

  outputRequest.io_Command=EXEC.CMD_WRITE
  outputRequest.io_Data=bytes
  outputRequest.io_Length=LONGCARD(count)
  outputRequest.io_Offset=0
  error=EXEC.DoIO(EXEC.IORequest POINTER(outputRequest))
  Check(error=0 AND outputRequest.io_Actual=LONGCARD(count))

RETURN

; Display the prompt before arming the next line of input.
PROC Prompt(BYTE unused)

  Print(@words(51),2)
  IF editor.lineLength<>0 THEN
    Print(line,CARD(editor.lineLength))
  FI

RETURN

; Acquire the parent session's console handles before starting the reader.
PROC OpenConsole(BYTE unused)
  INT error

  consoleTask=EXEC.FindTask(BYTE POINTER(0))
  Check(EXEC.AllocSignal(16)=16)
  replies=EXEC.CreateMsgPort()
  Check(replies<>EXEC.MsgPort POINTER(0))
  inputRequest=EXEC.IOStdReq POINTER(EXEC.CreateIORequest(replies,42))
  outputRequest=EXEC.IOStdReq POINTER(EXEC.CreateIORequest(replies,42))
  Check(inputRequest<>EXEC.IOStdReq POINTER(0)
      AND outputRequest<>EXEC.IOStdReq POINTER(0))
  error=EXEC.OpenDevice(consoleName,0,EXEC.IORequest POINTER(inputRequest),0)
  Check(error=0)
  ; A second request shares this one exclusive open; close the binding once.
  outputRequest.io_Device=inputRequest.io_Device
  outputRequest.io_Unit=inputRequest.io_Unit
  line=EXEC.AllocMem(40,EXEC.MEMF_PUBLIC)
  inputByte=EXEC.AllocMem(1,EXEC.MEMF_PUBLIC)
  Check(line<>BYTE POINTER(0) AND inputByte<>BYTE POINTER(0))

RETURN

; Allocate the independent input buffer retained by the reader Task.
PROC AllocateReader(BYTE unused)

  readBuffer=EXEC.AllocMem(70003,EXEC.MEMF_PUBLIC OR EXEC.MEMF_LINEAR)
  textBuffer=EXEC.AllocMem(259,EXEC.MEMF_PUBLIC)
  Check(readBuffer<>BYTE POINTER(0) AND textBuffer<>BYTE POINTER(0))

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

  okay=DOS.ReleaseContext()
  Check(okay<>0)

RETURN

; Run the reader protocol using Task-local DOS state.
PROC ReaderEntry()
  LONGCARD bits

  Check(EXEC.AllocSignal(16)=16)
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
    reader.reads==+1
    reader.busy=0
    reader.done=1
    EXEC.Signal(consoleTask,$10000)
  OD

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

; Show file text while translating its line endings at the console boundary.
PROC TextFile(BYTE unused)
  DOS.FileHandle POINTER file
  LONGINT count,okay
  CARD index
  BYTE value

  file=DOS.Open(textPath,DOS.MODE_OLDFILE)
  IF file=DOS.FileHandle POINTER(0) THEN
    editor.errors==+1
    Print(@words(73),12)
    okay=DOS.ReleaseContext()
    Check(okay<>0)
    RETURN
  FI

  count=DOS.Read(file,textBuffer,259)
  okay=DOS.Close(file)
  IF count<0 OR okay=0 THEN
    editor.errors==+1
    Print(@words(73),12)
  ELSE
    editor.textReads==+1
    IF count<>0 THEN
      FOR index=0 TO CARD(count)-1 DO
        value=textBuffer(index)
        ; Explicit ATASCII conversion here, outside both DOS and the device.
        IF value=155 THEN
          value=10
        ELSEIF value<32 OR value>126 THEN
          value=46
        FI

        textBuffer(index)=value
      OD

      Print(textBuffer,CARD(count))
      Print(@words(53),2)
    FI
  FI

  okay=DOS.ReleaseContext()
  Check(okay<>0)

RETURN

; Demonstrate a failed open without losing its DOS error during reporting.
PROC MissingFile(BYTE unused)
  DOS.FileHandle POINTER file
  LONGINT okay

  file=DOS.Open(missingPath,DOS.MODE_OLDFILE)
  Check(file=DOS.FileHandle POINTER(0) AND DOS.IoErr()=DOS.ERROR_OBJECT_NOT_FOUND)
  editor.errors==+1
  Print(@words(73),12)
  okay=DOS.ReleaseContext()
  Check(okay<>0)

RETURN

; Dispatch a completed input line to the demonstration's resident commands.
PROC Command(BYTE unused)

  IF editor.lineLength=1 THEN
    IF line(0)=113 THEN
      editor.quitting=1
    ELSEIF line(0)=114 THEN
      IF reader.busy<>0 THEN
        Print(@words(85),11)
      ELSE
        reader.busy=1
        reader.done=0
        EXEC.Signal(@readerTask,$10000)
      FI
    ELSEIF line(0)=116 THEN
      TextFile(0)
    ELSEIF line(0)=101 THEN
      MissingFile(0)
    FI
  FI

  editor.lineLength=0
  editor.lines==+1

RETURN

; Apply a received character to the example's bounded input line.
PROC Key(BYTE value)

  editor.typed==+1
  IF reader.active<>0 THEN
    editor.duringRead==+1
  FI

  IF value=10 THEN
    Print(@words(53),2)
    Command(0)
    IF editor.quitting=0 THEN
      Prompt(0)
    FI
  ELSEIF value=8 THEN
    IF editor.lineLength<>0 THEN
      editor.lineLength==-1
      Print(@words(55),3)
    FI
  ELSEIF value=3 THEN
    editor.lineLength=0
    Print(@words(53),2)
    Prompt(0)
  ELSEIF value>=32 AND value<=126 AND editor.lineLength<36 THEN
    line(editor.lineLength)=value
    editor.lineLength==+1
    Print(inputByte,1)
  FI

; Two prompt columns + at most 36 characters never wrap. BS cannot cross a row.
RETURN

; Request the next character without creating another reader Task.
PROC ArmRead(BYTE unused)

  inputRequest.io_Command=EXEC.CMD_READ
  inputRequest.io_Data=inputByte
  inputRequest.io_Length=1
  inputRequest.io_Offset=0
  EXEC.SendIO(EXEC.IORequest POINTER(inputRequest))

RETURN

; Drive the interactive session while the separate reader waits for input.
PROC Session(BYTE unused)
  LONGCARD bits,mask
  INT error

  mask=(LONGCARD(1) LSH replies.mp_SigBit) OR $10000
  Print(@words(0),51)
  Prompt(0)
  ArmRead(0)
  WHILE editor.quitting=0 DO
    ; Durable replies/flags are checked before sleeping: output collection can
    ; consume the shared port signal while an input reply is already queued.
    IF reader.done=0
        AND EXEC.CheckIO(EXEC.IORequest POINTER(
        inputRequest))=EXEC.IORequest POINTER(0) THEN
      bits=EXEC.Wait(mask)
    FI

    IF EXEC.CheckIO(EXEC.IORequest POINTER(
        inputRequest))<>EXEC.IORequest POINTER(0) THEN
      error=EXEC.WaitIO(EXEC.IORequest POINTER(inputRequest))
      IF error=0 THEN
        Check(inputRequest.io_Actual=1)
        Key(inputByte^)
      ELSE
        Check(error=1)
        editor.lineLength=0
        Print(@words(53),2)
        Prompt(0)
      FI

      IF editor.quitting=0 THEN
        ArmRead(0)
      FI
    FI

    IF reader.done<>0 THEN
      reader.done=0
      Print(@words(53),2)
      IF reader.error=0 AND reader.received>=0 THEN
        Print(@words(58),15)
      ELSE
        Print(@words(73),12)
      FI

      IF editor.quitting=0 THEN
        Prompt(0)
      FI
    FI
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

  EXEC.CloseDevice(EXEC.IORequest POINTER(inputRequest))
  EXEC.DeleteIORequest(EXEC.IORequest POINTER(inputRequest))
  EXEC.DeleteIORequest(EXEC.IORequest POINTER(outputRequest))
  EXEC.DeleteMsgPort(replies)
  EXEC.FreeSignal(16)
  EXEC.FreeMem(line,40)
  EXEC.FreeMem(inputByte,1)
  EXEC.FreeMem(readBuffer,70003)
  EXEC.FreeMem(textBuffer,259)

RETURN
