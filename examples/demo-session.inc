; The optional demonstration launches the same disk command users can run.
INCLUDE "shell/shell-session.inc"
INCLUDE "shell/shell-boot.inc"

BYTE FUNC DemoStart()

  IF ShellBootStart(shellCon)=0 THEN
    RETURN(0)
  FI

  ShellText(shell.console,c"RUN PRIMES\n")
  STR.strlcpy(ShellLine(),c"RUN PRIMES",LINE_CAPACITY)
  ShellCommand()
  ShellClear()
  IF shell.done=0 THEN
    ShellPrompt()
  FI

RETURN(shell.done=0)

LONGINT FUNC DemoFinish()

RETURN(ShellFinish())
