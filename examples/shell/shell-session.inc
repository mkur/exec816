; Resident application code, shared by the entry point and native fixtures.
USE EXEC
USE HEAPCORE
USE CONSOLE
USE CONSOLETYPES
USE DESKSTATE
USE DESKBOOT
USE DESKTYPES
USE DOSCLIENT
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
USE FSTYPES
USE FSDISCOVER
USE FSNAMES
USE FS83
USE IDEPLUS
USE IDEPLUSDRIVER
USE BLOCKTYPES
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
CONST EDIT_OFFSET=PATH_OFFSET+PATH_CAPACITY*LINE_CAPACITY
CONST EDIT_BYTES=20
CONST COMPLETION_PATH_OFFSET=EDIT_OFFSET+EDIT_BYTES
CONST SHELL_BYTES=COMPLETION_PATH_OFFSET+LINE_CAPACITY
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
CONST CMD_UNMOUNT=21
CONST CMD_NEWSHELL=22,CMD_SESSIONS=23,CMD_SESSION=24
CONST JOB_RUNNING=1,JOB_STOPPING=2,JOB_DONE=3

TYPE ShellEditState=[
  DOS.ConsoleEditState edit
  CARD first,component,common
  BYTE matches,directory
]

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

; Allocated only while EXECUTE owns a script and its inherited streams.
TYPE ShellScript=[
  DOS.FileHandle POINTER source
  DOS.FileHandle POINTER oldInput,oldOutput,tempInput,tempOutput
  CARD used,available
  BYTE redirectActive,previousCR
  BYTE ARRAY bytes(READ_CHUNK_SIZE)
]

INCLUDE "shell-session-types.inc"
INCLUDE "shell-context-types.inc"
INCLUDE "shell-session-client.inc"

BYTE ARRAY shellCon=c"CON:"
BYTE ARRAY shellRoot=c"SYS:"

; Borrow the current command line, shared by input collection and parsing.
BYTE POINTER FUNC ShellLine(ShellContext POINTER context)

RETURN(BYTE POINTER(ADDRESS(context.shell)+SIZE(HEADER_SIZE)))

; Borrow temporary output space; callers must not retain its contents.
BYTE POINTER FUNC ShellDrawBuffer(ShellContext POINTER context)

RETURN(BYTE POINTER(ADDRESS(context.shell)+SIZE(DRAW_OFFSET)))

; Borrow workspace for paths and directory information.
BYTE POINTER FUNC ShellScratch(ShellContext POINTER context)

RETURN(BYTE POINTER(ADDRESS(context.shell)+SIZE(SCRATCH_OFFSET)))

; Borrow shared space for file data, command arguments or inspection results.
BYTE POINTER FUNC ShellTransfer(ShellContext POINTER context)

RETURN(BYTE POINTER(ADDRESS(context.shell)+SIZE(TRANSFER_OFFSET)))

; Borrow prompt state without enlarging the stable command-state header.
ShellEditState POINTER FUNC ShellEdit(ShellContext POINTER context)

RETURN(ShellEditState POINTER(ADDRESS(context.shell)+SIZE(EDIT_OFFSET)))

; Parent names must survive Examine overwriting the shared scratch FIB.
BYTE POINTER FUNC ShellCompletionPath(ShellContext POINTER context)

RETURN(BYTE POINTER(ADDRESS(context.shell)+SIZE(COMPLETION_PATH_OFFSET)))

; Keep the original reason a command failed, while allowing a fatal failure
; to end the session when continuing would be unsafe.
PROC ShellFail(ShellContext POINTER context LONGINT status,error)

  ; A cleanup call must not replace the first causal error.
  IF context.shell.status=PROCESS.RETURN_OK THEN
    context.shell.status=status
    context.shell.error=error
  FI

  IF status=PROCESS.RETURN_FAIL THEN
    context.shell.status=PROCESS.RETURN_FAIL
    context.shell.done=1
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

; Controller close intent survives scope renewal and a previously unbound route.
BYTE FUNC ShellClosing(ShellContext POINTER context)

  IF context.control<>NULL THEN
    IF context.control.closeRequested<>0 THEN
      context.shell.done=1
      RETURN(1)
    FI
  FI

RETURN(0)

; Let ongoing shell work respond to the user's BREAK request.
; A nonzero result tells the caller to stop its current operation.
BYTE FUNC ShellPoll(ShellContext POINTER context)

  IF ShellClosing(context)<>0 THEN
    RETURN(1)
  FI

  IF DOS.BreakPending()=0 THEN
    RETURN(0)
  FI

  ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BREAK)

RETURN(1)

; Establish foreground BREAK handling for the current shell interaction.
BYTE FUNC ShellScope(ShellContext POINTER context)

  IF ShellClosing(context)<>0 THEN
    RETURN(0)
  FI

  IF DOS.BeginForeground(context.shell.console)<>0 THEN
    RETURN(ShellClosing(context)=0)
  FI

  ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())

RETURN(0)

; Finish a canceled console interaction so the next prompt starts cleanly.
; Cleanup must complete even when the user types nothing more.
PROC ShellRetireBreak(ShellContext POINTER context BYTE unused)
  BYTE attempt

  IF DOS.BreakPending()=0 THEN
    RETURN
  FI

  FOR attempt=0 TO 2 DO
    BEGIN
      LET count=DOS.Read(context.shell.console,ShellTransfer(context),LINE_CAPACITY)
      LET error=DOS.IoErr()
      IF count<0 THEN
        IF error<>DOS.ERROR_BREAK THEN
          ShellFail(context,PROCESS.RETURN_FAIL,error)
        FI

        RETURN
      FI
    END
  OD

  ShellFail(context,PROCESS.RETURN_FAIL,DOS.ERROR_BAD_NUMBER)

RETURN

; Give all shell output the same BREAK and error handling. Failed command
; output stops here, while the console remains available for diagnostics.
PROC ShellWrite(ShellContext POINTER context
    DOS.FileHandle POINTER handle BYTE POINTER bytes CARD count)
  LONGINT error

  IF (context.shell.status=PROCESS.RETURN_FAIL AND context.shell.done<>0)
    OR (context.shell.status<>PROCESS.RETURN_OK AND handle<>context.shell.console) THEN
    RETURN
  FI

  IF ShellPoll(context)<>0 THEN
    RETURN
  FI

  LET written=DOS.Write(handle,bytes,count)
  error=DOS.IoErr()
  IF error=DOS.ERROR_BREAK THEN
    ShellFail(context,PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  IF written<>count THEN
    IF error=0 THEN
      error=DOS.ERROR_BAD_NUMBER
    FI

    ShellFail(context,IF handle=context.shell.console THEN PROCESS.RETURN_FAIL

              ELSE PROCESS.RETURN_ERROR FI,error)
  FI

RETURN

; Emit a separator or console control using the shell's output error policy.
PROC ShellByte(ShellContext POINTER context
    DOS.FileHandle POINTER handle BYTE value)

  LET single=ShellScratch(context)+SIZE(SCRATCH_CAPACITY-1)
  single^=value
  ShellWrite(context,handle,single,1)

RETURN

; Present a C string through DOS, whether it is a literal or temporary text.
PROC ShellText(ShellContext POINTER context
    DOS.FileHandle POINTER handle SYS.CSTRING text)
  CARD offset,count,index

  LET length=ShellLength(BYTE POINTER(text))
  IF ADDRESS(text)>=ADDRESS($10000) THEN
    ShellWrite(context,handle,BYTE POINTER(text),length)
    RETURN
  FI

  ; Console I/O admits only writable bank-zero buffers. Stage near literals
  ; in the existing upper-RAM drawing buffer, without another allocation.
  LET buffer=ShellDrawBuffer(context)
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

    ShellWrite(context,handle,buffer,count)
    offset==+count
    IF offset=length OR context.shell.done<>0 THEN
      EXIT
    FI
  OD

RETURN

; Present a signed value in decimal for command reports and diagnostics.
PROC ShellNumber(ShellContext POINTER context
    DOS.FileHandle POINTER handle LONGINT number)
  LONGCARD magnitude
  CARD used

  LET buffer=ShellDrawBuffer(context)
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
  ShellWrite(context,handle,buffer,used)

RETURN

; Assemble report rows in the existing draw buffer. Oversized rows stream in
; bounded chunks; callers finish each row explicitly, through ShellWrite.
; Sources must not borrow the draw buffer while a row is being assembled.
CARD FUNC ShellRowBytes(ShellContext POINTER context
    DOS.FileHandle POINTER output CARD used
    BYTE POINTER bytes CARD length)
  CARD offset,count

  LET buffer=ShellDrawBuffer(context)
  offset=0
  WHILE offset<length DO
    IF used=DRAW_CAPACITY THEN
      ShellWrite(context,output,buffer,used)
      used=0
    FI

    count=length-offset
    IF count>DRAW_CAPACITY-used THEN
      count=DRAW_CAPACITY-used
    FI

    A816MEMORY.Move(buffer+SIZE(used),bytes+SIZE(offset),count)
    used==+count
    offset==+count
  OD

RETURN(used)

CARD FUNC ShellRowText(ShellContext POINTER context
    DOS.FileHandle POINTER output CARD used CSTRING text)

RETURN(ShellRowBytes(context,output,used,BYTE POINTER(text),
    ShellLength(BYTE POINTER(text))))

CARD FUNC ShellRowByte(ShellContext POINTER context
    DOS.FileHandle POINTER output CARD used BYTE value)

  LET buffer=ShellDrawBuffer(context)
  IF used=DRAW_CAPACITY THEN
    ShellWrite(context,output,buffer,used)
    used=0
  FI

  buffer(used)=value

RETURN(used+1)

; Ten decimal digits and the terminator fit even for MAXLONGCARD.
CARD FUNC ShellRowUnsigned(ShellContext POINTER context
    DOS.FileHandle POINTER output CARD used
    LONGCARD number)

  IF used>DRAW_CAPACITY-11 THEN
    ShellWrite(context,output,ShellDrawBuffer(context),used)
    used=0
  FI

RETURN(used+CARD(STR.u32toa(number,ShellDrawBuffer(context)+SIZE(used),
    DRAW_CAPACITY-used)))

CARD FUNC ShellRowNumber(ShellContext POINTER context
    DOS.FileHandle POINTER output CARD used LONGINT number)
  LONGCARD magnitude

  IF number<0 THEN
    IF used>DRAW_CAPACITY-12 THEN
      ShellWrite(context,output,ShellDrawBuffer(context),used)
      used=0
    FI

    used=ShellRowByte(context,output,used,CHAR_MINUS)
    ; Avoid negating MINLONGINT directly.
    magnitude=LONGCARD(-(number+1))+1
  ELSE
    magnitude=LONGCARD(number)
  FI

RETURN(ShellRowUnsigned(context,output,used,magnitude))

PROC ShellRowEnd(ShellContext POINTER context
    DOS.FileHandle POINTER output CARD used)

  used=ShellRowByte(context,output,used,ASCII.LF)
  ShellWrite(context,output,ShellDrawBuffer(context),used)

RETURN

PROC ShellLineText(ShellContext POINTER context
    DOS.FileHandle POINTER output CSTRING text)

  ShellRowEnd(context,output,ShellRowText(context,output,0,text))

RETURN

; Explain a recoverable command failure on the shell's own console.
; User cancellation needs no error message.
PROC ShellDiagnostic(ShellContext POINTER context)
  CSTRING header

  IF context.shell.done<>0 OR context.shell.status=PROCESS.RETURN_OK
      OR context.shell.error=DOS.ERROR_BREAK
      OR (context.shell.status=5 AND context.shell.error=0) THEN
    RETURN
  FI

  LET primary=context.shell.status
  LET secondary=context.shell.error
  LET saved=DOS.IoErr()
  header=c"Shell"
  IF context.shell.diagnosticWord=DIAGNOSTIC_SCRIPT THEN
    header=c"EXECUTE"
  ELSEIF context.shell.diagnosticWord<context.shell.argc THEN
    header=CSTRING(context.shell.words(context.shell.diagnosticWord).text)
  FI

  IF secondary<>0 THEN
    BEGIN
      LET length=DOS.Fault(secondary,header,ShellTransfer(context),TRANSFER_CAPACITY)
      IF length<0 THEN
        context.shell.done=1
      ELSE
        ShellWrite(context,context.shell.console,ShellTransfer(context),CARD(length))
        ShellByte(context,context.shell.console,ASCII.LF)
      FI
    END
  ELSE
    ShellText(context,context.shell.console,header)
    ShellText(context,context.shell.console,c": Command returned ")
    ShellNumber(context,context.shell.console,primary)
    ShellByte(context,context.shell.console,ASCII.LF)
  FI

  ; A failed diagnostic can retire the console, but cannot rewrite the result.
  context.shell.status=primary
  context.shell.error=secondary
  DOS.SetIoErr(saved)

RETURN

; History is a prompt feature; keep command results independent of toggles.
; An allocation failure disables optional history for this shell's lifetime.
PROC ShellHistory(ShellContext POINTER context BYTE enabled)

  IF context.shell.historyAvailable=0 THEN
    RETURN
  FI

  LET saved=DOS.IoErr()
  IF DOS.SetConsoleHistory(context.shell.console,enabled)=0 THEN
    IF enabled<>0 AND DOS.IoErr()=DOS.ERROR_NO_FREE_STORE THEN
      context.shell.historyAvailable=0
    ELSE
      ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    FI
  FI

  DOS.SetIoErr(saved)

RETURN

; Invite another command on the shell's console, regardless of redirection.
PROC ShellPrompt(ShellContext POINTER context)

  LET state=ShellEdit(context)
  state.edit.action=DOS.CONEDIT_START
  ShellHistory(context,1)
  IF context.shell.done<>0 THEN
    RETURN
  FI

  LET prompt=ShellDrawBuffer(context)
  prompt(0)=CHAR_GREATER
  prompt(1)=ASCII.SPACE
  ShellWrite(context,context.shell.console,prompt,2)

RETURN

; Start a new command line without retaining the previous input.
PROC ShellClear(ShellContext POINTER context)

  LET line=ShellLine(context)
  context.shell.length=0
  line^=ASCII.NUL

RETURN

; One name definition serves command dispatch and prompt completion.
CSTRING FUNC ShellCommandName(BYTE command)

  CASE command OF
  WHEN CMD_HELP THEN
    RETURN(c"HELP")

  WHEN CMD_ECHO THEN
    RETURN(c"ECHO")

  WHEN CMD_CD THEN
    RETURN(c"CD")

  WHEN CMD_EXIT THEN
    RETURN(c"EXIT")

  WHEN CMD_DIR THEN
    RETURN(c"DIR")

  WHEN CMD_TYPE THEN
    RETURN(c"TYPE")

  WHEN CMD_MEM THEN
    RETURN(c"MEM")

  WHEN CMD_TASKS THEN
    RETURN(c"TASKS")

  WHEN CMD_VER THEN
    RETURN(c"VER")

  WHEN CMD_MOUNT THEN
    RETURN(c"MOUNT")

  WHEN CMD_DEVICES THEN
    RETURN(c"DEVICES")

  WHEN CMD_PATH THEN
    RETURN(c"PATH")

  WHEN CMD_ALIAS THEN
    RETURN(c"ALIAS")

  WHEN CMD_UNALIAS THEN
    RETURN(c"UNALIAS")

  WHEN CMD_CLS THEN
    RETURN(c"CLS")

  WHEN CMD_RUN THEN
    RETURN(c"RUN")

  WHEN CMD_JOBS THEN
    RETURN(c"JOBS")

  WHEN CMD_BREAK THEN
    RETURN(c"BREAK")

  WHEN CMD_EXECUTE THEN
    RETURN(c"EXECUTE")

  WHEN CMD_UNMOUNT THEN
    RETURN(c"UNMOUNT")

  WHEN CMD_NEWSHELL THEN
    RETURN(c"NEWSHELL")

  WHEN CMD_SESSIONS THEN
    RETURN(c"SESSIONS")

  WHEN CMD_SESSION THEN
    RETURN(c"SESSION")

  ESAC

RETURN(c"")

; Recognize resident commands without changing the candidate text.
BYTE FUNC ShellClassify(BYTE POINTER word)
  BYTE command

  FOR command=CMD_HELP TO CMD_SESSION DO
    IF command<>CMD_EXTERNAL THEN
      IF ShellEqual(word,ShellCommandName(command))<>0 THEN
        RETURN(command)
      FI
    FI
  OD

RETURN(CMD_EXTERNAL)

; Accept the boundary between the two programs supported by a shell pipeline.
; Reject combinations whose stream ownership the shell cannot support.
BYTE FUNC ShellPipeBoundary(ShellContext POINTER context)

  IF context.shell.pipeline<>0 OR context.shell.argc=0 OR context.shell.outputRedirect<>NO_REDIRECT THEN
    RETURN(0)
  FI

  context.shell.pipeline=1
  context.shell.pipelineIndex=CARD(context.shell.argc)
  context.shell.secondArgumentOffset=context.shell.argumentLength+1
  context.shell.secondArgumentLength=0
  IF context.shell.secondArgumentOffset>LINE_LIMIT THEN
    RETURN(0)
  FI

  LET arguments=ShellTransfer(context)+SIZE(LINE_CAPACITY)
  arguments(context.shell.secondArgumentOffset)=ASCII.NUL

RETURN(1)

; Preserve the user's argument spelling, including quotes and escapes, for
; the loaded program's own argument parser. Redirection is handled separately.
BYTE FUNC ShellArgument(ShellContext POINTER context CARD start,finish)
  CARD first,used

  first=0
  used=context.shell.argumentLength
  IF context.shell.pipeline<>0 THEN
    first=context.shell.pipelineIndex
    used=context.shell.secondArgumentOffset+context.shell.secondArgumentLength
  FI

  IF CARD(context.shell.argc)=first THEN
    RETURN(1)
  FI

  LET original=ShellTransfer(context)
  LET arguments=original+SIZE(LINE_CAPACITY)
  IF CARD(context.shell.argc)>first+1 THEN
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
  IF context.shell.pipeline<>0 THEN
    context.shell.secondArgumentLength=used-context.shell.secondArgumentOffset

  ELSE
    context.shell.argumentLength=used
  FI

RETURN(1)

; Accept only command lines the shell can execute, before opening resources.
; Prepare arguments, redirection and an optional two-program pipeline.
BYTE FUNC ShellParse(ShellContext POINTER context)
  BYTE POINTER line
  CARD readAt,writeAt,start,rawStart,rawEnd,index
  BYTE value,quoted,closed,redirect

  line=ShellLine(context)
  readAt=0
  writeAt=0
  context.shell.argc=0
  context.shell.argsUsed=0
  context.shell.outputAppend=0
  context.shell.pipeline=0
  context.shell.pipelineIndex=0
  context.shell.secondArgumentOffset=0
  context.shell.secondArgumentLength=0
  context.shell.firstCommandStart=0
  context.shell.firstCommandEnd=0
  context.shell.secondCommandStart=0
  context.shell.secondCommandEnd=0

  LET original=ShellTransfer(context)
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

  context.shell.argumentLength=0
  arguments(0)=ASCII.NUL
  context.shell.inputRedirect=NO_REDIRECT
  context.shell.outputRedirect=NO_REDIRECT

  DO
    WHILE line(readAt)=ASCII.SPACE OR line(readAt)=ASCII.TAB DO
      readAt==+1
    OD

    IF line(readAt)=CHAR_PIPE THEN
      IF ShellPipeBoundary(context)=0 THEN
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
        context.shell.outputAppend=1
        readAt==+1
      FI

      IF redirect=CHAR_LESS AND context.shell.pipeline<>0 THEN
        RETURN(0)
      FI

      WHILE line(readAt)=ASCII.SPACE OR line(readAt)=ASCII.TAB DO
        readAt==+1
      OD

      IF line(readAt)=ASCII.NUL OR line(readAt)=CHAR_LESS
        OR line(readAt)=CHAR_GREATER OR line(readAt)=CHAR_PIPE THEN
        RETURN(0)
      FI

      IF (redirect=CHAR_LESS AND context.shell.inputRedirect<>NO_REDIRECT)
        OR (redirect=CHAR_GREATER AND context.shell.outputRedirect<>NO_REDIRECT) THEN
        RETURN(0)
      FI
    FI

    IF context.shell.argsUsed=WORD_CAPACITY THEN
      RETURN(0)
    FI

    context.shell.argsUsed==+1
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
      context.shell.inputRedirect=start

    ELSEIF redirect=CHAR_GREATER THEN
      context.shell.outputRedirect=start

    ELSE
      IF ShellArgument(context,rawStart,rawEnd)=0 THEN
        RETURN(0)
      FI

      IF context.shell.argc=0 THEN
        context.shell.firstCommandStart=BYTE(rawStart)
        context.shell.firstCommandEnd=BYTE(rawEnd)

      ELSEIF context.shell.pipeline<>0
          AND CARD(context.shell.argc)=context.shell.pipelineIndex THEN
        context.shell.secondCommandStart=BYTE(rawStart)
        context.shell.secondCommandEnd=BYTE(rawEnd)
      FI

      context.shell.words(context.shell.argc).text=line+SIZE(start)
      context.shell.argc==+1
    FI

    IF value=CHAR_PIPE THEN
      IF ShellPipeBoundary(context)=0 THEN
        RETURN(0)
      FI
    FI

    IF value=ASCII.NUL THEN
      EXIT
    FI
  OD

  context.shell.command=0
  IF context.shell.argc=0 THEN
    RETURN(context.shell.argsUsed=0)
  FI

  line=context.shell.words(0).text
  context.shell.command=ShellClassify(line)
  IF context.shell.pipeline<>0 THEN
    IF CARD(context.shell.argc)=context.shell.pipelineIndex
      OR context.shell.command<>CMD_EXTERNAL OR line(0)=ASCII.NUL THEN
      RETURN(0)
    FI

    line=context.shell.words(context.shell.pipelineIndex).text
    IF line(0)=ASCII.NUL OR ShellClassify(line)<>CMD_EXTERNAL THEN
      RETURN(0)
    FI

    RETURN(1)
  FI

  IF (context.shell.command=CMD_HELP OR context.shell.command=CMD_EXIT OR context.shell.command=CMD_CLS
      OR context.shell.command=CMD_JOBS OR context.shell.command=CMD_NEWSHELL
      OR context.shell.command=CMD_SESSIONS
      OR (context.shell.command>=CMD_MEM AND context.shell.command<=CMD_DEVICES
      AND context.shell.command<>CMD_MOUNT))
    AND context.shell.argc<>1 THEN
    RETURN(0)
  FI

  IF (context.shell.command=CMD_UNMOUNT OR context.shell.command=CMD_SESSION)
      AND context.shell.argc<>2 THEN
    RETURN(0)
  FI

  IF context.shell.command=CMD_BREAK AND context.shell.argc<>2 THEN
    RETURN(0)
  FI

  IF context.shell.command=CMD_EXECUTE AND (context.shell.argc<>2
      OR context.shell.words(1).text^=ASCII.NUL) THEN
    RETURN(0)
  FI

  IF (context.shell.command=CMD_CD OR context.shell.command=CMD_DIR OR context.shell.command=CMD_TYPE)
    AND context.shell.argc>2 THEN
    RETURN(0)
  FI

  IF (context.shell.command=CMD_ALIAS AND context.shell.argc>3)
      OR (context.shell.command=CMD_UNALIAS AND context.shell.argc<>2) THEN
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

BYTE FUNC ShellAliasIndex(ShellContext POINTER context BYTE POINTER name)
  BYTE index

  IF context.aliases=NULL THEN
    RETURN(ALIAS_CAPACITY)
  FI

  FOR index=0 TO ALIAS_CAPACITY-1 DO
    IF context.aliases(index).name(0)<>ASCII.NUL
        AND ShellEqual(name,CSTRING(@context.aliases(index).name(0)))<>0 THEN
      RETURN(index)
    FI
  OD

RETURN(ALIAS_CAPACITY)

PROC ShellAliasShow(ShellContext POINTER context BYTE index)
  CARD used

  LET output=DOS.Output()
  used=ShellRowText(context,output,0,CSTRING(@context.aliases(index).name(0)))
  used=ShellRowText(context,output,used,c" -> ")
  used=ShellRowText(context,output,used,CSTRING(@context.aliases(index).text(0)))
  ShellRowEnd(context,output,used)

RETURN

; Store a validated alias in the existing bounded session table.
PROC ShellAliasSet(ShellContext POINTER context BYTE POINTER name,text)
  ShellAlias POINTER entry
  BYTE index,position,value

  index=ShellAliasIndex(context,name)
  IF index=ALIAS_CAPACITY THEN
    IF context.aliasCount=ALIAS_CAPACITY THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BUFFER_OVERFLOW)
      RETURN
    FI

    IF context.aliases=NULL THEN
      context.aliases=ShellAlias POINTER(EXEC.AllocMem(
          ALIAS_CAPACITY*SIZEOF(ShellAlias),EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
      IF context.aliases=NULL THEN
        ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
        RETURN
      FI
    FI

    FOR position=0 TO ALIAS_CAPACITY-1 DO
      IF context.aliases(position).name(0)=ASCII.NUL THEN
        index=position
        EXIT
      FI
    OD

    context.aliasCount==+1
  FI

  entry=@context.aliases(index)
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
BYTE FUNC ShellAliasDefaults(ShellContext POINTER context)

  ShellAliasSet(context,BYTE POINTER(c"MKDIR"),BYTE POINTER(c"MAKEDIR"))
  IF context.aliases=NULL THEN
    RETURN(0)
  FI

  ShellAliasSet(context,BYTE POINTER(c"LS"),BYTE POINTER(c"LIST"))
  ShellAliasSet(context,BYTE POINTER(c"CP"),BYTE POINTER(c"COPY"))

RETURN(context.aliasCount=3)

; List, inspect or change the session's aliases using the same validation.
PROC ShellAliasCommand(ShellContext POINTER context)
  BYTE index

  IF context.shell.argc=1 THEN
    IF context.aliases<>NULL THEN
      FOR index=0 TO ALIAS_CAPACITY-1 DO
        IF context.aliases(index).name(0)<>ASCII.NUL THEN
          IF ShellPoll(context)<>0 THEN
            RETURN
          FI

          ShellAliasShow(context,index)
          IF context.shell.status<>PROCESS.RETURN_OK THEN
            RETURN
          FI
        FI
      OD
    FI

    RETURN
  FI

  LET name=context.shell.words(1).text
  IF ShellAliasName(name)=0 OR ShellClassify(name)<>CMD_EXTERNAL THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BAD_ARGUMENTS)
    RETURN
  FI

  IF context.shell.argc=2 THEN
    index=ShellAliasIndex(context,name)
    IF index=ALIAS_CAPACITY THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_NOT_FOUND)
    ELSE
      ShellAliasShow(context,index)
    FI

    RETURN
  FI

  LET text=context.shell.words(2).text
  IF ShellAliasText(text)=0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BAD_ARGUMENTS)
    RETURN
  FI

  ShellAliasSet(context,name,text)

RETURN

PROC ShellUnaliasCommand(ShellContext POINTER context)

  LET name=context.shell.words(1).text
  LET index=ShellAliasIndex(context,name)
  IF index=ALIAS_CAPACITY THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_NOT_FOUND)
    RETURN
  FI

  context.aliases(index).name(0)=ASCII.NUL
  context.aliases(index).text(0)=ASCII.NUL
  context.aliasCount==-1

RETURN

; Rewrite one already-parsed command word, then parse the bounded result.
; The right pipeline stage is rewritten first so its original span is valid.
BYTE FUNC ShellAliasReplace(ShellContext POINTER context BYTE stage)
  BYTE index,start,finish
  CARD sourceLength,textLength,total,offset
  BYTE POINTER source,target,line

  IF stage=0 THEN
    index=ShellAliasIndex(context,context.shell.words(0).text)
    start=context.shell.firstCommandStart
    finish=context.shell.firstCommandEnd
  ELSE
    index=ShellAliasIndex(context,context.shell.words(context.shell.pipelineIndex).text)
    start=context.shell.secondCommandStart
    finish=context.shell.secondCommandEnd
  FI

  IF index=ALIAS_CAPACITY THEN
    RETURN(1)
  FI

  source=ShellTransfer(context)
  target=ShellScratch(context)
  line=ShellLine(context)
  LET expansion=@context.aliases(index).text(0)
  sourceLength=ShellLength(source)
  textLength=ShellLength(expansion)
  total=sourceLength-CARD(finish-start)+textLength
  IF total>LINE_LIMIT THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_LINE_TOO_LONG)
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

  IF ShellParse(context)=0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BAD_ARGUMENTS)
    RETURN(0)
  FI

RETURN(1)

BYTE FUNC ShellAliasExpand(ShellContext POINTER context)

  IF context.aliasCount=0 THEN
    RETURN(1)
  FI

  IF context.shell.pipeline<>0 AND ShellAliasReplace(context,1)=0 THEN
    RETURN(0)
  FI

RETURN(ShellAliasReplace(context,0))

; Select a new working directory, retaining the old one if selection fails.
PROC ShellChange(ShellContext POINTER context BYTE POINTER path)
  DOS.FileLock POINTER previous

  LET candidate=DOS.Lock(path,DOS.SHARED_LOCK)
  LET lockError=DOS.IoErr()
  IF candidate=NULL THEN
    ShellFail(context,PROCESS.RETURN_ERROR,lockError)
    RETURN
  FI

  context.shell.retiredDirectory=candidate
  IF ShellPoll(context)<>0 THEN
    ShellReleaseLock(context)
    RETURN
  FI

  previous=DOS.CurrentDir(candidate)
  LET error=DOS.IoErr()
  IF error<>0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,error)
    ; Validate the retained default and clear IoErr before the void UnLock.
    ; Its successful return otherwise preserves the earlier selector error.
    previous=DOS.CurrentDir(context.shell.directory)
    IF DOS.IoErr()<>0 THEN
      ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN
    FI

  ELSE
    context.shell.directory=candidate
    context.shell.retiredDirectory=previous
  FI

  DOS.UnLock(context.shell.retiredDirectory)
  IF DOS.IoErr()<>0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())

  ELSE
    context.shell.retiredDirectory=NULL
  FI

RETURN

INCLUDE "shell-mount-diagnostics.inc"
INCLUDE "shell-commands.inc"
INCLUDE "shell-mounts.inc"
INCLUDE "shell-redirection.inc"
INCLUDE "shell-path.inc"
INCLUDE "shell-jobs.inc"
INCLUDE "shell-sessions.inc"
INCLUDE "shell-execute.inc"
INCLUDE "shell-completion.inc"

; Run a disk command in the foreground and keep its result for the shell.
PROC ShellExternal(ShellContext POINTER context)
  PROCESS.Result outcome

  LET image=ShellLoadCommand(context,context.shell.words(0).text)
  LET loadError=DOS.IoErr()
  IF image=NULL THEN
    ShellFail(context,PROCESS.RETURN_ERROR,loadError)
    RETURN
  FI

  IF ShellClosing(context)<>0 THEN
    PROGRAM.Unload(image)
    RETURN
  FI

  LET arguments=ShellTransfer(context)+SIZE(LINE_CAPACITY)
  LET identity=PROCESS.StartLoaded(
      BYTE POINTER(image),arguments,context.shell.argumentLength,1)
  LET error=DOS.IoErr()
  PROGRAM.Unload(image)
  IF identity=0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  IF PROCESS.Wait(identity,@outcome)=0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN
  FI

  context.shell.status=outcome.primary
  context.shell.error=outcome.secondary

RETURN

; Run two disk commands as one foreground job, with the first feeding the
; second. PIPELINE owns the stream connection and child lifetimes.
PROC ShellPipeline(ShellContext POINTER context)
  PIPELINE.Outcome outcome

  LET first=ShellLoadCommand(context,context.shell.words(0).text)
  LET firstError=DOS.IoErr()
  IF first=NULL THEN
    ShellFail(context,PROCESS.RETURN_ERROR,firstError)
    RETURN
  FI

  context.shell.diagnosticWord=BYTE(context.shell.pipelineIndex)
  LET second=ShellLoadCommand(context,context.shell.words(context.shell.pipelineIndex).text)
  LET secondError=DOS.IoErr()
  IF second=NULL THEN
    PROGRAM.Unload(first)
    ShellFail(context,PROCESS.RETURN_ERROR,secondError)
    RETURN
  FI

  IF ShellClosing(context)<>0 THEN
    PROGRAM.Unload(first)
    PROGRAM.Unload(second)
    RETURN
  FI

  LET arguments=ShellTransfer(context)+SIZE(LINE_CAPACITY)
  LET accepted=PIPELINE.Run(
      BYTE POINTER(first),BYTE POINTER(second),arguments,
      arguments+SIZE(context.shell.secondArgumentOffset),
      context.shell.argumentLength,context.shell.secondArgumentLength,@outcome)
  PROGRAM.Unload(first)
  PROGRAM.Unload(second)
  IF accepted=0 THEN
    context.shell.diagnosticWord=$ff
    ShellFail(context,outcome.primary,outcome.secondary)

  ELSE
    context.shell.status=outcome.primary
    context.shell.error=outcome.secondary
    context.shell.diagnosticWord=0
    IF outcome.second.primary=outcome.primary
        AND outcome.second.secondary=outcome.secondary
        AND (outcome.first.primary<>outcome.primary
        OR outcome.first.secondary<>outcome.secondary) THEN
      context.shell.diagnosticWord=BYTE(context.shell.pipelineIndex)
    FI
  FI

RETURN

; Carry out a validated command using the streams selected for this invocation.
PROC ShellDispatch(ShellContext POINTER context)
  CARD index,used

  CASE context.shell.command OF
  WHEN CMD_HELP THEN
    ShellLineText(context,DOS.Output(),
        c"HELP ECHO CLS CD DIR TYPE MEM TASKS VER MOUNT UNMOUNT DEVICES PATH ALIAS UNALIAS RUN JOBS BREAK EXECUTE NEWSHELL SESSIONS SESSION EXIT")
    ShellText(context,DOS.Output(),c"Edit: Ctrl-A/E home/end, B/F left/right\n")
    ShellText(context,DOS.Output(),c"Ctrl-U clear, K cut end, W cut word\n")
    ShellText(context,DOS.Output(),c"Ctrl-L clear screen\n")
    ShellText(context,DOS.Output(),c"History: Ctrl-P/N or Atari up/down\n")
    ShellText(context,DOS.Output(),c"Atari left/right move the cursor\n")
    ShellText(context,DOS.Output(),c"TAB completes commands and files\n")

  WHEN CMD_ECHO THEN
    used=0
    IF context.shell.argc>1 THEN
      FOR index=1 TO CARD(context.shell.argc)-1 DO
        IF index<>1 THEN
          used=ShellRowByte(context,DOS.Output(),used,ASCII.SPACE)
        FI

        used=ShellRowText(context,DOS.Output(),used,CSTRING(context.shell.words(index).text))
      OD
    FI

    ShellRowEnd(context,DOS.Output(),used)

  WHEN CMD_CLS THEN
    ShellByte(context,DOS.Output(),ASCII.FF)

  WHEN CMD_CD THEN
    IF context.shell.argc=2 THEN
      IF ShellEqual(context.shell.words(1).text,c"..")<>0 THEN
        ShellChange(context,BYTE POINTER(c"/"))
      ELSE
        ShellChange(context,context.shell.words(1).text)
      FI

    ELSEIF DOS.NameFromLock(context.shell.directory,ShellScratch(context),LINE_CAPACITY)=0 THEN
      ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())

    ELSE
      ShellLineText(context,DOS.Output(),CSTRING(ShellScratch(context)))
    FI

  WHEN CMD_EXIT THEN
    context.shell.done=1

  WHEN CMD_DIR THEN
    ShellDir(context)

  WHEN CMD_TYPE THEN
    ShellType(context)

  WHEN CMD_MEM THEN
    ShellMem(context)

  WHEN CMD_TASKS THEN
    ShellTasks(context,DOS.Output())

  WHEN CMD_VER THEN
    ShellText(context,DOS.Output(),CSTRING(EXECBUILD.version))

  WHEN CMD_MOUNT THEN
    ShellMountCommand(context)

  WHEN CMD_UNMOUNT THEN
    ShellUnmountCommand(context)

  WHEN CMD_DEVICES THEN
    ShellDevices(context,DOS.Output())

  WHEN CMD_PATH THEN
    ShellPath(context)

  WHEN CMD_ALIAS THEN
    ShellAliasCommand(context)

  WHEN CMD_UNALIAS THEN
    ShellUnaliasCommand(context)

  WHEN CMD_JOBS THEN
    ShellJobs(context)

  WHEN CMD_BREAK THEN
    ShellBreakJob(context)

  WHEN CMD_EXECUTE THEN
    ShellScriptOpen(context,context.shell.words(1).text,0)

  WHEN CMD_NEWSHELL THEN
    ShellSessionCommand(context,SESSION_CREATE)

  WHEN CMD_SESSIONS THEN
    ShellSessionCommand(context,SESSION_QUERY)

  WHEN CMD_SESSION THEN
    ShellSessionCommand(context,SESSION_SELECT)

  WHEN CMD_EXTERNAL THEN
    IF context.shell.background<>0 THEN
      ShellRun(context)

    ELSEIF context.shell.pipeline<>0 THEN
      ShellPipeline(context)

    ELSE
      ShellExternal(context)
    FI
  ESAC

RETURN

; Own one command's complete interaction: its foreground scope, temporary
; streams and final result must be settled before the next prompt.
PROC ShellOneCommand(ShellContext POINTER context)

  IF context.shell.done<>0 THEN
    RETURN
  FI

  context.shell.status=PROCESS.RETURN_OK
  context.shell.error=0
  context.shell.diagnosticWord=$ff
  ShellCollectJob(context)
  IF context.shell.done<>0 THEN
    RETURN
  FI

  IF ShellPoll(context)=0 THEN
    IF ShellScope(context)<>0 THEN
      IF ShellPrepareCommand(context)=0 THEN
        ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BAD_NUMBER)

      ELSEIF context.shell.command>=CMD_NEWSHELL AND context.shell.command<=CMD_SESSION
          AND (context.script<>NULL OR context.control=NULL) THEN
        context.shell.diagnosticWord=0
        ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_ACTION_NOT_KNOWN)

      ELSEIF context.shell.command=CMD_EXECUTE AND context.script<>NULL THEN
        ; Reject nesting before its redirections can create or truncate files.
        context.shell.diagnosticWord=0
        ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_ACTION_NOT_KNOWN)

      ELSE
        IF ShellRedirect(context)<>0 THEN
          IF ShellPoll(context)=0 THEN
            context.shell.diagnosticWord=0
            ShellDispatch(context)
          FI
        FI
      FI
    FI
  FI

  IF DOS.BreakPending()<>0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_BREAK)
  FI

  ShellUnredirect(context)
  ShellRetireBreak(context,0)
  IF context.shell.done=0 THEN
    IF ShellScope(context)<>0 THEN
      ShellDiagnostic(context)
      ShellJobAnnounce(context)
    FI
  FI

  context.shell.lastStatus=context.shell.status
  context.shell.lastError=context.shell.error

RETURN

; Finish an opened script through ordinary dispatch. Startup uses the same
; loop without creating a prompt or recording synthetic input in history.
PROC ShellRunScript(ShellContext POINTER context)

  IF context.script<>NULL THEN
    WHILE context.shell.done=0 AND context.shell.status<PROCESS.RETURN_ERROR DO
      BEGIN
        LET primary=context.shell.status
        LET secondary=context.shell.error
        context.shell.status=PROCESS.RETURN_OK
        context.shell.error=0
        context.shell.diagnosticWord=DIAGNOSTIC_SCRIPT
        context.shell.command=CMD_EXECUTE
        context.shell.argc=0
        IF ShellScriptNext(context)=0 THEN
          IF context.shell.status=PROCESS.RETURN_OK THEN
            context.shell.status=primary
            context.shell.error=secondary
          ELSE
            ShellDiagnostic(context)
          FI

          EXIT
        FI

        ShellOneCommand(context)
      END
    OD

    BEGIN
      LET primary=context.shell.status
      LET secondary=context.shell.error
      ShellScriptClose(context)
      IF context.shell.status<>primary OR context.shell.error<>secondary THEN
        context.shell.command=CMD_EXECUTE
        context.shell.argc=0
        context.shell.diagnosticWord=DIAGNOSTIC_SCRIPT
        ShellDiagnostic(context)
      FI
    END
  FI

  ShellRetireBreak(context,0)
  IF context.shell.done=0 THEN
    ShellScope(context)
  FI

  context.shell.lastStatus=context.shell.status
  context.shell.lastError=context.shell.error

RETURN

; Reuse ordinary execution without recursive dispatch or changing command Input.
PROC ShellCommand(ShellContext POINTER context)

  ShellOneCommand(context)
  IF context.script<>NULL THEN
    ShellRunScript(context)
  FI

RETURN

; Advance the interactive session as console input becomes available.
; Complete lines run as commands; cancellation returns to a fresh prompt.
PROC ShellReadStep(ShellContext POINTER context)

  IF context.shell.done<>0 OR ShellClosing(context)<>0 THEN
    RETURN
  FI

  LET state=ShellEdit(context)
  LET edit=@state.edit
  LET result=DOS.ConsoleEdit(context.shell.console,edit)
  LET error=DOS.IoErr()
  IF result=DOS.CONEDIT_COMPLETE THEN
    edit.action=DOS.CONEDIT_RESUME
    IF ShellClosing(context)=0 THEN
      ShellComplete(context)
    FI
    RETURN
  FI

  edit.action=DOS.CONEDIT_START
  IF ShellClosing(context)<>0 THEN
    RETURN
  FI

  IF result=DOS.CONEDIT_LINE THEN
    context.shell.length=edit.length
    IF edit.newline<>0 THEN
      ShellHistory(context,0)
      ShellCommand(context)
      ShellClear(context)
      IF context.shell.done=0 THEN
        ShellPrompt(context)
      FI

    ELSE
      ShellHistory(context,0)
      IF context.shell.length<>0 THEN
        ShellCommand(context)
      FI

      context.shell.done=1
    FI

  ELSEIF result=DOS.CONEDIT_EOF THEN
    ShellHistory(context,0)
    context.shell.done=1

  ELSEIF error=DOS.ERROR_BREAK OR error=DOS.ERROR_LINE_TOO_LONG
        OR error=DOS.ERROR_BUFFER_OVERFLOW THEN
    ShellHistory(context,0)
    IF context.shell.done<>0 THEN
      RETURN
    FI

    ShellClear(context)
    context.shell.diagnosticWord=$ff
    context.shell.status=PROCESS.RETURN_OK
    context.shell.error=0
    IF ShellScope(context)=0 THEN
      RETURN
    FI

    IF error<>DOS.ERROR_BREAK THEN
      context.shell.status=PROCESS.RETURN_ERROR
      context.shell.error=error
      IF error=DOS.ERROR_BUFFER_OVERFLOW THEN
        ShellText(context,context.shell.console,c"Input lost; line discarded")
        ShellByte(context,context.shell.console,ASCII.LF)

      ELSE
        ShellDiagnostic(context)
      FI
    FI

    context.shell.lastStatus=context.shell.status
    context.shell.lastError=context.shell.error
    ShellPrompt(context)

  ELSE
    ShellHistory(context,0)
    ShellFail(context,PROCESS.RETURN_FAIL,error)
  FI

RETURN

; Establish a shell session while preserving the caller's default streams.
; ShellFinish also handles a session whose setup succeeds only partly.
BYTE FUNC ShellOpen(ShellContext POINTER context BYTE POINTER consoleName)

  context.shell=ShellState POINTER(
      EXEC.AllocMem(SHELL_BYTES,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
  IF context.shell=NULL THEN
    RETURN(0)
  FI

  context.aliases=NULL
  context.script=NULL
  context.aliasCount=0
  context.job.identity=0
  context.job.state=0
  context.job.announce=0
  context.shell.historyAvailable=1
  LET edit=ShellEdit(context)
  edit.edit.buffer=ShellLine(context)
  edit.edit.capacity=LINE_CAPACITY
  ShellPathReset(context)
  context.shell.diagnosticWord=$ff
  context.shell.console=DOS.Open(consoleName,DOS.MODE_READWRITE)
  IF context.shell.console=NULL THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  context.shell.initialInput=DOS.SelectInput(context.shell.console)
  IF DOS.IoErr()<>0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  context.shell.initialized=1
  context.shell.initialOutput=DOS.SelectOutput(context.shell.console)
  IF DOS.IoErr()<>0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  context.shell.initialized=2

  IF ShellScope(context)=0 THEN
    RETURN(0)
  FI

RETURN(ShellAliasDefaults(context))

; Make the shell ready for input, reporting any recoverable startup failure.
PROC ShellInitialPrompt(ShellContext POINTER context)

  context.shell.lastStatus=context.shell.status
  context.shell.lastError=context.shell.error
  ShellDiagnostic(context)
  ShellPrompt(context)

RETURN

; Start a session on an already running system, optionally in a given directory.
BYTE FUNC ShellStart(ShellContext POINTER context BYTE POINTER initial)

  IF ShellOpen(context,shellCon)=0 THEN
    RETURN(0)
  FI

  IF initial<>NULL THEN
    ShellChange(context,initial)
  FI

  ShellInitialPrompt(context)

RETURN(context.shell.done=0)

; End the session and return its status without releasing resources still
; in use. The same cleanup applies after partial startup or a command failure.
LONGINT FUNC ShellFinish(ShellContext POINTER context)
  DOS.FileHandle POINTER ignored

  IF context.shell=NULL THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  LET edit=ShellEdit(context)
  IF edit.edit.action=DOS.CONEDIT_RESUME THEN
    edit.edit.action=DOS.CONEDIT_CANCEL
    IF DOS.ConsoleEdit(context.shell.console,@edit.edit)<0 THEN
      ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN(PROCESS.RETURN_FAIL)
    FI

    edit.edit.action=DOS.CONEDIT_START
  FI

  IF ShellStopJob(context)=0 THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  ShellScriptClose(context)
  IF context.script<>NULL THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  ShellUnredirect(context)
  IF context.shell.redirectActive<>0 THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  ; Selected resources are borrowed. Detach them before releasing ownership.
  IF context.shell.initialized>=1 THEN
    ignored=DOS.SelectInput(context.shell.initialInput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN(PROCESS.RETURN_FAIL)
    FI
  FI

  IF context.shell.initialized>=2 THEN
    ignored=DOS.SelectOutput(context.shell.initialOutput)
    IF DOS.IoErr()<>0 THEN
      ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN(PROCESS.RETURN_FAIL)
    FI
  FI

  LET previous=DOS.CurrentDir(NULL)
  IF DOS.IoErr()<>0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  DOS.UnLock(previous)
  IF DOS.IoErr()<>0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  context.shell.directory=NULL
  DOS.UnLock(context.shell.retiredDirectory)
  IF DOS.IoErr()<>0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  context.shell.retiredDirectory=NULL
  ShellCloseCommandInput(context)
  IF context.shell.commandInput<>NULL THEN
    RETURN(PROCESS.RETURN_FAIL)
  FI

  IF DOS.EndForeground()=0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  IF context.shell.console<>NULL THEN
    IF DOS.Close(context.shell.console)=0 THEN
      ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
      RETURN(PROCESS.RETURN_FAIL)
    FI

    context.shell.console=NULL
  FI

  IF DOS.ReleaseContext()=0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(PROCESS.RETURN_FAIL)
  FI

  LET result=context.shell.status
  IF context.aliases<>NULL THEN
    EXEC.FreeMem(BYTE POINTER(context.aliases),ALIAS_CAPACITY*SIZEOF(ShellAlias))
    context.aliases=NULL
    context.aliasCount=0
  FI

  EXEC.FreeMem(BYTE POINTER(context.shell),SHELL_BYTES)
  context.shell=NULL

RETURN(result)
