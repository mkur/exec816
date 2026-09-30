; Reject unrepresentable C addresses before converting to native pointers.
LONGINT FUNC CWrite(LONGCARD file,buffer LONGINT length)

  IF file>$ffffff OR buffer>$ffffff THEN
    BEGIN
      LET ignored=DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
      RETURN(-1)
    END
  FI

RETURN(DOS.Write(DOS.FileHandle POINTER(ADDRESS(file)),
    BYTE POINTER(ADDRESS(buffer)),length))

; Bind library calls once; every call still uses its own Task's DOS context.
PROC BindDos()

  LET entries=ADDRESS POINTER(C_EXECDOSENTRIES)
  entries(0)=ADDRESS(@DOS.Output)
  entries(1)=ADDRESS(@CWrite)

RETURN
