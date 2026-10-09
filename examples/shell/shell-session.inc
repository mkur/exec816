; Resident application code, shared by the entry point and native fixtures.
USE EXEC
USE FSFORMATS
USE DOS
USE DOSCORE
USE DOSOBJECTS
USE EXECBUILD
USE TASKINSPECT
USE DEVICEINSPECT
USE FSSYSTEM
USE BOOTCONFIG
USE BOOTDIAG
USE FSINSPECT
USE PROGRAMFILE
USE PROGRAM
USE PROGRAMIMAGE
USE PROCESS
USE PIPELINE
USE ASCII
USE A816MEMORY
USE DOSARGS
USE SYS
USE CSTRING.IMPL AS STR

CONST WORD_CAPACITY=16
CONST LINE_CAPACITY=256
CONST LINE_LIMIT=LINE_CAPACITY-1
CONST READ_CHUNK_SIZE=64

CONST HEADER_SIZE=128
CONST DRAW_CAPACITY=128
CONST SCRATCH_CAPACITY=288
CONST TRANSFER_CAPACITY=512

CONST DRAW_OFFSET=HEADER_SIZE+LINE_CAPACITY
CONST SCRATCH_OFFSET=DRAW_OFFSET+DRAW_CAPACITY
CONST TRANSFER_OFFSET=SCRATCH_OFFSET+SCRATCH_CAPACITY
CONST PATH_OFFSET=TRANSFER_OFFSET+TRANSFER_CAPACITY
CONST PATH_CAPACITY=4
CONST SHELL_BYTES=PATH_OFFSET+PATH_CAPACITY*LINE_CAPACITY
CONST ALIAS_CAPACITY=8
CONST ALIAS_NAME_CAPACITY=16
CONST ALIAS_TEXT_CAPACITY=128

CONST NO_REDIRECT=$ffff
CONST DIAGNOSTIC_SCRIPT=$fe

CONST CHAR_LOWER_A=97
CONST CHAR_LOWER_Z=122
CONST CASE_DELTA=32
CONST CHAR_LESS=60
CONST CHAR_GREATER=62
CONST CHAR_PIPE=124
CONST CHAR_SEMICOLON=59
CONST CHAR_MINUS=45
CONST CHAR_SLASH=47
CONST CHAR_DOT=46
CONST CHAR_COLON=58
CONST CHAR_LAST_PRINTABLE=126

CONST CMD_HELP=1
CONST CMD_ECHO=2
CONST CMD_CD=3
CONST CMD_EXIT=4
CONST CMD_DIR=5
CONST CMD_TYPE=6
CONST CMD_MEM=7
CONST CMD_TASKS=8
CONST CMD_VER=9
CONST CMD_MOUNT=10
CONST CMD_DEVICES=11
CONST CMD_EXTERNAL=12
CONST CMD_PATH=13
CONST CMD_ALIAS=14
CONST CMD_UNALIAS=15
CONST CMD_CLS=16
CONST CMD_RUN=17
CONST CMD_JOBS=18
CONST CMD_BREAK=19
CONST CMD_EXECUTE=20
CONST JOB_RUNNING=1,JOB_STOPPING=2,JOB_DONE=3

TYPE ShellWord=[BYTE POINTER text]
TYPE ShellAlias=[
  BYTE ARRAY name(ALIAS_NAME_CAPACITY)
  BYTE ARRAY text(ALIAS_TEXT_CAPACITY)
]

TYPE ShellState=[
  DOS.FileHandle POINTER console
  DOS.FileHandle POINTER initialInput,initialOutput
  DOS.FileHandle POINTER oldInput,oldOutput
  DOS.FileHandle POINTER tempInput,tempOutput
  DOS.FileLock POINTER directory

  LONGINT status,error,lastStatus,lastError

  CARD length
  CARD argumentLength
  CARD argsUsed
  BYTE background
  BYTE outputAppend
  CARD inputRedirect,outputRedirect
  BYTE argc,command,done
  BYTE ARRAY reservedLine(2)
  BYTE initialized,restoreFailure

  ShellWord ARRAY words(WORD_CAPACITY)

  DOS.FileLock POINTER retiredDirectory
  DOS.FileHandle POINTER commandInput
  BYTE redirectActive

  CARD pipelineIndex,secondArgumentOffset,secondArgumentLength
  BYTE pipeline
  BYTE pathCount
  BYTE diagnosticWord
  BYTE historyAvailable
  BYTE firstCommandStart,firstCommandEnd
  BYTE secondCommandStart,secondCommandEnd
]

TYPE ShellJob=[
  LONGCARD identity
  PROCESS.Result outcome
  BYTE state,announce
]

; Allocated only while EXECUTE owns a script and its inherited streams.
TYPE ShellScript=[
  DOS.FileHandle POINTER source
  DOS.FileHandle POINTER oldInput,oldOutput,tempInput,tempOutput
  CARD used,available
  BYTE redirectActive,previousCR
  BYTE ARRAY bytes(READ_CHUNK_SIZE)
]

ShellJob job
ShellState POINTER shell
ShellAlias POINTER aliases
BYTE aliasCount
ShellScript POINTER script
BYTE ARRAY shellCon=c"CON:"
BYTE ARRAY shellRoot=c"SYS:"

; Borrow the current command line, shared by input collection and parsing.
BYTE POINTER FUNC ShellLine()

RETURN(BYTE POINTER(ADDRESS(shell)+SIZE(HEADER_SIZE)))

; Borrow temporary output space; callers must not retain its contents.
BYTE POINTER FUNC ShellDrawBuffer()

RETURN(BYTE POINTER(ADDRESS(shell)+SIZE(DRAW_OFFSET)))

; Borrow workspace for paths and directory information.
BYTE POINTER FUNC ShellScratch()

RETURN(BYTE POINTER(ADDRESS(shell)+SIZE(SCRATCH_OFFSET)))

; Borrow shared space for file data, command arguments or inspection results.
BYTE POINTER FUNC ShellTransfer()

RETURN(BYTE POINTER(ADDRESS(shell)+SIZE(TRANSFER_OFFSET)))

; Keep the original reason a command failed, while allowing a fatal failure
; to end the session when continuing would be unsafe.
PROC ShellFail(LONGINT status,error)

  ; A cleanup call must not replace the first causal error.
  IF shell.status=PROCESS.RETURN_OK THEN
    shell.status=status
    shell.error=error
  FI

  IF status=PROCESS.RETURN_FAIL THEN
    shell.status=PROCESS.RETURN_FAIL
    shell.done=1
  FI

RETURN

; Keep shell text lengths within the command-line limit.
CARD FUNC ShellLength(BYTE POINTER text)

RETURN(CARD(STR.strnlen(text,LINE_LIMIT)))

; Recognize a command regardless of the case typed by the user.
; The expected spelling is uppercase.
BYTE FUNC ShellEqual(BYTE POINTER word SYS.CSTRING expected)
  CARD index
  BYTE value

  LET length=ShellLength(BYTE POINTER(expected))
  index=0
  WHILE index<length DO
    value=word(index)
    IF value>=CHAR_LOWER_A AND value<=CHAR_LOWER_Z THEN
      value==-CASE_DELTA
    FI

    IF value<>expected(index) THEN
      RETURN(0)
    FI

    index==+1
  OD

RETURN(word(index)=ASCII.NUL)

; Let ongoing shell work respond to the user's BREAK request.
; A nonzero result tells the caller to stop its current operation.
BYTE FUNC ShellPoll()

  IF DOS.BreakPending()=0 THEN
    RETURN(0)
  FI

  ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BREAK)

RETURN(1)

; Establish foreground BREAK handling for the current shell interaction.
BYTE FUNC ShellScope()

  IF DOS.BeginForeground(shell.console)<>0 THEN
    RETURN(1)
  FI

  ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())

RETURN(0)

; Finish a canceled console interaction so the next prompt starts cleanly.
; Cleanup must complete even when the user types nothing more.
PROC ShellRetireBreak(BYTE unused)
  BYTE attempt

  IF DOS.BreakPending()=0 THEN
    RETURN
  FI

  FOR attempt=0 TO 2 DO
    BEGIN
      LET count=DOS.Read(shell.console,ShellTransfer(),LINE_CAPACITY)
      LET error=DOS.IoErr()
      IF count<0 THEN
        IF error<>DOS.ERROR_BREAK THEN
          ShellFail(PROCESS.RETURN_FAIL,error)
        FI

        RETURN
      FI
    END
  OD

  ShellFail(PROCESS.RETURN_FAIL,DOS.ERROR_BAD_NUMBER)

RETURN

; Give all shell output the same BREAK and error handling. Failed command
; output stops here, while the console remains available for diagnostics.
PROC ShellWrite(DOS.FileHandle POINTER handle BYTE POINTER bytes CARD count)
  LONGINT error

  IF (shell.status=PROCESS.RETURN_FAIL AND shell.done<>0)
    OR (shell.status<>PROCESS.RETURN_OK AND handle<>shell.console) THEN
    RETURN
  FI

  IF ShellPoll()<>0 THEN
    RETURN
  FI

  LET written=DOS.Write(handle,bytes,count)
  error=DOS.IoErr()
  IF error=DOS.ERROR_BREAK THEN
    ShellFail(PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  IF written<>count THEN
    IF error=0 THEN
      error=DOS.ERROR_BAD_NUMBER
    FI

    ShellFail(IF handle=shell.console THEN PROCESS.RETURN_FAIL

              ELSE PROCESS.RETURN_ERROR FI,error)
  FI

RETURN

; Emit a separator or console control using the shell's output error policy.
PROC ShellByte(DOS.FileHandle POINTER handle BYTE value)

  LET single=ShellScratch()+SIZE(SCRATCH_CAPACITY-1)
  single^=value
  ShellWrite(handle,single,1)

RETURN

; Present a C string through DOS, whether it is a literal or temporary text.
PROC ShellText(DOS.FileHandle POINTER handle SYS.CSTRING text)
  CARD offset,count,index

  LET length=ShellLength(BYTE POINTER(text))
  IF ADDRESS(text)>=ADDRESS($10000) THEN
    ShellWrite(handle,BYTE POINTER(text),length)
    RETURN
  FI

  ; Console I/O admits only writable bank-zero buffers. Stage near literals
  ; in the existing upper-RAM drawing buffer, without another allocation.
  LET buffer=ShellDrawBuffer()
  offset=0
  DO
    count=length-offset
    IF count>DRAW_CAPACITY THEN
      count=DRAW_CAPACITY
    FI

    IF count<>0 THEN
      FOR index=0 TO count-1 DO
        buffer(index)=text(offset+index)
      OD
    FI

    ShellWrite(handle,buffer,count)
    offset==+count
    IF offset=length OR shell.done<>0 THEN
      EXIT
    FI
  OD

RETURN

; Present a signed value in decimal for command reports and diagnostics.
PROC ShellNumber(DOS.FileHandle POINTER handle LONGINT number)
  LONGCARD magnitude
  CARD used

  LET buffer=ShellDrawBuffer()
  used=0
  IF number<0 THEN
    ; Avoid negating MINLONGINT directly.
    magnitude=LONGCARD(-(number+1))+1
    buffer(used)=CHAR_MINUS
    used==+1

  ELSE
    magnitude=LONGCARD(number)
  FI

  used==+STR.u32toa(magnitude,buffer+SIZE(used),DRAW_CAPACITY-used)
  ShellWrite(handle,buffer,used)

RETURN

; Explain a recoverable command failure on the shell's own console.
; User cancellation needs no error message.
PROC ShellDiagnostic()
  CSTRING header

  IF shell.done<>0 OR shell.status=PROCESS.RETURN_OK
      OR shell.error=DOS.ERROR_BREAK
      OR (shell.status=5 AND shell.error=0) THEN
    RETURN
  FI

  LET primary=shell.status
  LET secondary=shell.error
  LET saved=DOS.IoErr()
  header=c"Shell"
  IF shell.diagnosticWord=DIAGNOSTIC_SCRIPT THEN
    header=c"EXECUTE"
  ELSEIF shell.diagnosticWord<shell.argc THEN
    header=CSTRING(shell.words(shell.diagnosticWord).text)
  FI

  IF secondary<>0 THEN
    BEGIN
      LET length=DOS.Fault(secondary,header,ShellTransfer(),TRANSFER_CAPACITY)
      IF length<0 THEN
        shell.done=1
      ELSE
        ShellWrite(shell.console,ShellTransfer(),CARD(length))
        ShellByte(shell.console,ASCII.LF)
      FI
    END
  ELSE
    ShellText(shell.console,header)
    ShellText(shell.console,c": Command returned ")
    ShellNumber(shell.console,primary)
    ShellByte(shell.console,ASCII.LF)
  FI

  ; A failed diagnostic can retire the console, but cannot rewrite the result.
  shell.status=primary
  shell.error=secondary
  DOS.SetIoErr(saved)

RETURN

; History is a prompt feature; keep command results independent of toggles.
; An allocation failure disables optional history for this shell's lifetime.
PROC ShellHistory(BYTE enabled)

  IF shell.historyAvailable=0 THEN
    RETURN
  FI

  LET saved=DOS.IoErr()
  IF DOS.SetConsoleHistory(shell.console,enabled)=0 THEN
    IF enabled<>0 AND DOS.IoErr()=DOS.ERROR_NO_FREE_STORE THEN
      shell.historyAvailable=0
    ELSE
      ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    FI
  FI

  DOS.SetIoErr(saved)

RETURN

; Invite another command on the shell's console, regardless of redirection.
PROC ShellPrompt()

  ShellHistory(1)
  IF shell.done<>0 THEN
    RETURN
  FI

  LET prompt=ShellDrawBuffer()
  prompt(0)=CHAR_GREATER
  prompt(1)=ASCII.SPACE
  ShellWrite(shell.console,prompt,2)

RETURN

; Start a new command line without retaining the previous input.
PROC ShellClear()

  LET line=ShellLine()
  shell.length=0
  line^=ASCII.NUL

RETURN

; Recognize resident commands; other names are candidates for disk loading.
; Ordinary dispatch and pipeline validation use the same classification.
BYTE FUNC ShellClassify(BYTE POINTER word)

  IF ShellEqual(word,c"RUN")<>0 THEN
    RETURN(CMD_RUN)

  ELSEIF ShellEqual(word,c"JOBS")<>0 THEN
    RETURN(CMD_JOBS)

  ELSEIF ShellEqual(word,c"BREAK")<>0 THEN
    RETURN(CMD_BREAK)

  ELSEIF ShellEqual(word,c"EXECUTE")<>0 THEN
    RETURN(CMD_EXECUTE)

  ELSEIF ShellEqual(word,c"HELP")<>0 THEN
    RETURN(CMD_HELP)

  ELSEIF ShellEqual(word,c"ECHO")<>0 THEN
    RETURN(CMD_ECHO)

  ELSEIF ShellEqual(word,c"CLS")<>0 THEN
    RETURN(CMD_CLS)

  ELSEIF ShellEqual(word,c"CD")<>0 THEN
    RETURN(CMD_CD)

  ELSEIF ShellEqual(word,c"EXIT")<>0 THEN
    RETURN(CMD_EXIT)

  ELSEIF ShellEqual(word,c"DIR")<>0 THEN
    RETURN(CMD_DIR)

  ELSEIF ShellEqual(word,c"TYPE")<>0 THEN
    RETURN(CMD_TYPE)

  ELSEIF ShellEqual(word,c"MEM")<>0 THEN
    RETURN(CMD_MEM)

  ELSEIF ShellEqual(word,c"TASKS")<>0 THEN
    RETURN(CMD_TASKS)

  ELSEIF ShellEqual(word,c"VER")<>0 THEN
    RETURN(CMD_VER)

  ELSEIF ShellEqual(word,c"MOUNT")<>0 THEN
    RETURN(CMD_MOUNT)

  ELSEIF ShellEqual(word,c"PATH")<>0 THEN
    RETURN(CMD_PATH)

  ELSEIF ShellEqual(word,c"DEVICES")<>0 THEN
    RETURN(CMD_DEVICES)

  ELSEIF ShellEqual(word,c"ALIAS")<>0 THEN
    RETURN(CMD_ALIAS)

  ELSEIF ShellEqual(word,c"UNALIAS")<>0 THEN
    RETURN(CMD_UNALIAS)
  FI

RETURN(CMD_EXTERNAL)

; Accept the boundary between the two programs supported by a shell pipeline.
; Reject combinations whose stream ownership the shell cannot support.
BYTE FUNC ShellPipeBoundary()

  IF shell.pipeline<>0 OR shell.argc=0 OR shell.outputRedirect<>NO_REDIRECT THEN
    RETURN(0)
  FI

  shell.pipeline=1
  shell.pipelineIndex=CARD(shell.argc)
  shell.secondArgumentOffset=shell.argumentLength+1
  shell.secondArgumentLength=0
  IF shell.secondArgumentOffset>LINE_LIMIT THEN
    RETURN(0)
  FI

  LET arguments=ShellTransfer()+SIZE(LINE_CAPACITY)
  arguments(shell.secondArgumentOffset)=ASCII.NUL

RETURN(1)

; Preserve the user's argument spelling, including quotes and escapes, for
; the loaded program's own argument parser. Redirection is handled separately.
BYTE FUNC ShellArgument(CARD start,finish)
  CARD first,used

  first=0
  used=shell.argumentLength
  IF shell.pipeline<>0 THEN
    first=shell.pipelineIndex
    used=shell.secondArgumentOffset+shell.secondArgumentLength
  FI

  IF CARD(shell.argc)=first THEN
    RETURN(1)
  FI

  LET original=ShellTransfer()
  LET arguments=original+SIZE(LINE_CAPACITY)
  IF CARD(shell.argc)>first+1 THEN
    IF used=LINE_LIMIT THEN
      RETURN(0)
    FI

    arguments(used)=ASCII.SPACE
    used==+1
  FI

  WHILE start<finish DO
    IF used=LINE_LIMIT THEN
      RETURN(0)
    FI

    arguments(used)=original(start)
    used==+1
    start==+1
  OD

  arguments(used)=ASCII.NUL
  IF shell.pipeline<>0 THEN
    shell.secondArgumentLength=used-shell.secondArgumentOffset

  ELSE
    shell.argumentLength=used
  FI

RETURN(1)

; Accept only command lines the shell can execute, before opening resources.
; Prepare arguments, redirection and an optional two-program pipeline.
BYTE FUNC ShellParse()
  BYTE POINTER line
  CARD readAt,writeAt,start,rawStart,rawEnd,index
  BYTE value,quoted,closed,redirect

  line=ShellLine()
  readAt=0
  writeAt=0
  shell.argc=0
  shell.argsUsed=0
  shell.outputAppend=0
  shell.pipeline=0
  shell.pipelineIndex=0
  shell.secondArgumentOffset=0
  shell.secondArgumentLength=0
  shell.firstCommandStart=0
  shell.firstCommandEnd=0
  shell.secondCommandStart=0
  shell.secondCommandEnd=0

  LET original=ShellTransfer()
  LET arguments=original+SIZE(LINE_CAPACITY)
  index=0
  DO
    original(index)=line(index)
    IF line(index)=ASCII.NUL THEN
      EXIT
    FI

    index==+1
    IF index=LINE_CAPACITY THEN
      RETURN(0)
    FI
  OD

  shell.argumentLength=0
  arguments(0)=ASCII.NUL
  shell.inputRedirect=NO_REDIRECT
  shell.outputRedirect=NO_REDIRECT

  DO
    WHILE line(readAt)=ASCII.SPACE OR line(readAt)=ASCII.TAB DO
      readAt==+1
    OD

    IF line(readAt)=CHAR_PIPE THEN
      IF ShellPipeBoundary()=0 THEN
        RETURN(0)
      FI

      readAt==+1
      WHILE line(readAt)=ASCII.SPACE OR line(readAt)=ASCII.TAB DO
        readAt==+1
      OD
    FI

    IF line(readAt)=ASCII.NUL THEN
      EXIT
    FI

    redirect=0
    IF line(readAt)=CHAR_LESS OR line(readAt)=CHAR_GREATER THEN
      redirect=line(readAt)
      readAt==+1
      IF redirect=CHAR_GREATER AND line(readAt)=CHAR_GREATER THEN
        shell.outputAppend=1
        readAt==+1
      FI

      IF redirect=CHAR_LESS AND shell.pipeline<>0 THEN
        RETURN(0)
      FI

      WHILE line(readAt)=ASCII.SPACE OR line(readAt)=ASCII.TAB DO
        readAt==+1
      OD

      IF line(readAt)=ASCII.NUL OR line(readAt)=CHAR_LESS
        OR line(readAt)=CHAR_GREATER OR line(readAt)=CHAR_PIPE THEN
        RETURN(0)
      FI

      IF (redirect=CHAR_LESS AND shell.inputRedirect<>NO_REDIRECT)
        OR (redirect=CHAR_GREATER AND shell.outputRedirect<>NO_REDIRECT) THEN
        RETURN(0)
      FI
    FI

    IF shell.argsUsed=WORD_CAPACITY THEN
      RETURN(0)
    FI

    shell.argsUsed==+1
    start=writeAt
    rawStart=readAt
    quoted=0
    closed=0
    IF line(readAt)=ASCII.DOUBLE_QUOTE THEN
      quoted=1
      readAt==+1
    FI

    DO
      value=line(readAt)
      IF quoted<>0 THEN
        IF value=ASCII.NUL THEN
          RETURN(0)
        FI

        IF value=ASCII.DOUBLE_QUOTE THEN
          readAt==+1
          closed=1
          EXIT
        FI

        IF value=ASCII.ASTERISK THEN
          readAt==+1
          value=line(readAt)
          IF value<>ASCII.ASTERISK AND value<>ASCII.DOUBLE_QUOTE THEN
            RETURN(0)
          FI
        FI

      ELSE
        IF value=ASCII.NUL OR value=ASCII.SPACE
          OR value=ASCII.TAB OR value=CHAR_PIPE THEN
          EXIT
        FI

        IF value=ASCII.DOUBLE_QUOTE OR value=CHAR_LESS
          OR value=CHAR_GREATER OR value=CHAR_SEMICOLON THEN
          RETURN(0)
        FI
      FI

      line(writeAt)=value
      writeAt==+1
      readAt==+1
    OD

    IF quoted<>0 AND (closed=0 OR (line(readAt)<>ASCII.NUL
      AND line(readAt)<>ASCII.SPACE AND line(readAt)<>ASCII.TAB
      AND line(readAt)<>CHAR_PIPE)) THEN
      RETURN(0)
    FI

    rawEnd=readAt
    ; Consume the delimiter before terminating a word at the same address.
    value=line(readAt)
    IF value=ASCII.SPACE OR value=ASCII.TAB OR value=CHAR_PIPE THEN
      readAt==+1
    FI

    line(writeAt)=ASCII.NUL
    writeAt==+1
    IF redirect=CHAR_LESS THEN
      shell.inputRedirect=start

    ELSEIF redirect=CHAR_GREATER THEN
      shell.outputRedirect=start

    ELSE
      IF ShellArgument(rawStart,rawEnd)=0 THEN
        RETURN(0)
      FI

      IF shell.argc=0 THEN
        shell.firstCommandStart=BYTE(rawStart)
        shell.firstCommandEnd=BYTE(rawEnd)

      ELSEIF shell.pipeline<>0
          AND CARD(shell.argc)=shell.pipelineIndex THEN
        shell.secondCommandStart=BYTE(rawStart)
        shell.secondCommandEnd=BYTE(rawEnd)
      FI

      shell.words(shell.argc).text=line+SIZE(start)
      shell.argc==+1
    FI

    IF value=CHAR_PIPE THEN
      IF ShellPipeBoundary()=0 THEN
        RETURN(0)
      FI
    FI

    IF value=ASCII.NUL THEN
      EXIT
    FI
  OD

  shell.command=0
  IF shell.argc=0 THEN
    RETURN(shell.argsUsed=0)
  FI

  line=shell.words(0).text
  shell.command=ShellClassify(line)
  IF shell.pipeline<>0 THEN
    IF CARD(shell.argc)=shell.pipelineIndex
      OR shell.command<>CMD_EXTERNAL OR line(0)=ASCII.NUL THEN
      RETURN(0)
    FI

    line=shell.words(shell.pipelineIndex).text
    IF line(0)=ASCII.NUL OR ShellClassify(line)<>CMD_EXTERNAL THEN
      RETURN(0)
    FI

    RETURN(1)
  FI

  IF (shell.command=CMD_HELP OR shell.command=CMD_EXIT OR shell.command=CMD_CLS
      OR shell.command=CMD_JOBS
      OR (shell.command>=CMD_MEM AND shell.command<=CMD_DEVICES))
    AND shell.argc<>1 THEN
    RETURN(0)
  FI

  IF shell.command=CMD_BREAK AND shell.argc<>2 THEN
    RETURN(0)
  FI

  IF shell.command=CMD_EXECUTE AND (shell.argc<>2
      OR shell.words(1).text^=ASCII.NUL) THEN
    RETURN(0)
  FI

  IF (shell.command=CMD_CD OR shell.command=CMD_DIR OR shell.command=CMD_TYPE)
    AND shell.argc>2 THEN
    RETURN(0)
  FI

  IF (shell.command=CMD_ALIAS AND shell.argc>3)
      OR (shell.command=CMD_UNALIAS AND shell.argc<>2) THEN
    RETURN(0)
  FI

RETURN(1)

; Alias names are simple command words, with no path or shell syntax.
BYTE FUNC ShellAliasName(BYTE POINTER name)
  CARD index
  BYTE value,letter,digit

  FOR index=0 TO ALIAS_NAME_CAPACITY-1 DO
    value=name(index)
    IF value=ASCII.NUL THEN
      RETURN(index<>0)
    FI

    letter=BYTE((value>='A AND value<='Z)
        OR (value>='a AND value<='z))
    digit=BYTE(value>='0 AND value<='9)
    IF (index=0 AND letter=0)
        OR (letter=0 AND digit=0 AND value<>'_ AND value<>'-) THEN
      RETURN(0)
    FI
  OD

RETURN(0)

; Expansions add a command and fixed arguments, never shell operators.
BYTE FUNC ShellAliasText(BYTE POINTER value)
  CARD index
  BYTE current,nonblank

  nonblank=0
  FOR index=0 TO ALIAS_TEXT_CAPACITY-1 DO
    current=value(index)
    IF current=ASCII.NUL THEN
      RETURN(nonblank)
    FI

    IF current<ASCII.SPACE OR current>CHAR_LAST_PRINTABLE
        OR current=CHAR_PIPE OR current=CHAR_LESS
        OR current=CHAR_GREATER OR current=CHAR_SEMICOLON
        OR current=ASCII.DOUBLE_QUOTE THEN
      RETURN(0)
    FI

    IF current<>ASCII.SPACE THEN
      nonblank=1
    FI
  OD

RETURN(0)

BYTE FUNC ShellAliasIndex(BYTE POINTER name)
  BYTE index

  IF aliases=NULL THEN
    RETURN(ALIAS_CAPACITY)
  FI

  FOR index=0 TO ALIAS_CAPACITY-1 DO
    IF aliases(index).name(0)<>ASCII.NUL
        AND ShellEqual(name,CSTRING(@aliases(index).name(0)))<>0 THEN
      RETURN(index)
    FI
  OD

RETURN(ALIAS_CAPACITY)

PROC ShellAliasShow(BYTE index)

  LET output=DOS.Output()
  ShellText(output,CSTRING(@aliases(index).name(0)))
  ShellText(output,c" -> ")
  ShellText(output,CSTRING(@aliases(index).text(0)))
  ShellByte(output,ASCII.LF)

RETURN

; Store a validated alias in the existing bounded session table.
PROC ShellAliasSet(BYTE POINTER name,text)
  ShellAlias POINTER entry
  BYTE index,position,value

  index=ShellAliasIndex(name)
  IF index=ALIAS_CAPACITY THEN
    IF aliasCount=ALIAS_CAPACITY THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BUFFER_OVERFLOW)
      RETURN
    FI

    IF aliases=NULL THEN
      aliases=ShellAlias POINTER(EXEC.AllocMem(
          ALIAS_CAPACITY*SIZEOF(ShellAlias),EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
      IF aliases=NULL THEN
        ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
        RETURN
      FI
    FI

    FOR position=0 TO ALIAS_CAPACITY-1 DO
      IF aliases(position).name(0)=ASCII.NUL THEN
        index=position
        EXIT
      FI
    OD

    aliasCount==+1
  FI

  entry=@aliases(index)
  FOR position=0 TO ALIAS_NAME_CAPACITY-1 DO
    value=name(position)
    IF value>='a AND value<='z THEN
      value==-CASE_DELTA
    FI

    entry.name(position)=value
    IF value=ASCII.NUL THEN
      EXIT
    FI
  OD

  STR.strlcpy(@entry.text(0),CSTRING(text),ALIAS_TEXT_CAPACITY)

RETURN

; Default aliases are ordinary entries: users can replace or remove them.
BYTE FUNC ShellAliasDefaults()

  ShellAliasSet(BYTE POINTER(c"MKDIR"),BYTE POINTER(c"MAKEDIR"))
  IF aliases=NULL THEN
    RETURN(0)
  FI

  ShellAliasSet(BYTE POINTER(c"LS"),BYTE POINTER(c"LIST"))
  ShellAliasSet(BYTE POINTER(c"CP"),BYTE POINTER(c"COPY"))

RETURN(aliasCount=3)

; List, inspect or change the session's aliases using the same validation.
PROC ShellAliasCommand()
  BYTE index

  IF shell.argc=1 THEN
    IF aliases<>NULL THEN
      FOR index=0 TO ALIAS_CAPACITY-1 DO
        IF aliases(index).name(0)<>ASCII.NUL THEN
          IF ShellPoll()<>0 THEN
            RETURN
          FI

          ShellAliasShow(index)
          IF shell.status<>PROCESS.RETURN_OK THEN
            RETURN
          FI
        FI
      OD
    FI

    RETURN
  FI

  LET name=shell.words(1).text
  IF ShellAliasName(name)=0 OR ShellClassify(name)<>CMD_EXTERNAL THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BAD_ARGUMENTS)
    RETURN
  FI

  IF shell.argc=2 THEN
    index=ShellAliasIndex(name)
    IF index=ALIAS_CAPACITY THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_NOT_FOUND)
    ELSE
      ShellAliasShow(index)
    FI

    RETURN
  FI

  LET text=shell.words(2).text
  IF ShellAliasText(text)=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BAD_ARGUMENTS)
    RETURN
  FI

  ShellAliasSet(name,text)

RETURN

PROC ShellUnaliasCommand()

  LET name=shell.words(1).text
  LET index=ShellAliasIndex(name)
  IF index=ALIAS_CAPACITY THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_NOT_FOUND)
    RETURN
  FI

  aliases(index).name(0)=ASCII.NUL
  aliases(index).text(0)=ASCII.NUL
  aliasCount==-1

RETURN

; Rewrite one already-parsed command word, then parse the bounded result.
; The right pipeline stage is rewritten first so its original span is valid.
BYTE FUNC ShellAliasReplace(BYTE stage)
  BYTE index,start,finish
  CARD sourceLength,textLength,total,offset
  BYTE POINTER source,target,line

  IF stage=0 THEN
    index=ShellAliasIndex(shell.words(0).text)
    start=shell.firstCommandStart
    finish=shell.firstCommandEnd
  ELSE
    index=ShellAliasIndex(shell.words(shell.pipelineIndex).text)
    start=shell.secondCommandStart
    finish=shell.secondCommandEnd
  FI

  IF index=ALIAS_CAPACITY THEN
    RETURN(1)
  FI

  source=ShellTransfer()
  target=ShellScratch()
  line=ShellLine()
  LET expansion=@aliases(index).text(0)
  sourceLength=ShellLength(source)
  textLength=ShellLength(expansion)
  total=sourceLength-CARD(finish-start)+textLength
  IF total>LINE_LIMIT THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_LINE_TOO_LONG)
    RETURN(0)
  FI

  IF start<>0 THEN
    FOR offset=0 TO CARD(start)-1 DO
      target(offset)=source(offset)
    OD
  FI

  FOR offset=0 TO textLength-1 DO
    target(CARD(start)+offset)=expansion(offset)
  OD

  FOR offset=finish TO sourceLength DO
    target(CARD(start)+textLength+offset-CARD(finish))=source(offset)
  OD

  FOR offset=0 TO total DO
    line(offset)=target(offset)
  OD

  IF ShellParse()=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BAD_ARGUMENTS)
    RETURN(0)
  FI

RETURN(1)

BYTE FUNC ShellAliasExpand()

  IF aliasCount=0 THEN
    RETURN(1)
  FI

  IF shell.pipeline<>0 AND ShellAliasReplace(1)=0 THEN
    RETURN(0)
  FI

RETURN(ShellAliasReplace(0))

; Select a new working directory, retaining the old one if selection fails.
PROC ShellChange(BYTE POINTER path)
  DOS.FileLock POINTER previous

  LET candidate=DOS.Lock(path,DOS.SHARED_LOCK)
  LET lockError=DOS.IoErr()
  IF candidate=NULL THEN
    ShellFail(PROCESS.RETURN_ERROR,lockError)
    RETURN
  FI

  shell.retiredDirectory=candidate
  IF ShellPoll()<>0 THEN
    ShellReleaseLock()
    RETURN
  FI

  previous=DOS.CurrentDir(candidate)
  LET error=DOS.IoErr()
  IF error<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,error)
    ; Validate the retained default and clear IoErr before the void UnLock.
    ; Its successful return otherwise preserves the earlier selector error.
    previous=DOS.CurrentDir(shell.directory)
    IF DOS.IoErr()<>0 THEN
      ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN
    FI

  ELSE
    shell.directory=candidate
    shell.retiredDirectory=previous
  FI

  DOS.UnLock(shell.retiredDirectory)
  IF DOS.IoErr()<>0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())

  ELSE
    shell.retiredDirectory=NULL
  FI

RETURN

INCLUDE "shell-commands.inc"
INCLUDE "shell-redirection.inc"
INCLUDE "shell-path.inc"
INCLUDE "shell-jobs.inc"
INCLUDE "shell-execute.inc"

; Run a disk command in the foreground and keep its result for the shell.
PROC ShellExternal()
  PROCESS.Result outcome

  LET image=ShellLoadCommand(shell.words(0).text)
  LET loadError=DOS.IoErr()
  IF image=NULL THEN
    ShellFail(PROCESS.RETURN_ERROR,loadError)
    RETURN
  FI

  LET arguments=ShellTransfer()+SIZE(LINE_CAPACITY)
  LET identity=PROCESS.StartLoaded(
      BYTE POINTER(image),arguments,shell.argumentLength,1)
  LET error=DOS.IoErr()
  PROGRAM.Unload(image)
  IF identity=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  IF PROCESS.Wait(identity,@outcome)=0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN
  FI

  shell.status=outcome.primary
  shell.error=outcome.secondary

RETURN

; Run two disk commands as one foreground job, with the first feeding the
; second. PIPELINE owns the stream connection and child lifetimes.
PROC ShellPipeline()
  PIPELINE.Outcome outcome

  LET first=ShellLoadCommand(shell.words(0).text)
  LET firstError=DOS.IoErr()
  IF first=NULL THEN
    ShellFail(PROCESS.RETURN_ERROR,firstError)
    RETURN
  FI

  shell.diagnosticWord=BYTE(shell.pipelineIndex)
  LET second=ShellLoadCommand(shell.words(shell.pipelineIndex).text)
  LET secondError=DOS.IoErr()
  IF second=NULL THEN
    PROGRAM.Unload(first)
    ShellFail(PROCESS.RETURN_ERROR,secondError)
    RETURN
  FI

  LET arguments=ShellTransfer()+SIZE(LINE_CAPACITY)
  LET accepted=PIPELINE.Run(
      BYTE POINTER(first),BYTE POINTER(second),arguments,
      arguments+SIZE(shell.secondArgumentOffset),
      shell.argumentLength,shell.secondArgumentLength,@outcome)
  PROGRAM.Unload(first)
  PROGRAM.Unload(second)
  IF accepted=0 THEN
    shell.diagnosticWord=$ff
    ShellFail(outcome.primary,outcome.secondary)

  ELSE
    shell.status=outcome.primary
    shell.error=outcome.secondary
    shell.diagnosticWord=0
    IF outcome.second.primary=outcome.primary
        AND outcome.second.secondary=outcome.secondary
        AND (outcome.first.primary<>outcome.primary
        OR outcome.first.secondary<>outcome.secondary) THEN
      shell.diagnosticWord=BYTE(shell.pipelineIndex)
    FI
  FI

RETURN

; Carry out a validated command using the streams selected for this invocation.
PROC ShellDispatch()
  CARD index

  CASE shell.command OF
  WHEN CMD_HELP THEN
    ShellText(DOS.Output(),
        c"HELP ECHO CLS CD DIR TYPE MEM TASKS VER MOUNT DEVICES PATH ALIAS UNALIAS RUN JOBS BREAK EXECUTE EXIT")
    ShellByte(DOS.Output(),ASCII.LF)
    ShellText(DOS.Output(),c"Edit: Ctrl-A/E home/end, B/F left/right\n")
    ShellText(DOS.Output(),c"Ctrl-U clear, K cut end, W cut word\n")
    ShellText(DOS.Output(),c"Ctrl-L clear screen\n")
    ShellText(DOS.Output(),c"History: Ctrl-P/N or Atari up/down\n")
    ShellText(DOS.Output(),c"Atari left/right move the cursor\n")

  WHEN CMD_ECHO THEN
    IF shell.argc>1 THEN
      FOR index=1 TO CARD(shell.argc)-1 DO
        IF index<>1 THEN
          ShellByte(DOS.Output(),ASCII.SPACE)
        FI

        ShellText(DOS.Output(),CSTRING(shell.words(index).text))
      OD
    FI

    ShellByte(DOS.Output(),ASCII.LF)

  WHEN CMD_CLS THEN
    ShellByte(DOS.Output(),ASCII.FF)

  WHEN CMD_CD THEN
    IF shell.argc=2 THEN
      IF ShellEqual(shell.words(1).text,c"..")<>0 THEN
        ShellChange(BYTE POINTER(c"/"))
      ELSE
        ShellChange(shell.words(1).text)
      FI

    ELSEIF DOS.NameFromLock(shell.directory,ShellScratch(),LINE_CAPACITY)=0 THEN
      ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())

    ELSE
      ShellText(DOS.Output(),CSTRING(ShellScratch()))
      ShellByte(DOS.Output(),ASCII.LF)
    FI

  WHEN CMD_EXIT THEN
    shell.done=1

  WHEN CMD_DIR THEN
    ShellDir()

  WHEN CMD_TYPE THEN
    ShellType()

  WHEN CMD_MEM THEN
    ShellMem()

  WHEN CMD_TASKS THEN
    ShellTasks(DOS.Output())

  WHEN CMD_VER THEN
    ShellText(DOS.Output(),CSTRING(EXECBUILD.version))

  WHEN CMD_MOUNT THEN
    ShellMounts(DOS.Output())

  WHEN CMD_DEVICES THEN
    ShellDevices(DOS.Output())

  WHEN CMD_PATH THEN
    ShellPath()

  WHEN CMD_ALIAS THEN
    ShellAliasCommand()

  WHEN CMD_UNALIAS THEN
    ShellUnaliasCommand()

  WHEN CMD_JOBS THEN
    ShellJobs()

  WHEN CMD_BREAK THEN
    ShellBreakJob()

  WHEN CMD_EXECUTE THEN
    ShellScriptOpen(shell.words(1).text,0)

  WHEN CMD_EXTERNAL THEN
    IF shell.background<>0 THEN
      ShellRun()

    ELSEIF shell.pipeline<>0 THEN
      ShellPipeline()

    ELSE
      ShellExternal()
    FI
  ESAC

RETURN

; Own one command's complete interaction: its foreground scope, temporary
; streams and final result must be settled before the next prompt.
PROC ShellOneCommand()

  IF shell.done<>0 THEN
    RETURN
  FI

  shell.status=PROCESS.RETURN_OK
  shell.error=0
  shell.diagnosticWord=$ff
  ShellCollectJob()
  IF shell.done<>0 THEN
    RETURN
  FI

  IF ShellPoll()=0 THEN
    IF ShellScope()<>0 THEN
      IF ShellPrepareCommand()=0 THEN
        ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BAD_NUMBER)

      ELSEIF shell.command=CMD_EXECUTE AND script<>NULL THEN
        ; Reject nesting before its redirections can create or truncate files.
        shell.diagnosticWord=0
        ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_ACTION_NOT_KNOWN)

      ELSE
        IF ShellRedirect()<>0 THEN
          IF ShellPoll()=0 THEN
            shell.diagnosticWord=0
            ShellDispatch()
          FI
        FI
      FI
    FI
  FI

  IF DOS.BreakPending()<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_BREAK)
  FI

  ShellUnredirect()
  ShellRetireBreak(0)
  IF shell.done=0 THEN
    IF ShellScope()<>0 THEN
      ShellDiagnostic()
      ShellJobAnnounce()
    FI
  FI

  shell.lastStatus=shell.status
  shell.lastError=shell.error

RETURN

; Finish an opened script through ordinary dispatch. Startup uses the same
; loop without creating a prompt or recording synthetic input in history.
PROC ShellRunScript()

  IF script<>NULL THEN
    WHILE shell.done=0 AND shell.status<PROCESS.RETURN_ERROR DO
      BEGIN
        LET primary=shell.status
        LET secondary=shell.error
        shell.status=PROCESS.RETURN_OK
        shell.error=0
        shell.diagnosticWord=DIAGNOSTIC_SCRIPT
        shell.command=CMD_EXECUTE
        shell.argc=0
        IF ShellScriptNext()=0 THEN
          IF shell.status=PROCESS.RETURN_OK THEN
            shell.status=primary
            shell.error=secondary
          ELSE
            ShellDiagnostic()
          FI

          EXIT
        FI

        ShellOneCommand()
      END
    OD

    BEGIN
      LET primary=shell.status
      LET secondary=shell.error
      ShellScriptClose()
      IF shell.status<>primary OR shell.error<>secondary THEN
        shell.command=CMD_EXECUTE
        shell.argc=0
        shell.diagnosticWord=DIAGNOSTIC_SCRIPT
        ShellDiagnostic()
      FI
    END
  FI

  ShellRetireBreak(0)
  IF shell.done=0 THEN
    ShellScope()
  FI

  shell.lastStatus=shell.status
  shell.lastError=shell.error

RETURN

; Reuse ordinary execution without recursive dispatch or changing command Input.
PROC ShellCommand()

  ShellOneCommand()
  IF script<>NULL THEN
    ShellRunScript()
  FI

RETURN

; Advance the interactive session as console input becomes available.
; Complete lines run as commands; cancellation returns to a fresh prompt.
PROC ShellReadStep()
  CARD limit

  IF shell.done<>0 THEN
    RETURN
  FI

  LET line=ShellLine()
  limit=LINE_CAPACITY-shell.length
  IF limit>READ_CHUNK_SIZE THEN
    limit=READ_CHUNK_SIZE
  FI

  LET count=DOS.Read(shell.console,line+SIZE(shell.length),limit)
  LET error=DOS.IoErr()
  IF count>0 THEN
    shell.length==+CARD(count)
    IF line(shell.length-1)=ASCII.LF THEN
      shell.length==-1
      line(shell.length)=ASCII.NUL
      ShellHistory(0)
      ShellCommand()
      ShellClear()
      IF shell.done=0 THEN
        ShellPrompt()
      FI
    FI

  ELSEIF count=0 THEN
    ShellHistory(0)
    ; Ctrl-D may seal an unterminated final command before its one-shot EOF.
    line(shell.length)=ASCII.NUL
    IF shell.length<>0 THEN
      ShellCommand()
    FI

    shell.done=1

  ELSEIF error=DOS.ERROR_BREAK OR error=DOS.ERROR_LINE_TOO_LONG
        OR error=DOS.ERROR_BUFFER_OVERFLOW THEN
    ShellHistory(0)
    IF shell.done<>0 THEN
      RETURN
    FI

    ShellClear()
    shell.diagnosticWord=$ff
    shell.status=PROCESS.RETURN_OK
    shell.error=0
    IF ShellScope()=0 THEN
      RETURN
    FI

    IF error<>DOS.ERROR_BREAK THEN
      shell.status=PROCESS.RETURN_ERROR
      shell.error=error
      IF error=DOS.ERROR_BUFFER_OVERFLOW THEN
        ShellText(shell.console,c"Input lost; line discarded")
        ShellByte(shell.console,ASCII.LF)

      ELSE
        ShellDiagnostic()
      FI
    FI

    shell.lastStatus=shell.status
    shell.lastError=shell.error
    ShellPrompt()

  ELSE
    ShellHistory(0)
    ShellFail(PROCESS.RETURN_FAIL,error)
  FI

RETURN

; Establish a shell session while preserving the caller's default streams.
; ShellFinish also handles a session whose setup succeeds only partly.
BYTE FUNC ShellOpen(BYTE POINTER consoleName)

  shell=ShellState POINTER(
      EXEC.AllocMem(SHELL_BYTES,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
  IF shell=NULL THEN
    RETURN(0)
  FI

  aliases=NULL
  script=NULL
  aliasCount=0
  job.identity=0
  job.state=0
  job.announce=0
  shell.historyAvailable=1
  ShellPathReset()
  shell.diagnosticWord=$ff
  shell.console=DOS.Open(consoleName,DOS.MODE_READWRITE)
  IF shell.console=NULL THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  shell.initialInput=DOS.SelectInput(shell.console)
  IF DOS.IoErr()<>0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  shell.initialized=1
  shell.initialOutput=DOS.SelectOutput(shell.console)
  IF DOS.IoErr()<>0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  shell.initialized=2

  IF ShellScope()=0 THEN
    RETURN(0)
  FI

RETURN(ShellAliasDefaults())

; Make the shell ready for input, reporting any recoverable startup failure.
PROC ShellInitialPrompt()

  shell.lastStatus=shell.status
  shell.lastError=shell.error
  ShellDiagnostic()
  ShellPrompt()

RETURN

; Start a session on an already running system, optionally in a given directory.
BYTE FUNC ShellStart(BYTE POINTER initial)

  IF ShellOpen(shellCon)=0 THEN
    RETURN(0)
  FI

  IF initial<>NULL THEN
    ShellChange(initial)
  FI

  ShellInitialPrompt()

RETURN(shell.done=0)

; End the session and return its status without releasing resources still
; in use. The same cleanup applies after partial startup or a command failure.
LONGINT FUNC ShellFinish()
  DOS.FileHandle POINTER ignored

  IF shell=NULL THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  IF ShellStopJob()=0 THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  ShellScriptClose()
  IF script<>NULL THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  ShellUnredirect()
  IF shell.redirectActive<>0 THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  ; Selected resources are borrowed. Detach them before releasing ownership.
  IF shell.initialized>=1 THEN
    ignored=DOS.SelectInput(shell.initialInput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN(PROCESS.RETURN_FAIL)
    FI
  FI

  IF shell.initialized>=2 THEN
    ignored=DOS.SelectOutput(shell.initialOutput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN(PROCESS.RETURN_FAIL)
    FI
  FI

  LET previous=DOS.CurrentDir(NULL)
  IF DOS.IoErr()<>0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  DOS.UnLock(previous)
  IF DOS.IoErr()<>0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  shell.directory=NULL
  DOS.UnLock(shell.retiredDirectory)
  IF DOS.IoErr()<>0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  shell.retiredDirectory=NULL
  ShellCloseCommandInput()
  IF shell.commandInput<>NULL THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  IF DOS.EndForeground()=0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  IF shell.console<>NULL THEN
    IF DOS.Close(shell.console)=0 THEN
      ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN(PROCESS.RETURN_FAIL)
    FI

    shell.console=NULL
  FI

  IF DOS.ReleaseContext()=0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  LET result=shell.status
  IF aliases<>NULL THEN
    EXEC.FreeMem(BYTE POINTER(aliases),ALIAS_CAPACITY*SIZEOF(ShellAlias))
    aliases=NULL
    aliasCount=0
  FI

  EXEC.FreeMem(BYTE POINTER(shell),SHELL_BYTES)
  shell=NULL

RETURN(result)
