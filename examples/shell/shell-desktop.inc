; Root can report an optional desktop application failure without borrowing
; a shell's selected streams or retaining its mutable context.
PROC ShellDesktopNotice(CSTRING text)
  LONGINT written
  BYTE closed

  LET output=DOS.Open(BYTE POINTER(c"RAW:"),DOS.MODE_READWRITE)
  IF output=NULL THEN
    RETURN
  FI

  written=DOS.Write(output,BYTE POINTER(text),LONGINT(STR.strlen(text)))
  closed=DOS.Close(output)

RETURN
