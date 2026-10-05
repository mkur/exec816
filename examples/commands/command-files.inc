; Shared command-side file ownership; routines use resident COMMAND services.
; A missing filename borrows Input; an explicit empty filename is an error.
BYTE POINTER FUNC CommandInput(ADDRESS name)

  IF COMMAND.BreakPending()<>0 THEN
    COMMAND.SetIoErr(COMMAND.ERROR_BREAK)
    RETURN(NULL)
  FI

  IF name=0 THEN
    RETURN(COMMAND.Input())
  FI

  LET path=BYTE POINTER(name)
  IF path(0)=ASCII.NUL THEN
    COMMAND.SetIoErr(COMMAND.ERROR_INVALID_COMPONENT_NAME)
    RETURN(NULL)
  FI

RETURN(COMMAND.Open(path,COMMAND.MODE_OLDFILE))

; Release only owned input, preserving the operation's original failure.
LONGINT FUNC CommandFinish(BYTE POINTER input BYTE owned LONGINT status)
  LONGINT cause

  cause=IF status>=COMMAND.RETURN_ERROR THEN COMMAND.IoErr() ELSE LONGINT(0) FI
  IF owned<>0 AND input<>NULL THEN
    BEGIN
      LET closed=COMMAND.Close(input)
      IF closed=0 AND cause=0 THEN
        cause=COMMAND.IoErr()
        IF cause=0 THEN
          cause=COMMAND.ERROR_BAD_STREAM_NAME
        FI

        status=COMMAND.RETURN_ERROR
      FI
    END
  FI

  COMMAND.SetIoErr(cause)

RETURN(status)
