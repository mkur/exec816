; Five full-width values cross from C; validate before narrowing pointers.
; All device calls execute in the calling Task through the existing API.
LONGCARD FUNC CDeviceCall(LONGCARD operation,a,b,c,d)
  EXEC.IORequest POINTER request

  IF a>$ffffff OR (operation=2 AND c>$ffffff) THEN
    HEAPCORE.Abort($ff50)
  FI

  request=EXEC.IORequest POINTER(ADDRESS(a))
  IF operation=0 THEN
    RETURN(LONGCARD(ADDRESS(EXEC.CreateIORequest(EXEC.MsgPort POINTER(ADDRESS(a)),b))))
  ELSEIF operation=1 THEN
    EXEC.DeleteIORequest(request)
  ELSEIF operation=2 THEN
    RETURN(LONGCARD(LONGINT(EXEC.OpenDevice(BYTE POINTER(ADDRESS(a)),b,
        EXEC.IORequest POINTER(ADDRESS(c)),d))))
  ELSEIF operation=3 THEN
    EXEC.CloseDevice(request)
  ELSEIF operation=4 THEN
    EXEC.BeginIO(request)
  ELSEIF operation=5 THEN
    EXEC.SendIO(request)
  ELSEIF operation=6 THEN
    RETURN(LONGCARD(LONGINT(EXEC.DoIO(request))))
  ELSEIF operation=7 THEN
    RETURN(LONGCARD(ADDRESS(EXEC.CheckIO(request))))
  ELSEIF operation=8 THEN
    RETURN(LONGCARD(LONGINT(EXEC.WaitIO(request))))
  ELSEIF operation=9 THEN
    EXEC.AbortIO(request)
  ELSE
    HEAPCORE.Abort($ff50)
  FI

RETURN(0)

PROC BindIO()

  LET entry=ADDRESS POINTER(C_EXECIOENTRY)
  entry^=ADDRESS(@CDeviceCall)

RETURN
