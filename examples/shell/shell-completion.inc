; Completion scans a snapshot. Only the resumed cooked editor changes the live
; input line; the ordinary parser and command result remain untouched.
BYTE FUNC ShellCompletionDelimiter(BYTE value)

RETURN(value=ASCII.NUL OR value=ASCII.SPACE OR value=ASCII.TAB
    OR value=CHAR_PIPE OR value=CHAR_LESS OR value=CHAR_GREATER)

; Return 1 for the first command, 2 for a file argument, or 0 for an unsupported
; token. Quoted earlier arguments still establish subsequent token positions.
BYTE FUNC ShellCompletionToken(ShellContext POINTER context)
  CARD at,start
  BYTE command,redirect,quoted,unsupported,value,kind

  LET state=ShellEdit(context)
  LET line=ShellLine(context)
  LET cursor=state.edit.cursor
  IF cursor=0 OR ShellCompletionDelimiter(line(cursor))=0 THEN
    RETURN(0)
  FI

  at=0
  command=1
  redirect=0
  WHILE at<cursor DO
    value=line(at)
    IF value=ASCII.SPACE OR value=ASCII.TAB THEN
      at==+1
    ELSEIF value=CHAR_PIPE THEN
      command=2
      redirect=0
      at==+1
    ELSEIF value=CHAR_LESS OR value=CHAR_GREATER THEN
      redirect=1
      at==+1
    ELSE
      start=at
      quoted=0
      unsupported=0
      WHILE at<cursor DO
        value=line(at)
        IF quoted=0 AND ShellCompletionDelimiter(value)<>0 THEN
          EXIT
        FI

        IF value=ASCII.DOUBLE_QUOTE THEN
          quoted=quoted XOR 1
          unsupported=1
        ELSEIF value=ASCII.ASTERISK THEN
          unsupported=1
          IF quoted<>0 AND at+1<cursor THEN
            at==+1
          FI
        ELSEIF value='? OR value=92 OR value=CHAR_SEMICOLON THEN
          unsupported=1
        FI

        at==+1
      OD

      IF at=cursor THEN
        IF unsupported<>0 OR start=at THEN
          RETURN(0)
        FI

        kind=2
        IF redirect=0 THEN
          IF command=2 THEN
            RETURN(0)
          ELSEIF command=1 THEN
            kind=1
          FI
        FI

        state.first=start
        state.component=start
        WHILE start<at DO
          IF line(start)=CHAR_COLON OR line(start)=CHAR_SLASH THEN
            state.component=start+1
            kind=2
          FI

          start==+1
        OD

        IF state.component=at THEN
          RETURN(0)
        FI

        RETURN(kind)
      FI

      IF redirect<>0 THEN
        redirect=0
      ELSEIF command<>0 THEN
        command=0
        IF unsupported=0 AND at-start=3 THEN
          IF FS83.Fold(line(start))='R AND FS83.Fold(line(start+1))='U
              AND FS83.Fold(line(start+2))='N THEN
            command=2
          FI
        FI
      FI
    FI
  OD

RETURN(0)

; Accumulate a case-folded common prefix without retaining the candidate set.
PROC ShellCompletionMatch(ShellContext POINTER context
    BYTE POINTER name BYTE directory)
  CARD index,length,prefix

  LET state=ShellEdit(context)
  LET first=ShellDrawBuffer(context)
  LET line=ShellLine(context)
  prefix=state.edit.cursor-state.component
  length=ShellLength(name)
  IF length<prefix THEN
    RETURN
  FI

  FOR index=0 TO prefix-1 DO
    IF FS83.Fold(name(index))<>FS83.Fold(line(state.component+index)) THEN
      RETURN
    FI
  OD

  IF state.matches=0 THEN
    STR.strlcpy(first,CSTRING(name),DRAW_CAPACITY)
    state.common=length
    state.matches=1
    state.directory=directory
    RETURN
  FI

  index=0
  WHILE index<state.common AND index<length DO
    IF FS83.Fold(first(index))<>FS83.Fold(name(index)) THEN
      EXIT
    FI

    index==+1
  OD

  IF index<>length OR first(index)<>ASCII.NUL THEN
    state.matches=2
  FI

  state.common=index

RETURN

; Resident names use exactly the classifier's definitions and current aliases.
PROC ShellCompletionNames(ShellContext POINTER context)
  BYTE command,index

  FOR command=CMD_HELP TO CMD_UNMOUNT DO
    IF command<>CMD_EXTERNAL THEN
      ShellCompletionMatch(context,BYTE POINTER(ShellCommandName(command)),0)
    FI
  OD

  IF context.aliases<>NULL THEN
    FOR index=0 TO ALIAS_CAPACITY-1 DO
      IF context.aliases(index).name(0)<>ASCII.NUL THEN
        ShellCompletionMatch(context,@context.aliases(index).name(0),0)
      FI
    OD
  FI

RETURN

; Extend a snapshot only when the whole replacement fits. The suffix after the
; cursor moves with its terminator, preserving arguments and redirection text.
PROC ShellCompletionApply(ShellContext POINTER context)
  CARD prefix,extra,index,finish
  BYTE separator

  LET state=ShellEdit(context)
  LET edit=@state.edit
  LET line=ShellLine(context)
  LET name=ShellDrawBuffer(context)
  IF state.matches=0 THEN
    RETURN
  FI

  prefix=edit.cursor-state.component
  extra=state.common-prefix
  separator=0
  IF state.matches=1 THEN
    IF state.directory<>0 THEN
      separator=CHAR_SLASH
    ELSEIF edit.cursor=edit.length AND edit.length+extra<LINE_LIMIT THEN
      separator=ASCII.SPACE
    FI
  FI

  finish=extra+CARD(separator<>0)
  IF finish=0 OR edit.length+finish>LINE_LIMIT THEN
    RETURN
  FI

  index=edit.length+1
  WHILE index>edit.cursor DO
    index==-1
    line(index+finish)=line(index)
  OD

  index=0
  WHILE index<extra DO
    line(edit.cursor+index)=name(prefix+index)
    index==+1
  OD

  IF separator<>0 THEN
    line(edit.cursor+extra)=separator
  FI

  edit.length==+finish
  edit.cursor==+finish
  edit.replace=1

RETURN

; Scan to EOF before accepting any result. The caller owns the paused editor,
; while ordinary DOS calls can reuse its collected request and client context.
BYTE FUNC ShellCompletionDirectory(ShellContext POINTER context
    BYTE POINTER path BYTE filesOnly)
  LONGINT count,cause
  BYTE index,complete

  IF DOS.BreakPending()<>0 THEN
    RETURN(0)
  FI

  context.shell.retiredDirectory=DOS.Lock(path,DOS.SHARED_LOCK)
  IF context.shell.retiredDirectory=NULL THEN
    BEGIN
      LET error=DOS.IoErr()
      RETURN(ShellPathMiss(error)<>0 OR error=DOS.ERROR_NO_DEFAULT_DIR)
    END
  FI

  LET info=DOS.FileInfoBlock POINTER(ShellScratch(context))
  LET batch=DOS.DirBatch POINTER(ShellTransfer(context))
  complete=0
  IF DOS.Examine(context.shell.retiredDirectory,info)<>0 THEN
    IF info.fib_DirEntryType>0 THEN
      batch.capacity=4
      DO
        IF DOS.BreakPending()<>0 THEN
          EXIT
        FI

        count=DOS.ExNextBatch(context.shell.retiredDirectory,info,batch)
        cause=DOS.IoErr()
        IF count<0 OR (cause<>0 AND cause<>DOS.ERROR_NO_MORE_ENTRIES)
            OR (count<4 AND cause<>DOS.ERROR_NO_MORE_ENTRIES) THEN
          EXIT
        FI

        IF count<>0 THEN
          FOR index=0 TO BYTE(count)-1 DO
            IF filesOnly=0 OR batch.entries(index).kind<0 THEN
              ShellCompletionMatch(context,@batch.entries(index).name(0),
                  batch.entries(index).kind>0)
            FI
          OD
        FI

        IF cause=DOS.ERROR_NO_MORE_ENTRIES THEN
          complete=1
          EXIT
        FI
      OD
    FI
  FI

  ; A failed release remains reachable for the shell's fatal cleanup path.
  DOS.SetIoErr(0)
  DOS.UnLock(context.shell.retiredDirectory)
  IF DOS.IoErr()<>0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  context.shell.retiredDirectory=NULL

RETURN(complete)

; Resolve each logical PATH spelling afresh. Never change CurrentDir or load
; a candidate: regular filenames alone do not establish executable validity.
BYTE FUNC ShellCompletionFiles(ShellContext POINTER context BYTE kind)
  BYTE index
  CARD length

  LET state=ShellEdit(context)
  LET path=ShellCompletionPath(context)
  length=state.component-state.first
  A816MEMORY.Move(path,ShellLine(context)+SIZE(state.first),SIZE(length))
  ; Lock rejects a trailing separator after a directory component. Preserve
  ; a bare root slash; the original logical prefix stays untouched in the edit.
  IF length>1 AND path(length-1)=CHAR_SLASH THEN
    length==-1
  FI

  path(length)=ASCII.NUL
  IF ShellCompletionDirectory(context,path,kind=1)=0 THEN
    RETURN(0)
  FI

  IF kind=1 AND context.shell.pathCount<>0 THEN
    FOR index=0 TO context.shell.pathCount-1 DO
      IF ShellCompletionDirectory(context,ShellPathEntry(context,index),1)=0 THEN
        RETURN(0)
      FI
    OD
  FI

RETURN(DOS.BreakPending()=0)

; A failed or canceled discovery never changes the edit or command result.
; The next RESUME observes sticky BREAK through normal cooked cancellation.
PROC ShellComplete(ShellContext POINTER context)

  LET state=ShellEdit(context)
  state.edit.replace=0
  state.matches=0
  LET kind=ShellCompletionToken(context)
  IF kind=0 THEN
    RETURN
  FI

  LET saved=DOS.IoErr()
  IF kind=1 THEN
    ShellCompletionNames(context)
  FI

  IF ShellCompletionFiles(context,kind)<>0 THEN
    ShellCompletionApply(context)
  FI

  DOS.SetIoErr(saved)

RETURN
