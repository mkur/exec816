; Resident entry startup. Shared command fixtures use ShellStart directly.
BYTE ARRAY bootShellName=c"shell"

; Optional cache allocation failure should be visible without losing the shell.
PROC ShellCacheStatus()
  FSINSPECT.CacheInfo cache

  IF FSINSPECT.CacheStatus(@cache)<>0 THEN
    IF cache.requested<>0 AND cache.blocks=0 THEN
      ShellByte(shell.console,ASCII.LF)
      ShellText(shell.console,c"cache: allocation failed; using one sector")
    FI
  FI

RETURN

; Bring the resident disk device online for the selected system drive.
; Filesystem access is responsible for the later disk operations.
BYTE FUNC ShellBootSIO()

  LET port=EXEC.CreateMsgPort()
  IF port=NULL THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
    RETURN(0)
  FI

  LET request=EXEC.CreateIORequest(port,EXEC.IOSIOREQ_SIZE)
  IF request=NULL THEN
    EXEC.DeleteMsgPort(port)
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
    RETURN(0)
  FI

  ; Opening starts the resident worker but sends no command to the disk.
  LET device=c"sio.device"
  LET error=EXEC.OpenDevice(BYTE POINTER(device),FSSYSTEM.SystemUnit(),request,0)
  IF error=0 THEN
    EXEC.CloseDevice(request)
  FI

  EXEC.DeleteIORequest(request)
  EXEC.DeleteMsgPort(port)
  IF error<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,error)
    RETURN(0)
  FI

RETURN(1)

; Present system startup and prepare an interactive shell on the system volume.
; A disk startup failure still leaves the console usable when possible.
BYTE FUNC ShellBootStart(BYTE POINTER consoleName)

  IF ShellOpen(consoleName)=0 THEN
    RETURN(0)
  FI

  LET self=EXEC.FindTask(NULL)
  EXEC.Forbid()
  self.tc_Node.ln_Name=bootShellName
  EXEC.Permit()

  ShellText(shell.console,CSTRING(EXECBUILD.banner))
  ShellText(shell.console,CSTRING(EXECBUILD.slots))
  ShellText(shell.console,CSTRING(EXECBUILD.stackChecks))
  ShellText(shell.console,c"console.device: ready")
  ShellByte(shell.console,ASCII.LF)
  IF shell.status<>PROCESS.RETURN_OK THEN
    RETURN(0)
  FI

  IF FSSYSTEM.SystemUnit()<>0 THEN
    IF ShellBootSIO()=0 THEN
      ShellText(shell.console,c"sio.device: initialization failed")
      ShellByte(shell.console,ASCII.LF)
      ShellInitialPrompt()
      RETURN(shell.done=0)
    FI

    ShellText(shell.console,c"sio.device: D")
    ShellByte(shell.console,ASCII.DIGIT_ZERO+BOOTCONFIG.SystemDrive())
    ShellText(shell.console,CSTRING(EXECBUILD.sioReady))
  FI

  IF shell.status<>PROCESS.RETURN_OK THEN
    RETURN(0)
  FI

  IF BOOTCONFIG.Status()<>0 THEN
    ShellText(shell.console,c"boot: invalid settings; using defaults")
    ShellByte(shell.console,ASCII.LF)
  FI

  ShellText(shell.console,CSTRING(EXECBUILD.mountStart))
  IF shell.status<>PROCESS.RETURN_OK THEN
    RETURN(0)
  FI

  ShellChange(shellRoot)
  IF shell.status=PROCESS.RETURN_OK THEN
    ShellText(shell.console,c"SYS: -> D")
    ShellByte(shell.console,ASCII.DIGIT_ZERO+BOOTCONFIG.SystemDrive())
    IF FSINSPECT.SystemWritable()<>0 THEN
      ShellText(shell.console,c": ready, read-write")
    ELSE
      ShellText(shell.console,c": ready, read-only")
    FI
    ShellCacheStatus()

    ; Publish the command directory through the ordinary, replaceable ASSIGN.
    IF DOS.AssignPath(BYTE POINTER(c"C"),BYTE POINTER(c"SYS:C"))=0 THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
      ShellByte(shell.console,ASCII.LF)
      ShellText(shell.console,c"C: assignment failed")
    FI

  ELSE
    ShellText(shell.console,CSTRING(EXECBUILD.mountFailure))
  FI

  ShellByte(shell.console,ASCII.LF)
  ShellByte(shell.console,ASCII.LF)
  ShellInitialPrompt()

RETURN(shell.done=0)
