; Resident commands; all temporary payload uses the shared shell allocation.

; Release a temporary directory lock without losing the command's original error.
PROC ShellReleaseLock()

  ; Preserve the saved command error while obtaining an unambiguous result
  ; from UnLock, whose successful void return preserves the current IoErr.
  LET ignored=DOS.CurrentDir(shell.directory)
  IF DOS.IoErr()<>0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN
  FI

  DOS.UnLock(shell.retiredDirectory)
  IF DOS.IoErr()<>0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())

  ELSE
    shell.retiredDirectory=NULL
  FI

RETURN

; Show the named or current directory, distinguishing subdirectories from files.
PROC ShellDir()
  SYS.CSTRING path

  path=c""
  IF shell.argc=2 THEN
    path=CSTRING(shell.words(1).text)
  FI

  shell.retiredDirectory=DOS.Lock(BYTE POINTER(path),DOS.SHARED_LOCK)
  IF shell.retiredDirectory=NULL THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
    RETURN
  FI

  LET info=DOS.FileInfoBlock POINTER(ShellScratch())
  LET result=DOS.Examine(shell.retiredDirectory,info)
  LET error=DOS.IoErr()
  IF result=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,error)

  ELSEIF info.fib_DirEntryType<=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_WRONG_TYPE)

  ELSE
    DO
      BEGIN
        IF ShellPoll()<>0 THEN
          EXIT
        FI

        LET next=DOS.ExNext(shell.retiredDirectory,info)
        LET nextError=DOS.IoErr()
        IF next=0 THEN
          IF nextError<>DOS.ERROR_NO_MORE_ENTRIES THEN
            ShellFail(PROCESS.RETURN_ERROR,nextError)
          FI

          EXIT
        FI

        ShellText(DOS.Output(),CSTRING(@info.fib_FileName(0)))
        IF info.fib_DirEntryType>0 THEN
          ShellByte(DOS.Output(),CHAR_SLASH)

        ELSE
          ShellByte(DOS.Output(),ASCII.SPACE)
          ShellNumber(DOS.Output(),info.fib_Size)
        FI

        ShellByte(DOS.Output(),ASCII.LF)
        IF shell.status<>PROCESS.RETURN_OK THEN
          EXIT
        FI
      END
    OD
  FI

  ShellReleaseLock()

RETURN

; Make Atari and ASCII file text readable through TYPE without letting
; arbitrary file bytes act as console controls. Return the displayable length
; in the shared transfer buffer.
CARD FUNC ShellConvert(CARD count)
  CARD source,target
  BYTE value

  LET buffer=ShellTransfer()
  target=0
  IF count=0 THEN
    RETURN(0)
  FI

  FOR source=0 TO count-1 DO
    value=buffer(source)
    IF value<>ASCII.CR THEN
      IF value=ASCII.ATASCII_EOL THEN
        value=ASCII.LF

      ELSEIF value<>ASCII.LF AND value<>ASCII.TAB
            AND (value<ASCII.SPACE OR value>CHAR_LAST_PRINTABLE) THEN
        value=CHAR_DOT
      FI

      buffer(target)=value
      target==+1
    FI
  OD

RETURN(target)

; Release a file opened by TYPE; borrowed standard input belongs to its caller.
PROC ShellCloseCommandInput()

  IF shell.commandInput<>NULL THEN
    IF DOS.Close(shell.commandInput)=0 THEN
      ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())

    ELSE
      shell.commandInput=NULL
    FI
  FI

RETURN

; Display a file or redirected input as readable text. With no filename,
; an interactive console is rejected so TYPE does not wait for keyboard input.
PROC ShellType()
  DOS.FileHandle POINTER file
  LONGINT error

  IF shell.argc=2 THEN
    shell.commandInput=DOS.Open(shell.words(1).text,DOS.MODE_OLDFILE)
    file=shell.commandInput

  ELSE
    file=DOS.Input()
  FI

  IF file=NULL THEN
    error=DOS.IoErr()
    IF error=0 THEN
      error=DOS.ERROR_BAD_STREAM_NAME
    FI

    ShellFail(PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  IF shell.argc=1 THEN
    BEGIN
      LET interactive=DOS.IsInteractive(file)
      LET interactiveError=DOS.IoErr()
      IF interactiveError<>0 THEN
        ShellFail(PROCESS.RETURN_ERROR,interactiveError)
        RETURN
      FI

      IF interactive<>0 THEN
        ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_WRONG_TYPE)
        RETURN
      FI
    END
  FI

  DO
    BEGIN
      IF ShellPoll()<>0 THEN
        EXIT
      FI

      LET count=DOS.Read(file,ShellTransfer(),TRANSFER_CAPACITY)
      LET readError=DOS.IoErr()
      IF count<0 OR readError<>0 THEN
        ShellFail(PROCESS.RETURN_ERROR,readError)
        EXIT
      FI

      IF count=0 THEN
        EXIT
      FI

      IF count>TRANSFER_CAPACITY THEN
        ShellFail(PROCESS.RETURN_FAIL,DOS.ERROR_BAD_NUMBER)
        EXIT
      FI

      LET converted=ShellConvert(CARD(count))
      ShellWrite(DOS.Output(),ShellTransfer(),converted)
      IF shell.status<>PROCESS.RETURN_OK THEN
        EXIT
      FI
    END
  OD

  ShellCloseCommandInput()

RETURN

; Show free memory and the largest ordinary and linear allocations available.
PROC ShellMem()

  ShellText(DOS.Output(),c"ordinary total ")
  ShellNumber(DOS.Output(),LONGINT(EXEC.AvailMem(0)))
  ShellByte(DOS.Output(),ASCII.LF)

  ShellText(DOS.Output(),c"ordinary largest ")
  ShellNumber(DOS.Output(),LONGINT(EXEC.AvailMem(EXEC.MEMF_LARGEST)))
  ShellByte(DOS.Output(),ASCII.LF)

  ShellText(DOS.Output(),c"linear total ")
  ShellNumber(DOS.Output(),LONGINT(EXEC.AvailMem(EXEC.MEMF_LINEAR)))
  ShellByte(DOS.Output(),ASCII.LF)

  ShellText(DOS.Output(),c"linear largest ")
  ShellNumber(DOS.Output(),
      LONGINT(EXEC.AvailMem(EXEC.MEMF_LINEAR OR EXEC.MEMF_LARGEST)))
  ShellByte(DOS.Output(),ASCII.LF)

RETURN

; Give task states readable, consistently sized labels for the TASKS listing.
PROC ShellTaskState(DOS.FileHandle POINTER output BYTE state)
  SYS.CSTRING label

  CASE state OF
  WHEN TASKINSPECT.STATE_RUNNING THEN
    label=c"RUNNING "

  WHEN TASKINSPECT.STATE_READY THEN
    label=c"READY   "

  WHEN TASKINSPECT.STATE_SIGNAL_WAIT THEN
    label=c"WAITING "

  WHEN TASKINSPECT.STATE_SLEEPING THEN
    label=c"SLEEPING"

  ELSE
    label=c"UNKNOWN "
  ESAC

  ShellText(output,label)

RETURN

; Show a snapshot of live tasks without holding up scheduling during output.
PROC ShellTasks(DOS.FileHandle POINTER output)
  CARD index

  ; 26 bytes per slot, at most 16 configured slots: fits the existing 512 bytes.
  ; Snapshot releases Forbid before any DOS output can block.
  LET rows=TASKINSPECT.Info POINTER(ShellTransfer())
  LET count=TASKINSPECT.Snapshot(rows,TASKINSPECT.CAPACITY)
  ShellText(output,c"SLOT STATE    NAME")
  ShellByte(output,ASCII.LF)
  IF count=0 THEN
    RETURN
  FI

  FOR index=0 TO count-1 DO
    ShellNumber(output,rows(index).slot)
    IF rows(index).slot<10 THEN
      ShellByte(output,ASCII.SPACE)
    FI

    ShellByte(output,ASCII.SPACE)
    ShellByte(output,ASCII.SPACE)
    ShellByte(output,ASCII.SPACE)
    ShellTaskState(output,rows(index).state)
    ShellByte(output,ASCII.SPACE)
    IF rows(index).name(0)=ASCII.NUL THEN
      ShellText(output,c"(unnamed)")

    ELSE
      ShellText(output,CSTRING(@rows(index).name(0)))
    FI

    ShellByte(output,ASCII.LF)
    IF shell.status<>PROCESS.RETURN_OK THEN
      EXIT
    FI
  OD

RETURN

; Show which resident devices are available and their lifecycle state.
PROC ShellDevices(DOS.FileHandle POINTER output)
  CARD index
  SYS.CSTRING label

  LET rows=DEVICEINSPECT.Info POINTER(ShellTransfer())
  LET count=DEVICEINSPECT.Snapshot(rows,DEVICEINSPECT.CAPACITY)
  ShellText(output,c"DEVICE          STATE")
  ShellByte(output,ASCII.LF)
  IF count=0 THEN
    RETURN
  FI

  FOR index=0 TO count-1 DO
    IF rows(index).kind=DEVICEINSPECT.CONSOLE THEN
      ShellText(output,c"console.device  ")

    ELSE
      ShellText(output,c"sio.device      ")
    FI

    CASE rows(index).state OF
    WHEN DEVICEINSPECT.INACTIVE THEN
      label=c"inactive"

    WHEN DEVICEINSPECT.STARTING THEN
      label=c"starting"

    WHEN DEVICEINSPECT.READY THEN
      label=c"ready"

    WHEN DEVICEINSPECT.STOPPING THEN
      label=c"stopping"

    WHEN DEVICEINSPECT.STOPPED THEN
      label=c"stopped"

    WHEN DEVICEINSPECT.OFFLINE THEN
      label=c"offline"

    ELSE
      label=c"unknown"
    ESAC

    ShellText(output,label)
    ShellByte(output,ASCII.LF)
    IF shell.status<>PROCESS.RETURN_OK THEN
      EXIT
    FI
  OD

RETURN

; Show mounted filesystems, their access mode and whether they are online.
PROC ShellMounts(DOS.FileHandle POINTER output)
  CARD index,width

  LET rows=FSINSPECT.Info POINTER(ShellTransfer())
  LET count=FSINSPECT.Snapshot(rows,FSINSPECT.CAPACITY)
  ShellText(output,c"MOUNT FILESYSTEM ACCESS    STATE")
  ShellByte(output,ASCII.LF)
  IF count=0 THEN
    ShellText(output,c"No mounted filesystems")
    ShellByte(output,ASCII.LF)
    RETURN
  FI

  FOR index=0 TO count-1 DO
    ShellText(output,CSTRING(@rows(index).name(0)))
    ShellByte(output,CHAR_COLON)
    width=ShellLength(rows(index).name)+1
    WHILE width<5 DO
      ShellByte(output,ASCII.SPACE)
      width==+1
    OD

    ShellByte(output,ASCII.SPACE)
    CASE rows(index).format OF
    WHEN FSFORMATS.MYDOS THEN
      ShellText(output,c"MyDOS      ")

    WHEN FSFORMATS.SDFS THEN
      ShellText(output,c"SDFS       ")

    ELSE
      ShellText(output,c"unknown    ")
    ESAC

    IF rows(index).readOnly<>0 THEN
      ShellText(output,c"read-only ")

    ELSE
      ShellText(output,c"writable  ")
    FI

    IF rows(index).offline<>0 THEN
      ShellText(output,c"offline")

    ELSE
      ShellText(output,c"mounted")
    FI

    ShellByte(output,ASCII.LF)
    IF shell.status<>PROCESS.RETURN_OK THEN
      EXIT
    FI
  OD

RETURN
