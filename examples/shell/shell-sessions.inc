; Parse the full nonzero unsigned identity without signed /N truncation.
BYTE FUNC ShellSessionNumber(BYTE POINTER text LONGCARD POINTER identity)
  BYTE digit
  CARD index
  LONGCARD value

  value=0
  index=0
  WHILE text(index)<>ASCII.NUL DO
    digit=text(index)
    IF digit<ASCII.DIGIT_ZERO OR digit>ASCII.DIGIT_ZERO+9 THEN
      RETURN(0)
    FI

    digit==-ASCII.DIGIT_ZERO
    IF value>429496729 OR (value=429496729 AND digit>5) THEN
      RETURN(0)
    FI

    value=value*10+LONGCARD(digit)
    index==+1
  OD

  identity^=value

RETURN(index<>0 AND value<>0)

; Query data is a copied snapshot, independent of later session retirement.
PROC ShellSessionsReport(ShellContext POINTER context
    ShellSessionQuery POINTER query BYTE count)
  BYTE index,first
  CARD used

  LET output=DOS.Output()
  ShellLineText(context,output,c"  SESSION STATE")
  first=0
  IF count=2 AND query.entries(0).identity>query.entries(1).identity THEN
    first=1
  FI

  FOR index=0 TO count-1 DO
    BEGIN
      LET entry=@query.entries(first)
      used=ShellRowByte(context,output,0,
          IF entry.selected<>0 THEN BYTE('*) ELSE BYTE(ASCII.SPACE) FI)
      used=ShellRowByte(context,output,used,ASCII.SPACE)
      used=ShellRowUnsigned(context,output,used,entry.identity)
      used=ShellRowByte(context,output,used,ASCII.SPACE)
      CASE entry.state OF
      WHEN SESSION_STATE_CREATING THEN
        used=ShellRowText(context,output,used,c"creating")
      WHEN SESSION_STATE_READY THEN
        used=ShellRowText(context,output,used,c"ready")
      ELSE
        used=ShellRowText(context,output,used,c"closing")
      ESAC

      ShellRowEnd(context,output,used)
      first=1-first
    END
  OD

RETURN

; Borrow only this shell's scratch through the exact controller reply.
PROC ShellSessionCommand(ShellContext POINTER context BYTE operation)
  LONGCARD identity
  BYTE exchanged

  identity=context.control.identity
  IF operation=SESSION_SELECT THEN
    IF ShellSessionNumber(context.shell.words(1).text,@identity)=0 THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BAD_NUMBER)
      RETURN
    FI
  ELSEIF operation=SESSION_CREATE THEN
    IF context.shell.directory=NULL THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_NO_DEFAULT_DIR)
      RETURN
    FI

    IF DOS.NameFromLock(context.shell.directory,ShellScratch(context),
        SESSION_PATH_BYTES)=0 THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
      RETURN
    FI
  FI

  LET request=ShellSessionMessage POINTER(EXEC.AllocMem(
      SHELLSESSIONMESSAGE_SIZE,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
  IF request=NULL THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
    RETURN
  FI

  request.operation=operation
  request.session=identity
  request.payload=ShellScratch(context)
  request.capacity=SESSION_PATH_BYTES
  exchanged=ShellSessionExchange(context.control,request)
  IF request.primary<>PROCESS.RETURN_OK THEN
    ; Failure of a controller request does not retire the invoking shell.
    ShellFail(context,PROCESS.RETURN_ERROR,request.secondary)
  ELSEIF operation=SESSION_QUERY AND request.value<>0 THEN
    ShellSessionsReport(context,ShellSessionQuery POINTER(request.payload),
        BYTE(request.value))
  FI

  EXEC.FreeMem(BYTE POINTER(request),SHELLSESSIONMESSAGE_SIZE)

RETURN
