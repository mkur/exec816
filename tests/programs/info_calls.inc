; Controlled copied records below the actual INFO command and DOS helpers.
PROC Copy(CARD index VolumeInfo POINTER info)
  CARD at

  LET source=BYTE POINTER(@T.scenario.data(0)+SIZE(index*CARD(SIZEOF(VolumeInfo))))
  LET target=BYTE POINTER(info)
  FOR at=0 TO CARD(SIZEOF(VolumeInfo))-1 DO
    target(at)=source(at)
  OD

RETURN

PUBLIC LONGINT FUNC GetVolume(CARD index VolumeInfo POINTER info)
  CARD at

  T.state.error=0
  LET target=BYTE POINTER(info)
  FOR at=0 TO CARD(SIZEOF(VolumeInfo))-1 DO
    target(at)=0
  OD
  IF index>=T.scenario.entries THEN
    RETURN(0)
  FI

  Copy(index,info)
  IF info.name(0)=0 THEN
    RETURN(0)
  FI

  info.flags=0

RETURN(-1)

PUBLIC LONGINT FUNC Info(BYTE POINTER lock VolumeInfo POINTER info)

  T.state.error=0
  IF ADDRESS(lock)=2 AND T.scenario.enumerationError<>0 THEN
    T.state.error=T.scenario.enumerationError
    RETURN(0)
  FI

  Copy(CARD(ADDRESS(lock))-1,info)
  T.state.first==+1

RETURN(-1)

PUBLIC BYTE POINTER FUNC Lock(BYTE POINTER name LONGINT mode)
  CARD index

  T.state.error=0
  IF name(0)='M OR name(0)=0 THEN
    T.state.error=205
    RETURN(NULL)
  FI

  index=0
  IF name(0)='W THEN
    index=1
  ELSEIF name(0)='R THEN
    index=2
  FI

  T.state.opens==+1

RETURN(BYTE POINTER(ADDRESS(index+1)))

PUBLIC PROC UnLock(BYTE POINTER lock)

  Close(lock)

RETURN
