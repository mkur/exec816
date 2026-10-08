; Capture at most eight names before writes invalidate an ExNext cookie.
; Prefixes borrow immutable argument text; only the 8.3 leaf names are copied.
CONST SELECTION_MAX=8, SELECTION_PATH_BYTES=256, SELECTION_NAME_BYTES=13
CONST SELECTION_EXACT=$ffff, SELECTION_INVALID=$fffe

TYPE CommandSelection=[
  CSTRING source
  CARD prefix
  BYTE ARRAY name(SELECTION_NAME_BYTES)
]

CommandSelection ARRAY selections(SELECTION_MAX)
CARD selectionCount
BYTE ARRAY selectionPath(SELECTION_PATH_BYTES)

; Return the final-component prefix, or distinguish exact and invalid paths.
CARD FUNC CommandPattern(CSTRING path)
  CARD index,last,first

  index=0
  last=SELECTION_EXACT
  first=SELECTION_EXACT
  WHILE path(index)<>ASCII.NUL DO
    IF path(index)=': OR path(index)='/ THEN
      last=index
    ELSEIF (path(index)='* OR path(index)='?) AND first=SELECTION_EXACT THEN
      first=index
    FI

    index==+1
  OD

  IF first=SELECTION_EXACT THEN
    RETURN(SELECTION_EXACT)
  FI

  IF last<>SELECTION_EXACT AND first<last THEN
    COMMAND.SetIoErr(COMMAND.ERROR_BAD_ARGUMENTS)
    RETURN(SELECTION_INVALID)
  FI

RETURN(IF last=SELECTION_EXACT THEN CARD(0) ELSE last+1 FI)

; Append a borrowed exact argument or a copied leaf; overflow changes no files.
BYTE FUNC CommandRemember(CSTRING source CARD prefix CSTRING name)
  SIZE length

  IF selectionCount=SELECTION_MAX THEN
    COMMAND.SetIoErr(COMMAND.ERROR_TOO_MANY_ARGS)
    RETURN(0)
  FI

  LET entry=@selections(selectionCount)
  IF prefix<>SELECTION_EXACT THEN
    length=STR.strlcpy(@entry.name(0),name,SIZEOF(entry.name))
    IF length>=SIZEOF(entry.name)
        OR SIZE(prefix)+length>=SELECTION_PATH_BYTES THEN
      COMMAND.SetIoErr(COMMAND.ERROR_LINE_TOO_LONG)
      RETURN(0)
    FI
  FI

  entry.source=source
  entry.prefix=prefix
  selectionCount==+1

RETURN(1)

; Enumerate without modifying the namespace; COPY skips directories, while
; DELETE leaves empty/nonempty directory policy to ordinary DeleteFile.
BYTE FUNC CommandCollect(CSTRING source CARD prefix BYTE filesOnly
    BYTE POINTER lock COMMAND.FileInfoBlock POINTER info)
  CARD before

  IF COMMAND.Examine(lock,BYTE POINTER(info))=0 THEN
    RETURN(0)
  FI

  IF info.fib_DirEntryType<=0 THEN
    COMMAND.SetIoErr(COMMAND.ERROR_OBJECT_WRONG_TYPE)
    RETURN(0)
  FI

  before=selectionCount
  LET pattern=source+SIZE(prefix)
  DO
    IF CommandReady()=0 THEN
      RETURN(0)
    FI

    IF COMMAND.ExNext(lock,BYTE POINTER(info))=0 THEN
      IF COMMAND.IoErr()<>COMMAND.ERROR_NO_MORE_ENTRIES THEN
        RETURN(0)
      FI

      IF selectionCount=before THEN
        COMMAND.SetIoErr(COMMAND.ERROR_OBJECT_NOT_FOUND)
        RETURN(0)
      FI

      COMMAND.SetIoErr(0)
      RETURN(1)
    FI

    IF filesOnly=0 OR info.fib_DirEntryType<0 THEN
      IF PatternMatch(pattern,CSTRING(@info.fib_FileName(0)))<>0 THEN
        IF CommandRemember(source,prefix,CSTRING(@info.fib_FileName(0)))=0 THEN
          RETURN(0)
        FI
      FI
    FI
  OD

RETURN(1)

; Release the enumeration lock before any caller mutation, retaining failures.
BYTE FUNC CommandSelect(CSTRING source CARD prefix BYTE filesOnly
    COMMAND.FileInfoBlock POINTER info)
  CARD index,length
  LONGINT cause

  IF prefix=SELECTION_INVALID THEN
    RETURN(0)
  FI

  IF prefix=SELECTION_EXACT THEN
    RETURN(CommandRemember(source,prefix,NULL))
  FI

  IF CommandReady()=0 THEN
    RETURN(0)
  FI

  length=prefix
  IF length<>0 THEN
    IF source(length-1)='/ AND length>1 THEN
      length==-1
    FI
  FI

  index=0
  WHILE index<length DO
    selectionPath(index)=source(index)
    index==+1
  OD

  selectionPath(length)=ASCII.NUL
  LET lock=COMMAND.Lock(selectionPath,COMMAND.SHARED_LOCK)
  IF lock=NULL THEN
    RETURN(0)
  FI

  LET collected=CommandCollect(source,prefix,filesOnly,lock,info)
  cause=COMMAND.IoErr()
  COMMAND.SetIoErr(0)
  COMMAND.UnLock(lock)
  IF cause=0 THEN
    cause=COMMAND.IoErr()
  FI

  COMMAND.SetIoErr(cause)

RETURN(BYTE(collected<>0 AND cause=0))

; Build one stable selected path; no enumeration remains active during use.
CSTRING FUNC CommandSelected(CARD index)
  CARD at

  LET entry=@selections(index)
  IF entry.prefix=SELECTION_EXACT THEN
    RETURN(entry.source)
  FI

  at=0
  WHILE at<entry.prefix DO
    selectionPath(at)=entry.source(at)
    at==+1
  OD

  LET capacity=SIZE(SELECTION_PATH_BYTES-at)
  IF STR.strlcpy(@selectionPath(at),CSTRING(@entry.name(0)),capacity)>=capacity THEN
    COMMAND.SetIoErr(COMMAND.ERROR_LINE_TOO_LONG)
    RETURN(NULL)
  FI

RETURN(CSTRING(selectionPath))
