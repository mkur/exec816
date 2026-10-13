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

; Stream one complete row from the drawing buffer, separate from the scratch FIB.
PROC ShellDirRow(DOS.FileInfoBlock POINTER info)
  CARD used
  LONGCARD magnitude

  LET buffer=ShellDrawBuffer()
  LET name=BYTE POINTER(@info.fib_FileName(0))
  used=STR.strnlen(name,32)
  ; Include the bound marker, sign, ten digits, LF and temporary NUL.
  IF used+16>DRAW_CAPACITY THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.ERROR_BAD_NUMBER)
    RETURN
  FI

  A816MEMORY.Move(buffer,name,SIZE(used))
  IF info.fib_DirEntryType>0 THEN
    buffer(used)=CHAR_SLASH
    used==+1

  ELSE
    buffer(used)=ASCII.SPACE
    used==+1
    IF (info.fib_InfoFlags & (DOS.FIB_SIZE_EXACT OR DOS.FIB_SIZE_BOUND))=0 THEN
      buffer(used)='?
      used==+1
    ELSE
      BEGIN
        IF (info.fib_InfoFlags & DOS.FIB_SIZE_BOUND)<>0 THEN
          buffer(used)='<
          buffer(used+1)='=
          used==+2
        FI

        IF info.fib_Size<0 THEN
          magnitude=LONGCARD(-(info.fib_Size+1))+1
          buffer(used)=CHAR_MINUS
          used==+1
        ELSE
          magnitude=LONGCARD(info.fib_Size)
        FI

        used==+STR.u32toa(magnitude,buffer+SIZE(used),DRAW_CAPACITY-used-1)
      END
    FI
  FI

  buffer(used)=ASCII.LF
  ShellWrite(DOS.Output(),buffer,used+1)

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

        ShellDirRow(info)
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
    IF ShellCloseTemporary(shell.commandInput)<>0 THEN
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
PROC ShellMemRow(DOS.FileHandle POINTER output CSTRING label LONGCARD flags)

  LET used=ShellRowText(output,0,label)
  ShellRowEnd(output,ShellRowNumber(output,used,LONGINT(EXEC.AvailMem(flags))))

RETURN

PROC ShellMem()

  LET output=DOS.Output()
  ShellMemRow(output,c"ordinary total ",0)
  ShellMemRow(output,c"ordinary largest ",EXEC.MEMF_LARGEST)
  ShellMemRow(output,c"linear total ",EXEC.MEMF_LINEAR)
  ShellMemRow(output,c"linear largest ",EXEC.MEMF_LINEAR OR EXEC.MEMF_LARGEST)

RETURN

; Give task states readable, consistently sized labels for the TASKS listing.
CSTRING FUNC ShellTaskState(BYTE state)

  CASE state OF
  WHEN TASKINSPECT.STATE_RUNNING THEN
    RETURN(c"RUNNING ")

  WHEN TASKINSPECT.STATE_READY THEN
    RETURN(c"READY   ")

  WHEN TASKINSPECT.STATE_SIGNAL_WAIT THEN
    RETURN(c"WAITING ")

  WHEN TASKINSPECT.STATE_SLEEPING THEN
    RETURN(c"SLEEPING")

  ELSE
    RETURN(c"UNKNOWN ")
  ESAC

RETURN(c"UNKNOWN ")

; Show a snapshot of live tasks without holding up scheduling during output.
PROC ShellTasks(DOS.FileHandle POINTER output)
  CARD index,used

  ; 26 bytes per slot, at most 16 configured slots: fits the existing 512 bytes.
  ; Snapshot releases Forbid before any DOS output can block.
  LET rows=TASKINSPECT.Info POINTER(ShellTransfer())
  LET count=TASKINSPECT.Snapshot(rows,TASKINSPECT.CAPACITY)
  ShellLineText(output,c"SLOT STATE    NAME")
  IF count=0 THEN
    RETURN
  FI

  FOR index=0 TO count-1 DO
    used=ShellRowNumber(output,0,rows(index).slot)
    IF rows(index).slot<10 THEN
      used=ShellRowByte(output,used,ASCII.SPACE)
    FI

    used=ShellRowText(output,used,c"   ")
    used=ShellRowText(output,used,ShellTaskState(rows(index).state))
    used=ShellRowByte(output,used,ASCII.SPACE)
    IF rows(index).name(0)=ASCII.NUL THEN
      used=ShellRowText(output,used,c"(unnamed)")
    ELSE
      used=ShellRowText(output,used,CSTRING(@rows(index).name(0)))
    FI

    ShellRowEnd(output,used)
    IF shell.status<>PROCESS.RETURN_OK THEN
      EXIT
    FI
  OD

RETURN

; Show which resident devices are available and their lifecycle state.
PROC ShellDevices(DOS.FileHandle POINTER output)
  CARD index,used
  CSTRING label

  LET rows=DEVICEINSPECT.Info POINTER(ShellTransfer())
  LET count=DEVICEINSPECT.Snapshot(rows,DEVICEINSPECT.CAPACITY)
  ShellLineText(output,c"DEVICE          STATE")
  IF count=0 THEN
    RETURN
  FI

  FOR index=0 TO count-1 DO
    used=0
    CASE rows(index).kind OF
    WHEN DEVICEINSPECT.CONSOLE THEN
      used=ShellRowText(output,used,c"console.device  ")

    WHEN DEVICEINSPECT.SIO THEN
      used=ShellRowText(output,used,c"sio.device      ")

    WHEN DEVICEINSPECT.IDEPLUS THEN
      used=ShellRowText(output,used,c"ideplus.device  ")

    WHEN DEVICEINSPECT.TIMER THEN
      used=ShellRowText(output,used,c"timer.device    ")
    ESAC

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

    used=ShellRowText(output,used,label)
    ShellRowEnd(output,used)
    IF shell.status<>PROCESS.RETURN_OK THEN
      EXIT
    FI
  OD

RETURN

; Show mounted filesystems, their access mode and whether they are online.
PROC ShellMounts(DOS.FileHandle POINTER output)
  CARD index,used

  LET rows=FSINSPECT.Info POINTER(ShellTransfer())
  LET count=FSINSPECT.Snapshot(rows,FSINSPECT.CAPACITY)
  ShellLineText(output,c"MOUNT FILESYSTEM ACCESS    STATE DEVICE/UNIT")
  IF count=0 THEN
    ShellLineText(output,c"No mounted filesystems")
    ShellMountFailure(output)
    RETURN
  FI

  FOR index=0 TO count-1 DO
    used=ShellRowText(output,0,CSTRING(@rows(index).name(0)))
    used=ShellRowByte(output,used,CHAR_COLON)
    WHILE used<5 DO
      used=ShellRowByte(output,used,ASCII.SPACE)
    OD

    used=ShellRowByte(output,used,ASCII.SPACE)
    CASE rows(index).format OF
    WHEN FSFORMATS.MYDOS THEN
      used=ShellRowText(output,used,c"MyDOS      ")

    WHEN FSFORMATS.SDFS THEN
      used=ShellRowText(output,used,c"SDFS       ")

    WHEN FSFORMATS.RAM THEN
      used=ShellRowText(output,used,c"RAM        ")

    ELSE
      used=ShellRowText(output,used,c"unknown    ")
    ESAC

    IF rows(index).readOnly<>0 THEN
      used=ShellRowText(output,used,c"read-only ")
    ELSE
      used=ShellRowText(output,used,c"writable  ")
    FI

    IF rows(index).offline<>0 THEN
      used=ShellRowText(output,used,c"offline")
    ELSE
      used=ShellRowText(output,used,c"mounted")
    FI

    IF rows(index).format<>FSFORMATS.RAM THEN
      used=ShellRowByte(output,used,ASCII.SPACE)
      IF rows(index).backend=BLOCKTYPES.BACKEND_IDEPLUS THEN
        used=ShellRowText(output,used,c"ideplus.device/")
        used=ShellRowNumber(output,used,LONGINT(rows(index).unit))
      ELSE
        used=ShellRowText(output,used,c"sio.device/D")
        used=ShellRowNumber(output,used,LONGINT(rows(index).unit-48))
      FI
    FI

    ShellRowEnd(output,used)
    IF rows(index).offline<>0 AND rows(index).error<>0 THEN
      used=ShellRowText(output,0,c"  ")
      ShellMountError(output,used,rows(index).error)
    FI

    IF shell.status<>PROCESS.RETURN_OK THEN
      EXIT
    FI
  OD

  ShellMountFailure(output)

RETURN
