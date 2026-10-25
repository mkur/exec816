; Validate the complete public vector once, before its first model mutation.
; The caller owns live nested buffers through exact completion collection.
BYTE FUNC SpansValid(CONSOLETYPES.Instance POINTER instance
    EXEC.IOStdReq POINTER request)
  CARD offset
  CONSOLETYPES.CellSpan POINTER span

  IF request.io_Length>LONGCARD(CONSOLETYPES.CELLSPAN_SIZE*30)
      OR (request.io_Length MOD LONGCARD(CONSOLETYPES.CELLSPAN_SIZE))<>0 THEN
    RETURN(BYTE(EXEC.IOERR_BADLENGTH))
  FI

  offset=0
  WHILE offset<CARD(request.io_Length) DO
    span=CONSOLETYPES.CellSpan POINTER(request.io_Data+SIZE(offset))
    IF span.row>=instance.height OR span.column>=instance.width
        OR span.data=NULL THEN
      RETURN(BYTE(EXEC.IOERR_BADADDRESS))
    FI
    IF span.length=0 OR span.length>instance.width-span.column THEN
      RETURN(BYTE(EXEC.IOERR_BADLENGTH))
    FI
    offset==+CONSOLETYPES.CELLSPAN_SIZE
  OD

RETURN(0)

; Spend at most one ordinary source quantum across descriptors. Actual counts
; only whole descriptors; a partial span retains its cursor until next turn.
BYTE FUNC SpansWrite(CONSOLETYPES.Instance POINTER instance
    EXEC.IOStdReq POINTER request)
  CARD budget,count
  CONSOLETYPES.CellSpan POINTER span

  IF instance.writeCancel<>0 OR request.io_Actual=request.io_Length THEN
    FinishWrite(instance,request)
    RETURN(0)
  FI

  budget=CONSOLETYPES.SOURCE_QUANTUM
  WHILE budget<>0 AND instance.vectorIndex<CARD(request.io_Length)
      AND instance.writeCancel=0 DO
    span=CONSOLETYPES.CellSpan POINTER(request.io_Data+SIZE(instance.vectorIndex))
    count=span.length-instance.vectorOffset
    IF count>budget THEN
      count=budget
    FI
    CONSOLECORE.WriteAt(instance,span.column+instance.vectorOffset,span.row,
        span.data+SIZE(instance.vectorOffset),count)
    instance.vectorOffset==+count
    budget==-count
    IF instance.vectorOffset=span.length THEN
      instance.vectorIndex==+CONSOLETYPES.CELLSPAN_SIZE
      instance.vectorOffset=0
      request.io_Actual=LONGCARD(instance.vectorIndex)
    FI
  OD

RETURN(request.io_Actual=request.io_Length)
