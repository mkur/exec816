; One owned Process; collection changes job state before later reporting.
PROC ShellJobReport(ShellContext POINTER context DOS.FileHandle POINTER handle)
  CARD used

  used=ShellRowText(context,handle,0,c"Job ")
  used=ShellRowUnsigned(context,handle,used,context.job.identity)
  CASE context.job.state OF
  WHEN JOB_RUNNING THEN
    used=ShellRowText(context,handle,used,c" running")

  WHEN JOB_STOPPING THEN
    used=ShellRowText(context,handle,used,c" stopping")

  WHEN JOB_DONE THEN
    used=ShellRowText(context,handle,used,c" finished (")
    used=ShellRowNumber(context,handle,used,context.job.outcome.primary)
    used=ShellRowText(context,handle,used,c", ")
    used=ShellRowNumber(context,handle,used,context.job.outcome.secondary)
    used=ShellRowText(context,handle,used,c")")
  ESAC

  ShellRowEnd(context,handle,used)

RETURN

; A not-yet-retired child is normal. Never replace a foreground command result.
PROC ShellCollectJob(ShellContext POINTER context)

  IF context.job.state<>JOB_RUNNING AND context.job.state<>JOB_STOPPING THEN
    RETURN
  FI

  LET saved=DOS.IoErr()
  IF PROCESS.Collect(context.job.identity,@context.job.outcome)<>0 THEN
    context.job.state=JOB_DONE
    context.job.announce=1
  ELSEIF DOS.IoErr()<>DOS.ERROR_OBJECT_IN_USE THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
  FI

  DOS.SetIoErr(saved)

RETURN

PROC ShellJobAnnounce(ShellContext POINTER context)

  IF context.job.announce<>0 THEN
    context.job.announce=0
    ShellJobReport(context,context.shell.console)
  FI

RETURN

; Strip RUN, then reuse the existing parser, alias expansion and argument tail.
BYTE FUNC ShellPrepareCommand(ShellContext POINTER context)

  context.shell.background=0
  IF ShellParse(context)=0 OR ShellAliasExpand(context)=0 THEN
    RETURN(0)
  FI

  IF context.shell.command<>CMD_RUN THEN
    RETURN(1)
  FI

  IF context.shell.argc<2 THEN
    RETURN(0)
  FI

  IF context.job.state=JOB_RUNNING OR context.job.state=JOB_STOPPING THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_IN_USE)
    RETURN(0)
  FI

  ShellJobAnnounce(context)
  LET tail=ShellTransfer(context)+SIZE(context.shell.firstCommandEnd)
  A816MEMORY.Move(ShellLine(context),tail,STR.strlen(CSTRING(tail))+1)
  IF ShellParse(context)=0 OR ShellAliasExpand(context)=0 THEN
    RETURN(0)
  FI

  IF context.shell.pipeline<>0 OR context.shell.command<>CMD_EXTERNAL THEN
    RETURN(0)
  FI

  context.shell.background=1

RETURN(1)

PROC ShellRun(ShellContext POINTER context)

  LET image=ShellLoadCommand(context,context.shell.words(0).text)
  IF image=NULL THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
    RETURN
  FI

  LET identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),
      ShellTransfer(context)+SIZE(LINE_CAPACITY),context.shell.argumentLength)
  LET cause=DOS.IoErr()
  PROGRAM.Unload(image)
  IF identity=0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,cause)
    RETURN
  FI

  context.job.identity=identity
  context.job.state=JOB_RUNNING
  context.job.announce=0

RETURN

PROC ShellJobs(ShellContext POINTER context)

  IF context.job.state=0 THEN
    ShellText(context,DOS.Output(),c"No background jobs\n")
  ELSE
    ShellJobReport(context,DOS.Output())
    context.job.announce=0
  FI

RETURN

PROC ShellBreakJob(ShellContext POINTER context)
  ADDRESS ARRAY values(1)

  LET cause=DOSARGS.Parse(CSTRING(ShellTransfer(context)+SIZE(LINE_CAPACITY)),
      c"JOB/A/N",values,1,ShellScratch(context),SCRATCH_CAPACITY)
  IF cause<>0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,cause)
    RETURN
  FI

  LET number=LONGCARD POINTER(values(0))
  IF number^<>context.job.identity OR (context.job.state<>JOB_RUNNING
      AND context.job.state<>JOB_STOPPING) THEN
    ShellFail(context,PROCESS.RETURN_ERROR,PROCESS.ERROR_INVALID_PROCESS)
    RETURN
  FI

  IF PROCESS.RequestStop(context.job.identity)=0 THEN
    ShellFail(context,PROCESS.RETURN_ERROR,DOS.IoErr())
  ELSE
    context.job.state=JOB_STOPPING
  FI

RETURN

; EXIT remains cooperative: wait for cleanup and kernel retirement before free.
BYTE FUNC ShellStopJob(ShellContext POINTER context)

  IF context.job.state<>JOB_RUNNING AND context.job.state<>JOB_STOPPING THEN
    RETURN(1)
  FI

  IF PROCESS.RequestStop(context.job.identity)=0
      OR PROCESS.Wait(context.job.identity,@context.job.outcome)=0 THEN
    ShellFail(context,PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  context.job.state=JOB_DONE
  context.job.announce=0

RETURN(1)
