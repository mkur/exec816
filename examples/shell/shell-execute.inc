; Open one script independently of command Input. Transfer outer redirection
; ownership so each script command can temporarily override inherited streams.
PROC ShellScriptOpen(BYTE POINTER path BYTE optional)

  script=ShellScript POINTER(EXEC.AllocMem(SIZEOF(ShellScript),
      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
  IF script=NULL THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
    RETURN
  FI

  script.source=DOS.Open(path,DOS.MODE_OLDFILE)
  IF script.source=NULL THEN
    BEGIN
      LET error=DOS.IoErr()
      IF optional<>0 AND error=DOS.ERROR_OBJECT_NOT_FOUND THEN
        EXEC.FreeMem(BYTE POINTER(script),SIZEOF(ShellScript))
        script=NULL
      ELSE
        ShellFail(PROCESS.RETURN_ERROR,error)
      FI
    END

    RETURN
  FI

  LET interactive=DOS.IsInteractive(script.source)
  LET error=DOS.IoErr()
  IF error<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  IF interactive<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_WRONG_TYPE)
    RETURN
  FI

  script.oldInput=shell.oldInput
  script.oldOutput=shell.oldOutput
  script.tempInput=shell.tempInput
  script.tempOutput=shell.tempOutput
  script.redirectActive=shell.redirectActive
  shell.redirectActive=0
  shell.oldInput=NULL
  shell.oldOutput=NULL
  shell.tempInput=NULL
  shell.tempOutput=NULL

RETURN

; Assemble one bounded line into the shell's existing command buffer. Retain
; unread bytes separately because dispatch overwrites all shared workspaces.
BYTE FUNC ShellScriptLine()
  BYTE value

  ShellClear()
  LET line=ShellLine()
  DO
    IF ShellPoll()<>0 THEN
      RETURN(0)
    FI

    IF script.used=script.available THEN
      BEGIN
        LET count=DOS.Read(script.source,@script.bytes(0),READ_CHUNK_SIZE)
        LET error=DOS.IoErr()
        IF count<0 OR error<>0 THEN
          ShellFail(PROCESS.RETURN_ERROR,
              IF error<>0 THEN error ELSE LONGINT(DOS.ERROR_BAD_NUMBER) FI)
          RETURN(0)
        FI

        IF count=0 THEN
          RETURN(shell.length<>0)
        FI

        script.used=0
        script.available=CARD(count)
      END
    FI

    value=script.bytes(script.used)
    script.used==+1
    IF script.previousCR<>0 AND value=ASCII.LF THEN
      script.previousCR=0
    ELSE
      script.previousCR=0
      IF value=ASCII.CR OR value=ASCII.LF OR value=ASCII.ATASCII_EOL THEN
        script.previousCR=value=ASCII.CR
        RETURN(1)
      FI

      ; Reject the entire line rather than executing a prefix before NUL or
      ; an overlong suffix. The script stops at the first such input error.
      IF value=ASCII.NUL THEN
        ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BAD_NUMBER)
        RETURN(0)
      FI

      IF shell.length=LINE_LIMIT THEN
        ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_LINE_TOO_LONG)
        RETURN(0)
      FI

      line(shell.length)=value
      shell.length==+1
      line(shell.length)=ASCII.NUL
    FI
  OD

RETURN(0)

; Ignore empty lines and full-line semicolon comments, including indentation.
BYTE FUNC ShellScriptNext()
  CARD index

  LET line=ShellLine()
  WHILE ShellScriptLine()<>0 DO
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
PROC ShellScriptClose()

  IF script=NULL THEN
    RETURN
  FI

  ShellUnredirect()
  IF shell.redirectActive<>0 THEN
    RETURN
  FI

  IF script.source<>NULL THEN
    IF ShellCloseTemporary(script.source)=0 THEN
      RETURN
    FI

    script.source=NULL
  FI

  IF script.redirectActive<>0 THEN
    shell.oldInput=script.oldInput
    shell.oldOutput=script.oldOutput
    shell.tempInput=script.tempInput
    shell.tempOutput=script.tempOutput
    shell.redirectActive=script.redirectActive
    script.redirectActive=0
    ShellUnredirect()
    IF shell.redirectActive<>0 THEN
      RETURN
    FI
  FI

  EXEC.FreeMem(BYTE POINTER(script),SIZEOF(ShellScript))
  script=NULL

RETURN
