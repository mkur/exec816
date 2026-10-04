; Small command policy shared by these examples; parsing, conversion and I/O
; algorithms are imported resident services, not included implementations.
USE COMMAND
USE CSTRING AS STR
USE ASCII
USE SYS

; DOS transfers require upper-RAM buffers. Loaded-image globals are private to
; this command instance; the native stack is in bank zero.
BYTE ARRAY commandDigits(11)

; Syntax diagnostics belong to the foreground console, not redirected data.
; A headless caller still receives the original parser error through IoErr.
LONGINT FUNC CommandArgs(CSTRING template ADDRESS POINTER values CARD count
                        BYTE POINTER storage CARD capacity)

  IF COMMAND.ReadArgs(template,values,count,storage,capacity)<>0 THEN
    RETURN(-1)
  FI

  LET cause=COMMAND.IoErr()
  LET console=COMMAND.OpenConsole()
  IF console<>NULL THEN
    COMMAND.WriteAll(console,BYTE POINTER(c"Arguments: "),11)
    COMMAND.WriteAll(console,BYTE POINTER(template),STR.strlen(template))
    COMMAND.WriteAll(console,BYTE POINTER(c"\n"),1)
    COMMAND.Close(console)
  FI

  COMMAND.SetIoErr(cause)

RETURN(0)

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

; Early consumers must still report an error already attached to prefetched
; bytes, even when they intentionally stop before another read.
LONGINT FUNC CommandReadResult(COMMAND.Reader POINTER reader LONGINT status)

  IF status<COMMAND.RETURN_ERROR AND reader.error<>0 THEN
    COMMAND.SetIoErr(reader.error)
    RETURN(COMMAND.RETURN_ERROR)
  FI

RETURN(status)

; Read a /N result without narrowing its four-byte value to an address.
LONGCARD FUNC CommandNumber(ADDRESS value LONGCARD fallback)

  IF value=0 THEN
    RETURN(fallback)
  FI

  LET number=LONGCARD POINTER(value)

RETURN(number^)

LONGINT FUNC CommandText(CSTRING text)

RETURN(COMMAND.WriteAll(COMMAND.Output(),BYTE POINTER(text),STR.strlen(text)))

; Format through the compiler-owned resident conversion primitive.
LONGINT FUNC CommandDecimal(LONGCARD number)

  LET length=STR.u32toa(number,commandDigits,SIZEOF(commandDigits))

RETURN(COMMAND.WriteAll(COMMAND.Output(),commandDigits,length))

; Emit the counted text payload and normalize only a present line delimiter.
LONGINT FUNC CommandLine(COMMAND.Reader POINTER reader BYTE POINTER text
                         LONGINT length)

  IF COMMAND.WriteAll(COMMAND.Output(),text,length)=0 THEN
    RETURN(0)
  FI

  IF reader.terminated<>0 THEN
    RETURN(CommandText(c"\n"))
  FI

RETURN(-1)
