; Standalone examples own a CON: handle; disk commands borrow Output().
USE DOS
USE ASCII
USE CSTRING.IMPL AS STR

DOS.FileHandle POINTER console
BYTE consoleFailed
BYTE ARRAY consoleName=c"CON:"
BYTE ARRAY consolePrompt=c"Press RETURN to exit.\n"
BYTE consoleKey

; Open the native console for this Task.
BYTE FUNC OpenConsole()

  console=DOS.Open(consoleName,DOS.MODE_READWRITE)
  IF console=NULL THEN
    BEGIN
      consoleFailed=1
      LET released=DOS.ReleaseContext()
      RETURN(0)
    END
  FI

RETURN(1)

; Bank-zero I/O buffers must be writable, so callers supply text arrays.
PROC Print(BYTE POINTER text)

  LET length=LONGINT(STR.strlen(CSTRING(text)))
  IF DOS.Write(console,text,length)<>length THEN
    consoleFailed=1
  FI

RETURN

; Leave the result visible until Return, then release this Task's DOS state.
; The resident console restores the OS display when the application exits.
PROC CloseConsole()

  LONGINT count

  IF consoleFailed=0 THEN
    Print(consolePrompt)
    IF consoleFailed=0 THEN
      DO
        count=DOS.Read(console,@consoleKey,1)
      UNTIL count<>1 OR consoleKey=ASCII.LF
      OD

      IF count<>1 THEN
        consoleFailed=1
      FI
    FI
  FI

  IF DOS.Close(console)=0 THEN
    consoleFailed=1
  FI

  console=NULL

  IF DOS.ReleaseContext()=0 THEN
    consoleFailed=1
  FI

RETURN
