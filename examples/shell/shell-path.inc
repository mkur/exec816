; Session-owned search names do not pin mounts or change CurrentDir.
BYTE POINTER FUNC ShellPathEntry(ShellContext POINTER context BYTE index)

RETURN(BYTE POINTER(ADDRESS(context.shell)+SIZE(PATH_OFFSET)
    +SIZE(index)*SIZE(LINE_CAPACITY)))

PROC ShellPathReset(ShellContext POINTER context)

  STR.strlcpy(ShellPathEntry(context,0),c"C:",LINE_CAPACITY)
  context.shell.pathCount=1

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
BYTE FUNC ShellPathAssigned(ShellContext POINTER context BYTE POINTER path)
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

  info=DOS.AssignInfo POINTER(ShellScratch(context))
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
PROC ShellPathUpdate(ShellContext POINTER context BYTE POINTER name BYTE append)
  BYTE index,symbolic
  LONGINT cause

  IF ShellPoll(context)<>0 THEN
    RETURN
  FI

  symbolic=ShellPathAssigned(context,name)
  context.shell.retiredDirectory=DOS.Lock(name,DOS.SHARED_LOCK)
  IF context.shell.retiredDirectory=NULL THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
    RETURN
  FI

  LET info=DOS.FileInfoBlock POINTER(ShellScratch(context))
  cause=0
  IF DOS.Examine(context.shell.retiredDirectory,info)=0 THEN
    cause=DOS.IoErr()
  ELSEIF info.fib_DirEntryType<=0 THEN
    cause=DOS.ERROR_OBJECT_WRONG_TYPE
  ELSEIF DOS.NameFromLock(context.shell.retiredDirectory,ShellScratch(context),LINE_CAPACITY)=0 THEN
    cause=DOS.IoErr()
  ELSEIF ShellEqual(name,c"SYS:")<>0 OR symbolic<>0 THEN
    STR.strlcpy(ShellScratch(context),CSTRING(name),LINE_CAPACITY)
  FI

  DOS.SetIoErr(0)
  DOS.UnLock(context.shell.retiredDirectory)
  IF DOS.IoErr()<>0 THEN
    IF cause=0 THEN
      cause=DOS.IoErr()
    FI

    ; Keep the failed retirement reachable by ShellFinish.
    ShellFail(context,PROCESS.RETURN_FAIL,cause)
    RETURN
  FI

  context.shell.retiredDirectory=NULL
  IF cause<>0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,cause)
    RETURN
  FI

  IF ShellPoll(context)<>0 THEN
    RETURN
  FI

  index=0
  IF append<>0 THEN
    WHILE index<context.shell.pathCount DO
      IF ShellPathEqual(ShellPathEntry(context,index),ShellScratch(context))<>0 THEN
        RETURN
      FI

      index==+1
    OD

    IF index=PATH_CAPACITY THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BUFFER_OVERFLOW)
      RETURN
    FI
  FI

  STR.strlcpy(ShellPathEntry(context,index),CSTRING(ShellScratch(context)),LINE_CAPACITY)
  context.shell.pathCount=index+1

RETURN

; Mutations are deliberately bounded to one directory per invocation.
PROC ShellPath(ShellContext POINTER context)
  BYTE index

  IF context.shell.argc=1 THEN
    ShellText(context,DOS.Output(),c"Current directory\n")
    index=0
    WHILE index<context.shell.pathCount DO
      ShellLineText(context,DOS.Output(),CSTRING(ShellPathEntry(context,index)))
      index==+1
    OD

    RETURN
  FI

  LET operation=context.shell.words(1).text
  IF context.shell.argc=2 THEN
    IF ShellEqual(operation,c"CLEAR")<>0 THEN
      context.shell.pathCount=0
      RETURN
    FI

    IF ShellEqual(operation,c"RESET")<>0 THEN
      ShellPathReset(context)
      RETURN
    FI
  ELSEIF context.shell.argc=3 THEN
    IF ShellEqual(operation,c"SET")<>0 THEN
      ShellPathUpdate(context,context.shell.words(2).text,0)
      RETURN
    FI

    IF ShellEqual(operation,c"ADD")<>0 THEN
      ShellPathUpdate(context,context.shell.words(2).text,1)
      RETURN
    FI
  FI

  ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BAD_ARGUMENTS)

RETURN

; Only a missing entry permits trying the next directory.
BYTE FUNC ShellPathMiss(LONGINT error)

RETURN(error=DOS.ERROR_OBJECT_NOT_FOUND OR error=DOS.ERROR_DIR_NOT_FOUND)

; Try the literal name first, then the conventional SDX command suffix.
PROGRAMIMAGE.Image POINTER FUNC ShellTryCommand(ShellContext POINTER context
    BYTE POINTER name)
  CARD index,length
  BYTE extension

  LET image=PROGRAMFILE.Load(name)
  LET error=DOS.IoErr()
  IF image<>NULL OR ShellPathMiss(error)=0 THEN
    RETURN(image)
  FI
  index=0
  extension=0
  WHILE name(index)<>0 DO
    IF name(index)=CHAR_COLON OR name(index)=CHAR_SLASH THEN
      extension=0
    ELSEIF name(index)='. THEN
      extension=1
    FI
    index==+1
  OD
  IF extension<>0 THEN
    RETURN(NULL)
  FI
  length=index
  IF length+4>LINE_LIMIT THEN
    DOS.SetIoErr(DOS.ERROR_LINE_TOO_LONG)
    RETURN(NULL)
  FI
  LET candidate=ShellScratch(context)
  STR.strlcpy(candidate,CSTRING(name),LINE_CAPACITY)
  STR.strlcpy(candidate+SIZE(length),c".COM",LINE_CAPACITY-length)
  LET suffixed=PROGRAMFILE.Load(candidate)
  candidate(length)=0

RETURN(suffixed)

; Search only executable names. The exact public loader remains unchanged.
PROGRAMIMAGE.Image POINTER FUNC ShellLoadCommand(ShellContext POINTER context BYTE POINTER name)
  CARD index,length,used
  BYTE entry
  LONGINT error
  PROGRAMIMAGE.Image POINTER image

  length=ShellLength(name)
  index=0
  WHILE index<length DO
    IF name(index)=CHAR_COLON OR name(index)=CHAR_SLASH THEN
      RETURN(ShellTryCommand(context,name))
    FI

    index==+1
  OD

  IF ShellPoll(context)<>0 THEN
    DOS.SetIoErr(DOS.ERROR_BREAK)
    RETURN(NULL)
  FI

  image=ShellTryCommand(context,name)
  error=DOS.IoErr()
  IF image<>NULL OR (ShellPathMiss(error)=0 AND error<>DOS.ERROR_NO_DEFAULT_DIR) THEN
    RETURN(image)
  FI

  entry=0
  WHILE entry<context.shell.pathCount DO
    BEGIN
      IF ShellPoll(context)<>0 THEN
        DOS.SetIoErr(DOS.ERROR_BREAK)
        RETURN(NULL)
      FI

      LET directory=ShellPathEntry(context,entry)
      LET candidate=ShellScratch(context)
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
      image=ShellTryCommand(context,candidate)
      error=DOS.IoErr()
      IF image<>NULL OR ShellPathMiss(error)=0 THEN
        RETURN(image)
      FI

      entry==+1
    END
  OD

  DOS.SetIoErr(DOS.ERROR_OBJECT_NOT_FOUND)

RETURN(NULL)
