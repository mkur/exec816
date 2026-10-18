; Return to the shell's default streams after a command or failed redirection.
; Borrowed defaults must be restored before temporary handles can be released.
BYTE FUNC ShellCloseTemporary(ShellContext POINTER context
    DOS.FileHandle POINTER handle)

  IF DOS.Close(handle)<>0 THEN
    RETURN(1)
  FI

  LET error=DOS.IoErr()
  IF DOSOBJECTS.Find(DOSCORE.Current(),BYTE POINTER(handle),
      DOSOBJECTS.KIND_FILE)<>NULL THEN
    ShellFail(context,PROCESS.RETURN_FAIL,error)
    RETURN(0)
  FI

  ; A terminal disk Close consumes its wrapper even on failure. Preserve an
  ; earlier command failure; otherwise report finalization failure and allow
  ; another prompt without retrying through the freed handle.
  IF context.shell.status<PROCESS.RETURN_ERROR THEN
    context.shell.status=PROCESS.RETURN_FAIL
    context.shell.error=error
  FI

RETURN(1)

PROC ShellUnredirect(ShellContext POINTER context)
  DOS.FileHandle POINTER ignored
  BYTE failed

  IF context.shell.redirectActive=0 THEN
    RETURN
  FI

  failed=0
  IF context.shell.redirectActive=2 THEN
    ignored=DOS.SelectInput(context.shell.oldInput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
      failed=1
    FI

    ignored=DOS.SelectOutput(context.shell.oldOutput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
      failed=1
    FI

    IF failed<>0 THEN
      context.shell.restoreFailure=1
      RETURN
    FI

    context.shell.redirectActive=1
    context.shell.restoreFailure=0
  FI

  IF context.shell.tempOutput<>NULL THEN
    IF ShellCloseTemporary(context,context.shell.tempOutput)<>0 THEN
      context.shell.tempOutput=NULL
    FI
  FI

  IF context.shell.tempInput<>NULL THEN
    IF ShellCloseTemporary(context,context.shell.tempInput)<>0 THEN
      context.shell.tempInput=NULL
    FI
  FI

  IF context.shell.tempInput=NULL
    AND context.shell.tempOutput=NULL THEN
    context.shell.redirectActive=0
    context.shell.oldInput=NULL
    context.shell.oldOutput=NULL
  FI

RETURN

; Give this command its requested input and output while retaining enough
; ownership information to restore the shell even if setup fails partway.
BYTE FUNC ShellRedirect(ShellContext POINTER context)
  DOS.FileHandle POINTER ignored

  IF context.shell.background=0 AND context.shell.inputRedirect=NO_REDIRECT
      AND context.shell.outputRedirect=NO_REDIRECT THEN
    RETURN(1)
  FI

  LET line=ShellLine(context)
  context.shell.oldInput=DOS.Input()
  context.shell.oldOutput=DOS.Output()
  context.shell.redirectActive=1
  IF context.shell.inputRedirect<>NO_REDIRECT THEN
    context.shell.tempInput=DOS.Open(line+SIZE(context.shell.inputRedirect),DOS.MODE_OLDFILE)
    IF context.shell.tempInput=NULL THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN(0)
    FI
  ELSEIF context.shell.background<>0 THEN
    context.shell.tempInput=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
    IF context.shell.tempInput=NULL THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN(0)
    FI
  FI

  IF context.shell.outputRedirect<>NO_REDIRECT THEN
    BEGIN
      LET mode=IF context.shell.outputAppend<>0 THEN DOS.MODE_READWRITE
          ELSE DOS.MODE_NEWFILE FI
      context.shell.tempOutput=DOS.Open(line+SIZE(context.shell.outputRedirect),mode)
      IF context.shell.tempOutput=NULL THEN
        ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
        RETURN(0)
      FI

      IF context.shell.outputAppend<>0 THEN
        IF DOS.Seek(context.shell.tempOutput,0,DOS.OFFSET_END)<0 THEN
          ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
          RETURN(0)
        FI
      FI
    END
  FI

  IF context.shell.background<>0 THEN
    IF context.shell.tempOutput=NULL THEN
      context.shell.tempOutput=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
      IF context.shell.tempOutput=NULL THEN
        ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
        RETURN(0)
      FI
    FI

    IF DOS.IsInteractive(context.shell.tempInput)<>0 OR DOS.IsInteractive(context.shell.tempOutput)<>0 THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_WRONG_TYPE)
      RETURN(0)
    FI
  FI

  ; Complete all opens and positioning before either selector.
  context.shell.redirectActive=2
  IF context.shell.tempInput<>NULL THEN
    ignored=DOS.SelectInput(context.shell.tempInput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN(0)
    FI
  FI

  IF context.shell.tempOutput<>NULL THEN
    ignored=DOS.SelectOutput(context.shell.tempOutput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN(0)
    FI
  FI

RETURN(1)
