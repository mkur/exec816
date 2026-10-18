; Resident entry startup. Shared command fixtures use ShellStart directly.
BYTE ARRAY bootShellName=c"shell"
BYTE ARRAY bootControllerName=c"shell controller"
BYTE bootScriptsReady

; Optional cache allocation failure should be visible without losing the shell.
PROC ShellCacheStatus(ShellContext POINTER context)
  FSINSPECT.CacheInfo cache

  IF FSINSPECT.CacheStatus(@cache)<>0 THEN
    IF cache.requested<>0 AND cache.blocks=0 THEN
      ShellByte(context,context.shell.console,ASCII.LF)
      ShellText(context,context.shell.console,c"cache: allocation failed; using one sector")
    FI
  FI

RETURN

; Settle configured IDE discovery before mounting filesystems. Later device
; opens join the ready driver; an unconfigured controller is left untouched.
PROC ShellBootIde(ShellContext POINTER context)
  BYTE index,ready

  LET registry=DOSCORE.GetRegistry()
  LET specs=FSTYPES.Spec POINTER(registry.config)
  IF registry.count=0 THEN
    RETURN
  FI

  FOR index=0 TO registry.count-1 DO
    IF (registry.enabled & (CARD(1) LSH index))<>0 AND
        specs(index).backend=BLOCKTYPES.BACKEND_IDEPLUS THEN
      ready=IDEPLUSDRIVER.Start()
      IF BOOTCONFIG.Verbose()<>0 THEN
        ShellIdeDiagnostics(context,context.shell.console,0)
      FI

      RETURN
    FI
  OD

RETURN

; Missing startup files are optional. Other setup and execution errors retain
; normal EXECUTE results; the first interactive prompt must not report twice.
PROC ShellStartupFile(ShellContext POINTER context BYTE POINTER path)

  LET primary=context.shell.status
  LET secondary=context.shell.error
  context.shell.status=PROCESS.RETURN_OK
  context.shell.error=0
  context.shell.command=CMD_EXECUTE
  context.shell.argc=1
  context.shell.words(0).text=path
  context.shell.diagnosticWord=0
  IF ShellPoll(context)=0 THEN
    IF ShellScope(context)<>0 THEN
      ShellScriptOpen(context,path,1)
    FI
  FI

  IF context.script=NULL AND context.shell.status=PROCESS.RETURN_OK THEN
    context.shell.status=primary
    context.shell.error=secondary
  ELSE
    ShellDiagnostic(context)
  FI

  ShellRunScript(context)
  ShellClear(context)

RETURN

; Startup scripts belong only to the first admitted shell Process.
PROC ShellBootScripts(ShellContext POINTER context)

  ShellStartupFile(context,BYTE POINTER(c"S:STARTUP"))
  IF context.shell.done=0 AND context.shell.status<PROCESS.RETURN_ERROR THEN
    ShellStartupFile(context,BYTE POINTER(c"S:USER"))
  FI

RETURN

; Present system startup and establish services/assignments before spawning.
; A disk startup failure still leaves the console usable when possible.
BYTE FUNC ShellSystemStart(ShellContext POINTER context BYTE POINTER consoleName)

  IF ShellOpen(context,consoleName)=0 THEN
  BEGIN
    LET reason=IF context.shell=NULL THEN CARD(DOS.ERROR_NO_FREE_STORE)
        ELSE CARD(context.shell.error) FI
    BOOTDIAG.Halt(reason)
  END
  FI

  IF BOOTCONFIG.Verbose()<>0 THEN
    ShellText(context,context.shell.console,c"\rCONSOLE       =OK\nSHELL         =LAUNCHED\n")
    IF context.shell.status<>PROCESS.RETURN_OK THEN
      BOOTDIAG.Halt(CARD(context.shell.error))
    FI
  FI

  BOOTDIAG.Complete()
  LET self=EXEC.FindTask(NULL)
  EXEC.Forbid()
  self.tc_Node.ln_Name=bootControllerName
  EXEC.Permit()

  ShellByte(context,context.shell.console,ASCII.LF)
  ShellText(context,context.shell.console,CSTRING(EXECBUILD.banner))
  ShellText(context,context.shell.console,CSTRING(EXECBUILD.slots))
  ShellText(context,context.shell.console,CSTRING(EXECBUILD.stackChecks))
  ShellText(context,context.shell.console,c"console.device: ready")
  ShellByte(context,context.shell.console,ASCII.LF)
  IF context.shell.status<>PROCESS.RETURN_OK THEN
    RETURN(0)
  FI

  IF BOOTCONFIG.Status()<>0 THEN
    ShellText(context,context.shell.console,c"boot: invalid settings; using defaults")
    ShellByte(context,context.shell.console,ASCII.LF)
  FI

  ShellBootIde(context)
  ShellText(context,context.shell.console,CSTRING(EXECBUILD.mountStart))
  IF context.shell.status<>PROCESS.RETURN_OK THEN
    RETURN(0)
  FI

  ShellChange(context,shellRoot)
  IF context.shell.status=PROCESS.RETURN_OK THEN
    ShellText(context,context.shell.console,CSTRING(EXECBUILD.systemReady))
    IF BOOTCONFIG.SystemDrive()<>0 THEN
      ShellByte(context,context.shell.console,ASCII.DIGIT_ZERO+BOOTCONFIG.SystemDrive())
    FI
    IF FSINSPECT.SystemWritable()<>0 THEN
      ShellText(context,context.shell.console,c": ready, read-write")
    ELSE
      ShellText(context,context.shell.console,c": ready, read-only")
    FI

    ; Filesystem startup publishes all configured volumes before SYS resolves.
    ShellText(context,context.shell.console,CSTRING(EXECBUILD.otherMountsReady))
    ShellCacheStatus(context)

    ; Publish the command directory through the ordinary, replaceable ASSIGN.
    IF DOS.AssignPath(BYTE POINTER(c"C"),BYTE POINTER(c"SYS:C"))=0 THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
      ShellByte(context,context.shell.console,ASCII.LF)
      ShellText(context,context.shell.console,c"C: assignment failed")
    FI

  ELSE
    ShellByte(context,context.shell.console,ASCII.LF)
    ShellMountFailure(context,context.shell.console)
    ShellText(context,context.shell.console,CSTRING(EXECBUILD.mountFailure))
  FI

  ShellByte(context,context.shell.console,ASCII.LF)
  ShellByte(context,context.shell.console,ASCII.LF)
  ShellDiagnostic(context)
  IF context.shell.status=PROCESS.RETURN_OK THEN
    ; Publish the optional script directory once. Older disks may omit it.
    IF DOS.AssignPath(BYTE POINTER(c"S"),BYTE POINTER(c"SYS:S"))<>0 THEN
      bootScriptsReady=1
    ELSE
      BEGIN
        LET error=DOS.IoErr()
        IF error<>DOS.ERROR_OBJECT_NOT_FOUND THEN
          context.shell.diagnosticWord=$ff
          ShellFail(context,PROCESS.RETURN_ERROR,error)
          ShellDiagnostic(context)
        FI
      END
    FI
  FI

  context.shell.lastStatus=context.shell.status
  context.shell.lastError=context.shell.error
  ShellClear(context)

RETURN(context.shell.done=0)
