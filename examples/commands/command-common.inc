; Small command policy shared by these examples; parsing, conversion and I/O
; algorithms are imported resident services, not included implementations.
USE COMMAND
USE CSTRING AS STR
USE ASCII
USE SYS

; DOS transfers require upper-RAM buffers. Loaded-image globals are private to
; this command instance; the native stack is in bank zero.
BYTE ARRAY commandDigits(11)

INCLUDE "command-files.inc"

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
