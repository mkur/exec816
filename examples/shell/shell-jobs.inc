; One owned Process; collection changes job state before later reporting.
PROC ShellJobNumber(DOS.FileHandle POINTER handle LONGCARD number)

  LET buffer=ShellDrawBuffer()
  LET length=STR.u32toa(number,buffer,DRAW_CAPACITY)
  ShellWrite(handle,buffer,CARD(length))

RETURN

PROC ShellJobReport(DOS.FileHandle POINTER handle)

  ShellText(handle,c"Job ")
  ShellJobNumber(handle,job.identity)
  CASE job.state OF
  WHEN JOB_RUNNING THEN
    ShellText(handle,c" running\n")
  WHEN JOB_STOPPING THEN
    ShellText(handle,c" stopping\n")
  WHEN JOB_DONE THEN
    ShellText(handle,c" finished (")
    ShellNumber(handle,job.outcome.primary)
    ShellText(handle,c", ")
    ShellNumber(handle,job.outcome.secondary)
    ShellText(handle,c")\n")
  ESAC

RETURN

; A not-yet-retired child is normal. Never replace a foreground command result.
PROC ShellCollectJob()

  IF job.state<>JOB_RUNNING AND job.state<>JOB_STOPPING THEN
    RETURN
  FI

  LET saved=DOS.IoErr()
  IF PROCESS.Collect(job.identity,@job.outcome)<>0 THEN
    job.state=JOB_DONE
    job.announce=1
  ELSEIF DOS.IoErr()<>DOS.ERROR_OBJECT_IN_USE THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
  FI

  DOS.SetIoErr(saved)

RETURN

PROC ShellJobAnnounce()

  IF job.announce<>0 THEN
    job.announce=0
    ShellJobReport(shell.console)
  FI

RETURN

; Strip RUN, then reuse the existing parser, alias expansion and argument tail.
BYTE FUNC ShellPrepareCommand()

  shell.background=0
  IF ShellParse()=0 OR ShellAliasExpand()=0 THEN
    RETURN(0)
  FI

  IF shell.command<>CMD_RUN THEN
    RETURN(1)
  FI

  IF shell.argc<2 THEN
    RETURN(0)
  FI

  IF job.state=JOB_RUNNING OR job.state=JOB_STOPPING THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_IN_USE)
    RETURN(0)
  FI

  ShellJobAnnounce()
  LET tail=ShellTransfer()+SIZE(shell.firstCommandEnd)
  A816MEMORY.Move(ShellLine(),tail,STR.strlen(CSTRING(tail))+1)
  IF ShellParse()=0 OR ShellAliasExpand()=0 THEN
    RETURN(0)
  FI

  IF shell.pipeline<>0 OR shell.command<>CMD_EXTERNAL THEN
    RETURN(0)
  FI

  shell.background=1

RETURN(1)

PROC ShellRun()

  LET image=ShellLoadCommand(shell.words(0).text)
  IF image=NULL THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
    RETURN
  FI

  LET identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),
      ShellTransfer()+SIZE(LINE_CAPACITY),shell.argumentLength)
  LET cause=DOS.IoErr()
  PROGRAM.Unload(image)
  IF identity=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,cause)
    RETURN
  FI

  job.identity=identity
  job.state=JOB_RUNNING
  job.announce=0

RETURN

PROC ShellJobs()

  IF job.state=0 THEN
    ShellText(DOS.Output(),c"No background jobs\n")
  ELSE
    ShellJobReport(DOS.Output())
    job.announce=0
  FI

RETURN

PROC ShellBreakJob()
  ADDRESS ARRAY values(1)

  LET cause=DOSARGS.Parse(CSTRING(ShellTransfer()+SIZE(LINE_CAPACITY)),
      c"JOB/A/N",values,1,ShellScratch(),SCRATCH_CAPACITY)
  IF cause<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,cause)
    RETURN
  FI

  LET number=LONGCARD POINTER(values(0))
  IF number^<>job.identity OR (job.state<>JOB_RUNNING
      AND job.state<>JOB_STOPPING) THEN
    ShellFail(PROCESS.RETURN_ERROR,PROCESS.ERROR_INVALID_PROCESS)
    RETURN
  FI

  IF PROCESS.RequestStop(job.identity)=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,DOS.IoErr())
  ELSE
    job.state=JOB_STOPPING
  FI

RETURN

; EXIT remains cooperative: wait for cleanup and kernel retirement before free.
BYTE FUNC ShellStopJob()

  IF job.state<>JOB_RUNNING AND job.state<>JOB_STOPPING THEN
    RETURN(1)
  FI

  IF PROCESS.RequestStop(job.identity)=0
      OR PROCESS.Wait(job.identity,@job.outcome)=0 THEN
    ShellFail(PROCESS.RETURN_FAIL,DOS.IoErr())
    RETURN(0)
  FI

  job.state=JOB_DONE
  job.announce=0

RETURN(1)
