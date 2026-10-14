; Normalize only the operation word; paths retain their original case.
CARD FUNC ParseOperation()
  CARD index

  IF values(0)=0 THEN
    RETURN(OP_STATUS)
  FI

  LET word=BYTE POINTER(values(0))
  index=0
  WHILE word(index)<>0 DO
    IF word(index)>='a AND word(index)<='z THEN
      word(index)==-32
    FI

    index==+1
  OD

  IF STR.strcmp(CSTRING(word),c"STATUS")=0 THEN
    RETURN(OP_STATUS)
  ELSEIF STR.strcmp(CSTRING(word),c"HOSTS")=0 THEN
    RETURN(OP_HOSTS)
  ELSEIF STR.strcmp(CSTRING(word),c"DISKS")=0 THEN
    RETURN(OP_DISKS)
  ELSEIF STR.strcmp(CSTRING(word),c"DIR")=0 THEN
    RETURN(OP_DIRECTORY)
  ELSEIF STR.strcmp(CSTRING(word),c"ATTACH")=0 THEN
    RETURN(OP_ATTACH)
  ELSEIF STR.strcmp(CSTRING(word),c"EJECT")=0 THEN
    RETURN(OP_EJECT)
  FI

RETURN(0)

BYTE FUNC ParseDrive()

  IF values(1)=0 THEN
    RETURN(0)
  FI

  LET name=BYTE POINTER(values(1))
  IF (name(0)<>'D AND name(0)<>'d) OR name(1)<'1 OR name(1)>'8 THEN
    RETURN(0)
  FI

  IF name(2)<>0 THEN
    IF name(2)<>': OR name(3)<>0 THEN
      RETURN(0)
    FI
  FI

  drive=DRIVE_FIRST+CARD(name(1)-'1)

RETURN(1)

BYTE FUNC ParseHost()

  IF values(2)=0 THEN
    RETURN(0)
  FI

  LET number=LONGCARD POINTER(values(2))
  IF number^<1 OR number^>FUJINET.SLOTS THEN
    RETURN(0)
  FI

  host=CARD(number^-1)

RETURN(1)

; Reject invalid paths before even mounting a configured host.
BYTE FUNC ParsePath(CARD index,nulBytes)

  LET path=BYTE POINTER(values(index))
  IF path=NULL THEN
    RETURN(0)
  FI

  LET length=STR.strlen(CSTRING(path))
  IF length=0 THEN
    RETURN(0)
  FI

  IF length+SIZE(nulBytes)>SIZE(FUJINET.PATH_BYTES) THEN
    cause=COMMAND.ERROR_LINE_TOO_LONG
    RETURN(0)
  FI

RETURN(1)

BYTE FUNC Parse()
  CARD index
  BYTE okay

  operation=ParseOperation()
  okay=1
  IF operation=OP_STATUS OR operation=OP_HOSTS THEN
    FOR index=1 TO 5 DO
      IF values(index)<>0 THEN
        okay=0
      FI
    OD
  ELSEIF operation=OP_DISKS THEN
    FOR index=2 TO 5 DO
      IF values(index)<>0 THEN
        okay=0
      FI
    OD

    IF values(1)<>0 THEN
      okay=okay AND ParseDrive()
    FI
  ELSEIF operation=OP_DIRECTORY THEN
    okay=values(1)=0 AND values(4)=0 AND values(5)=0 AND ParseHost()
    IF values(3)<>0 THEN
      okay=okay AND ParsePath(3,2)
    FI
  ELSEIF operation=OP_ATTACH THEN
    okay=values(3)=0 AND ParseDrive() AND ParseHost() AND ParsePath(4,1)
  ELSEIF operation=OP_EJECT THEN
    okay=ParseDrive()
    FOR index=2 TO 5 DO
      IF values(index)<>0 THEN
        okay=0
      FI
    OD
  ELSE
    okay=0
  FI

  IF okay=0 AND cause=0 THEN
    cause=COMMAND.ERROR_BAD_ARGUMENTS
  FI

RETURN(okay)
