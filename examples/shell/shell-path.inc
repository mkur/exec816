; Session-owned search names do not pin mounts or change CurrentDir.
BYTE POINTER FUNC ShellPathEntry(BYTE index)

RETURN(BYTE POINTER(ADDRESS(shell)+SIZE(PATH_OFFSET)
    +SIZE(index)*SIZE(LINE_CAPACITY)))

PROC ShellPathReset()

  STR.strlcpy(ShellPathEntry(0),c"SYS:",LINE_CAPACITY)
  shell.pathCount=1

RETURN

; Compare canonical names without depending on a mount alias's letter case.
BYTE FUNC ShellPathEqual(BYTE POINTER left,right)
  CARD index
  BYTE a,b

  index=0
  DO
    a=left(index)
    b=right(index)
    IF a>='a AND a<='z THEN
      a==-32
    FI

    IF b>='a AND b<='z THEN
      b==-32
    FI

    IF a<>b THEN
      RETURN(0)
    FI

    IF a=ASCII.NUL THEN
      RETURN(1)
    FI

    index==+1
  OD

RETURN(0)

; Keep a validated logical PATH prefix so a later ASSIGN replacement follows it.
BYTE FUNC ShellPathAssigned(BYTE POINTER path)
  DOS.AssignInfo POINTER info
  CARD colon,slot,index
  BYTE equal,value

  colon=0
  WHILE colon<32 AND path(colon)<>0 AND path(colon)<>': DO
    colon==+1
  OD

  IF colon=0 OR colon=32 OR path(colon)<>': THEN
    RETURN(0)
  FI

  info=DOS.AssignInfo POINTER(ShellScratch())
  FOR slot=0 TO 3 DO
    IF DOS.GetAssign(slot,info)<>0 THEN
      equal=BYTE(info.name(colon)=0)
      FOR index=0 TO colon-1 DO
        value=path(index)
        IF value>='a AND value<='z THEN
          value==-32
        FI

        IF value<>info.name(index) THEN
          equal=0
          EXIT
        FI
      OD

      IF equal<>0 THEN
        RETURN(1)
      FI
    FI
  OD

RETURN(0)

; Canonicalize one candidate, release its temporary lock, then publish it.
PROC ShellPathUpdate(BYTE POINTER name BYTE append)
  BYTE index,symbolic
  LONGINT cause

  IF ShellPoll()<>0 THEN
    RETURN
  FI

  symbolic=ShellPathAssigned(name)
  shell.retiredDirectory=DOS.Lock(name,DOS.SHARED_LOCK)
  IF shell.retiredDirectory=NULL THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
    RETURN
  FI

  LET info=DOS.FileInfoBlock POINTER(ShellScratch())
  cause=0
  IF DOS.Examine(shell.retiredDirectory,info)=0 THEN
    cause=DOS.IoErr()
  ELSEIF info.fib_DirEntryType<=0 THEN
    cause=DOS.ERROR_OBJECT_WRONG_TYPE
  ELSEIF DOS.NameFromLock(shell.retiredDirectory,ShellScratch(),LINE_CAPACITY)=0 THEN
    cause=DOS.IoErr()
  ELSEIF ShellEqual(name,c"SYS:")<>0 OR symbolic<>0 THEN
    STR.strlcpy(ShellScratch(),CSTRING(name),LINE_CAPACITY)
  FI

  DOS.SetIoErr(0)
  DOS.UnLock(shell.retiredDirectory)
  IF DOS.IoErr()<>0 THEN
    IF cause=0 THEN
      cause=DOS.IoErr()
    FI

    ; Keep the failed retirement reachable by ShellFinish.
    ShellFail(PROCESS.RETURN_FAIL,cause)
    RETURN
  FI

  shell.retiredDirectory=NULL
  IF cause<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,cause)
    RETURN
  FI

  IF ShellPoll()<>0 THEN
    RETURN
  FI

  index=0
  IF append<>0 THEN
    WHILE index<shell.pathCount DO
      IF ShellPathEqual(ShellPathEntry(index),ShellScratch())<>0 THEN
        RETURN
      FI

      index==+1
    OD

    IF index=PATH_CAPACITY THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BUFFER_OVERFLOW)
      RETURN
    FI
  FI

  STR.strlcpy(ShellPathEntry(index),CSTRING(ShellScratch()),LINE_CAPACITY)
  shell.pathCount=index+1

RETURN

; Mutations are deliberately bounded to one directory per invocation.
PROC ShellPath()
  BYTE index

  IF shell.argc=1 THEN
    ShellText(DOS.Output(),c"Current directory\n")
    index=0
    WHILE index<shell.pathCount DO
      ShellText(DOS.Output(),CSTRING(ShellPathEntry(index)))
      ShellByte(DOS.Output(),ASCII.LF)
      index==+1
    OD

    RETURN
  FI

  LET operation=shell.words(1).text
  IF shell.argc=2 THEN
    IF ShellEqual(operation,c"CLEAR")<>0 THEN
      shell.pathCount=0
      RETURN
    FI

    IF ShellEqual(operation,c"RESET")<>0 THEN
      ShellPathReset()
      RETURN
    FI
  ELSEIF shell.argc=3 THEN
    IF ShellEqual(operation,c"SET")<>0 THEN
      ShellPathUpdate(shell.words(2).text,0)
      RETURN
    FI

    IF ShellEqual(operation,c"ADD")<>0 THEN
      ShellPathUpdate(shell.words(2).text,1)
      RETURN
    FI
  FI

  ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BAD_ARGUMENTS)

RETURN

; Only a missing entry permits trying the next directory.
BYTE FUNC ShellPathMiss(LONGINT error)

RETURN(error=DOS.ERROR_OBJECT_NOT_FOUND OR error=DOS.ERROR_DIR_NOT_FOUND)

; Search only executable names. The exact public loader remains unchanged.
PROGRAMIMAGE.Image POINTER FUNC ShellLoadCommand(BYTE POINTER name)
  CARD index,length,used
  BYTE entry
  LONGINT error
  PROGRAMIMAGE.Image POINTER image

  length=ShellLength(name)
  index=0
  WHILE index<length DO
    IF name(index)=CHAR_COLON OR name(index)=CHAR_SLASH THEN
      RETURN(PROGRAMFILE.Load(name))
    FI

    index==+1
  OD

  IF ShellPoll()<>0 THEN
    DOS.SetIoErr(DOS.ERROR_BREAK)
    RETURN(NULL)
  FI

  image=PROGRAMFILE.Load(name)
  error=DOS.IoErr()
  IF image<>NULL OR (ShellPathMiss(error)=0 AND error<>DOS.ERROR_NO_DEFAULT_DIR) THEN
    RETURN(image)
  FI

  entry=0
  WHILE entry<shell.pathCount DO
    BEGIN
      IF ShellPoll()<>0 THEN
        DOS.SetIoErr(DOS.ERROR_BREAK)
        RETURN(NULL)
      FI

      LET directory=ShellPathEntry(entry)
      LET candidate=ShellScratch()
      used=ShellLength(directory)
      LET separator=BYTE(directory(used-1)<>CHAR_COLON)
      IF used+CARD(separator)+length>LINE_LIMIT THEN
        DOS.SetIoErr(DOS.ERROR_LINE_TOO_LONG)
        RETURN(NULL)
      FI

      STR.strlcpy(candidate,CSTRING(directory),LINE_CAPACITY)
      IF separator<>0 THEN
        candidate(used)=CHAR_SLASH
        used==+1
      FI

      STR.strlcpy(candidate+SIZE(used),CSTRING(name),LINE_CAPACITY-used)
      image=PROGRAMFILE.Load(candidate)
      error=DOS.IoErr()
      IF image<>NULL OR ShellPathMiss(error)=0 THEN
        RETURN(image)
      FI

      entry==+1
    END
  OD

  DOS.SetIoErr(DOS.ERROR_OBJECT_NOT_FOUND)

RETURN(NULL)
