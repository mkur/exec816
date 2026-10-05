; Return to the shell's default streams after a command or failed redirection.
; Borrowed defaults must be restored before temporary handles can be released.
BYTE FUNC ShellCloseTemporary(DOS.FileHandle POINTER handle)

  IF DOS.Close(handle)<>0 THEN
    RETURN(1)
  FI

  LET error=DOS.IoErr()
  IF DOSOBJECTS.Find(DOSCORE.Current(),BYTE POINTER(handle),
      DOSOBJECTS.KIND_FILE)<>NULL THEN
    ShellFail(PROCESS.RETURN_FAIL,error)
    RETURN(0)
  FI

  ; A terminal disk Close consumes its wrapper even on failure. Preserve an
  ; earlier command failure; otherwise report finalization failure and allow
  ; another prompt without retrying through the freed handle.
  IF shell.status<PROCESS.RETURN_ERROR THEN
    shell.status=PROCESS.RETURN_FAIL
    shell.error=error
  FI

RETURN(1)

PROC ShellUnredirect()
  DOS.FileHandle POINTER ignored
  BYTE failed

  IF shell.redirectActive=0 THEN
    RETURN
  FI

  failed=0
  IF shell.redirectActive=2 THEN
    ignored=DOS.SelectInput(shell.oldInput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
      failed=1
    FI

    ignored=DOS.SelectOutput(shell.oldOutput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
      failed=1
    FI

    IF failed<>0 THEN
      shell.restoreFailure=1
      RETURN
    FI

    shell.redirectActive=1
    shell.restoreFailure=0
  FI

  IF shell.tempOutput<>NULL THEN
    IF ShellCloseTemporary(shell.tempOutput)<>0 THEN
      shell.tempOutput=NULL
    FI
  FI

  IF shell.tempInput<>NULL THEN
    IF ShellCloseTemporary(shell.tempInput)<>0 THEN
      shell.tempInput=NULL
    FI
  FI

  IF shell.tempInput=NULL
    AND shell.tempOutput=NULL THEN
    shell.redirectActive=0
    shell.oldInput=NULL
    shell.oldOutput=NULL
  FI

RETURN

; Give this command its requested input and output while retaining enough
; ownership information to restore the shell even if setup fails partway.
BYTE FUNC ShellRedirect()
  DOS.FileHandle POINTER ignored

  IF shell.inputRedirect=NO_REDIRECT AND shell.outputRedirect=NO_REDIRECT THEN
    RETURN(1)
  FI

  LET line=ShellLine()
  shell.oldInput=DOS.Input()
  shell.oldOutput=DOS.Output()
  shell.redirectActive=1
  IF shell.inputRedirect<>NO_REDIRECT THEN
    shell.tempInput=DOS.Open(line+SIZE(shell.inputRedirect),DOS.MODE_OLDFILE)
    IF shell.tempInput=NULL THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN(0)
    FI
  FI

  IF shell.outputRedirect<>NO_REDIRECT THEN
    shell.tempOutput=DOS.Open(line+SIZE(shell.outputRedirect),DOS.MODE_NEWFILE)
    IF shell.tempOutput=NULL THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN(0)
    FI
  FI

  ; Complete all opens against the pre-command directory before either selector.
  shell.redirectActive=2
  IF shell.tempInput<>NULL THEN
    ignored=DOS.SelectInput(shell.tempInput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN(0)
    FI
  FI

  IF shell.tempOutput<>NULL THEN
    ignored=DOS.SelectOutput(shell.tempOutput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN(0)
    FI
  FI

RETURN(1)
