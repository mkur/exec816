; The optional demonstration launches the same disk command users can run.
INCLUDE "shell/shell-session.inc"
INCLUDE "shell/shell-boot.inc"

ShellContext context

BYTE FUNC DemoStart()

  IF ShellBootStart(@context,shellCon)=0 THEN
    RETURN(0)
  FI

  ShellText(@context,context.shell.console,c"RUN PRIMES >CON:\n")
  STR.strlcpy(ShellLine(@context),c"RUN PRIMES >CON:",LINE_CAPACITY)
  ShellCommand(@context)
  ShellClear(@context)
  IF context.shell.done=0 THEN
    ShellPrompt(@context)
  FI

RETURN(context.shell.done=0)

LONGINT FUNC DemoFinish()

RETURN(ShellFinish(@context))
