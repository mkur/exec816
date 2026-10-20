; Caller-context console lifecycle and mode operations. No driver policy or
; new kernel gateway is introduced by these ordinary library calls.
LONGCARD FUNC CConsoleCreate(LONGCARD width,height,unused)

RETURN(CONSOLE.Create(CARD(width),CARD(height)))

LONGINT FUNC CConsoleDestroy(LONGCARD unit,unused,unused2)

RETURN(LONGINT(CONSOLE.Destroy(unit)))

LONGINT FUNC CConsoleMode(LONGCARD file,caps,unused)
  BYTE mode

  IF file>$ffffff OR caps>$ff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

  mode=BYTE(caps)

RETURN(DOS.ConsoleIO(DOS.FileHandle POINTER(ADDRESS(file)),
    CONSOLETYPES.CONCMD_MODE,0,@mode,1))

LONGINT FUNC CConsoleGetMode(LONGCARD file,unused,unused2)
  BYTE mode

  IF file>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(-1)
  FI
  IF DOS.ConsoleIO(DOS.FileHandle POINTER(ADDRESS(file)),
      CONSOLETYPES.CONCMD_GET_MODE,0,@mode,1)<>1 THEN
    RETURN(-1)
  FI

RETURN(LONGINT(mode))

PROC BindConsole()

  LET entries=ADDRESS POINTER(C_EXECCONSOLEENTRIES)
  entries(1)=ADDRESS(@CConsoleCreate)
  entries(2)=ADDRESS(@CConsoleDestroy)
  entries(3)=ADDRESS(@CConsoleMode)
  entries(4)=ADDRESS(@CConsoleGetMode)

RETURN
