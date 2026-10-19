; Open one script independently of command Input. Transfer outer redirection
; ownership so each script command can temporarily override inherited streams.
PROC ShellScriptOpen(ShellContext POINTER context
    BYTE POINTER path BYTE optional)

  context.script=ShellScript POINTER(EXEC.AllocMem(SIZEOF(ShellScript),
      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
  IF context.script=NULL THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
    RETURN
  FI

  context.script.source=DOS.Open(path,DOS.MODE_OLDFILE)
  IF context.script.source=NULL THEN
    BEGIN
      LET error=DOS.IoErr()
      IF optional<>0 AND error=DOS.ERROR_OBJECT_NOT_FOUND THEN
        EXEC.FreeMem(BYTE POINTER(context.script),SIZEOF(ShellScript))
        context.script=NULL
      ELSE
        ShellFail(context,PROCESS.RETURN_ERROR,error)
      FI
    END

    RETURN
  FI

  LET interactive=DOS.IsInteractive(context.script.source)
  LET error=DOS.IoErr()
  IF error<>0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  IF interactive<>0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_WRONG_TYPE)
    RETURN
  FI

  context.script.oldInput=context.shell.oldInput
  context.script.oldOutput=context.shell.oldOutput
  context.script.tempInput=context.shell.tempInput
  context.script.tempOutput=context.shell.tempOutput
  context.script.redirectActive=context.shell.redirectActive
  context.shell.redirectActive=0
  context.shell.oldInput=NULL
  context.shell.oldOutput=NULL
  context.shell.tempInput=NULL
  context.shell.tempOutput=NULL

RETURN

; Assemble one bounded line into the shell's existing command buffer. Retain
; unread bytes separately because dispatch overwrites all shared workspaces.
BYTE FUNC ShellScriptLine(ShellContext POINTER context)
  BYTE value

  ShellClear(context)
  LET line=ShellLine(context)
  DO
    IF ShellPoll(context)<>0 THEN
      RETURN(0)
    FI

    IF context.script.used=context.script.available THEN
      BEGIN
        LET count=DOS.Read(context.script.source,@context.script.bytes(0),READ_CHUNK_SIZE)
        LET error=DOS.IoErr()
        IF count<0 OR error<>0 THEN
          ShellFail(context,PROCESS.RETURN_ERROR,
              IF error<>0 THEN error ELSE LONGINT(DOS.ERROR_BAD_NUMBER) FI)
          RETURN(0)
        FI

        IF count=0 THEN
          RETURN(context.shell.length<>0)
        FI

        context.script.used=0
        context.script.available=CARD(count)
      END
    FI

    value=context.script.bytes(context.script.used)
    context.script.used==+1
    IF context.script.previousCR<>0 AND value=ASCII.LF THEN
      context.script.previousCR=0
    ELSE
      context.script.previousCR=0
      IF value=ASCII.CR OR value=ASCII.LF OR value=ASCII.ATASCII_EOL THEN
        context.script.previousCR=value=ASCII.CR
        RETURN(1)
      FI

      ; Reject the entire line rather than executing a prefix before NUL or
      ; an overlong suffix. The script stops at the first such input error.
      IF value=ASCII.NUL THEN
        ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BAD_NUMBER)
        RETURN(0)
      FI

      IF context.shell.length=LINE_LIMIT THEN
        ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_LINE_TOO_LONG)
        RETURN(0)
      FI

      line(context.shell.length)=value
      context.shell.length==+1
      line(context.shell.length)=ASCII.NUL
    FI
  OD

RETURN(0)

; Ignore empty lines and full-line semicolon comments, including indentation.
BYTE FUNC ShellScriptNext(ShellContext POINTER context)
  CARD index

  LET line=ShellLine(context)
  WHILE ShellScriptLine(context)<>0 DO
    index=0
    WHILE line(index)=ASCII.SPACE OR line(index)=ASCII.TAB DO
      index==+1
    OD

    IF line(index)<>ASCII.NUL AND line(index)<>CHAR_SEMICOLON THEN
      RETURN(1)
    FI
  OD

RETURN(0)

; Settle any command override, close the owned source, then restore borrowed
; outer streams before closing the script's inherited temporary handles.
PROC ShellScriptClose(ShellContext POINTER context)

  IF context.script=NULL THEN
    RETURN
  FI

  ShellUnredirect(context)
  IF context.shell.redirectActive<>0 THEN
    RETURN
  FI

  IF context.script.source<>NULL THEN
    IF ShellCloseTemporary(context,context.script.source)=0 THEN
      RETURN
    FI

    context.script.source=NULL
  FI

  IF context.script.redirectActive<>0 THEN
    context.shell.oldInput=context.script.oldInput
    context.shell.oldOutput=context.script.oldOutput
    context.shell.tempInput=context.script.tempInput
    context.shell.tempOutput=context.script.tempOutput
    context.shell.redirectActive=context.script.redirectActive
    context.script.redirectActive=0
    ShellUnredirect(context)
    IF context.shell.redirectActive<>0 THEN
      RETURN
    FI
  FI

  EXEC.FreeMem(BYTE POINTER(context.script),SIZEOF(ShellScript))
  context.script=NULL

RETURN
