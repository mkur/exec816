; Root owns registry/presentation; each child owns one explicit shell context.

TYPE ShellSession=[
  ShellStartup startup
  ShellSessionControl control
  CONSOLETYPES.KeyWatch watch
  PROCESS.Result result
  LONGCARD process
  ShellSessionMessage POINTER createRequest,readyRequest
  BYTE state,ready
]

ShellSession ARRAY sessions(SESSION_CAPACITY)
ShellContext ARRAY contexts(SESSION_CAPACITY)
ShellContext systemContext
EXEC.MsgPort POINTER shellRequests
ShellSessionMessage POINTER selectionRequest
LONGCARD nextSession,selectedSession,shortcutMask,shortcutTarget
LONGINT controllerStatus,bootPrimary,bootSecondary
BYTE shortcutBit,controllerLive,controllerRetry,firstFlags

; Formatting shared scalar identities never borrows another Task's DOS object.
PROC ShellHexIdentity(LONGCARD identity BYTE POINTER text)
  BYTE index,value

  FOR index=0 TO 7 DO
    value=BYTE((identity RSH ((7-index) LSH 2)) & 15)
    text(index)=IF value<10 THEN value+48 ELSE value+87 FI
  OD

  text(8)=0

RETURN

; Registry identity checks admit requests; callers retain the record thereafter.
ShellSession POINTER FUNC ShellSessionFind(LONGCARD identity)
  BYTE index

  FOR index=0 TO SESSION_CAPACITY-1 DO
    IF sessions(index).state<>SESSION_STATE_FREE
        AND sessions(index).control.identity=identity THEN
      RETURN(@sessions(index))
    FI
  OD

RETURN(NULL)

; One exact message is returned after the requested ownership transition.
PROC ShellSessionReply(ShellSessionMessage POINTER request
    LONGINT primary,secondary)

  request.primary=primary
  request.secondary=secondary
  EXEC.ReplyMsg(@request.message)

RETURN

; The admitted Process argument is only its immutable eight-digit identity.
ShellSession POINTER FUNC ShellOwnSession()
  BYTE index,value
  LONGCARD identity

  LET arguments=PROCESS.GetArgStr()
  IF arguments=NULL OR STR.strlen(arguments)<>8 THEN
    RETURN(NULL)
  FI

  identity=0
  FOR index=0 TO 7 DO
    value=arguments(index)
    IF value>='0 AND value<='9 THEN
      value==-'0
    ELSEIF value>='a AND value<='f THEN
      value=value-'a+10
    ELSE
      RETURN(NULL)
    FI

    identity=(identity LSH 4) OR LONGCARD(value)
  OD

RETURN(ShellSessionFind(identity))

; Setup and command execution remain entirely in the shell Process's context.
LONGINT FUNC ShellProcessEntry()
  BYTE ARRAY consoleName(13)
  BYTE index,opened
  LONGINT primary,secondary

  LET session=ShellOwnSession()
  IF session=NULL THEN
    DOS.SetIoErr(PROCESS.ERROR_INVALID_PROCESS)
    RETURN(PROCESS.RETURN_FAIL)
  FI

  index=0
  WHILE @sessions(index)<>session DO
    index==+1
  OD

  LET context=@contexts(index)
  context.control=@session.control
  LET self=EXEC.FindTask(NULL)
  EXEC.Forbid()
  self.tc_Node.ln_Name=bootShellName
  EXEC.Permit()
  STR.strlcpy(consoleName,c"CON:",13)
  ShellHexIdentity(session.startup.unit,BYTE POINTER(ADDRESS(consoleName)+SIZE(4)))
  opened=ShellOpen(context,consoleName)
  primary=PROCESS.RETURN_OK
  secondary=0
  IF opened=0 THEN
    primary=PROCESS.RETURN_FAIL
    secondary=IF context.shell=NULL THEN LONGINT(DOS.ERROR_NO_FREE_STORE)
        ELSE context.shell.error FI
  ELSE
    IF session.startup.directory(0)<>0 THEN
      ShellChange(context,session.startup.directory)
    FI

    IF (session.startup.flags & SESSION_FIRST_BOOT)<>0 THEN
      IF bootPrimary<>PROCESS.RETURN_OK THEN
        context.shell.status=bootPrimary
        context.shell.error=bootSecondary
      FI

      IF context.shell.status=PROCESS.RETURN_OK
          AND (session.startup.flags & SESSION_SCRIPTS)<>0 THEN
        ShellBootScripts(context)
      FI

      IF context.shell.done=0 AND (session.startup.flags & SESSION_PRIME)<>0 THEN
        ShellText(context,context.shell.console,c"RUN PRIMES >CON:\n")
        STR.strlcpy(ShellLine(context),c"RUN PRIMES >CON:",LINE_CAPACITY)
        ShellCommand(context)
        ShellClear(context)
      FI
    ELSE
      IF context.shell.status<>PROCESS.RETURN_OK THEN
        primary=context.shell.status
        secondary=context.shell.error
      ELSE
        ; A reused unit zero starts with a fresh transcript and input endpoint.
        ShellByte(context,context.shell.console,ASCII.FF)
        IF context.shell.status<>PROCESS.RETURN_OK THEN
          primary=context.shell.status
          secondary=context.shell.error
        FI
      FI
    FI
  FI

  LET ready=ShellSessionMessage POINTER(EXEC.AllocMem(
      SHELLSESSIONMESSAGE_SIZE,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
  IF ready=NULL THEN
    primary=PROCESS.RETURN_FAIL
    secondary=DOS.ERROR_NO_FREE_STORE
  ELSE
    ; Start publishes the returned Process identity before root services READY.
    WHILE session.process=0 DO
      EXEC.Yield()
    OD

    ready.value=session.process
    ready.operation=SESSION_READY
    ready.session=session.control.identity
    ready.primary=primary
    ready.secondary=secondary
    IF opened<>0 THEN
      IF context.shell.done<>0 OR ShellClosing(context)<>0 THEN
        ready.flags=SESSION_READY_EXIT
      FI
    FI

    BEGIN
      LET replied=ShellSessionExchange(@session.control,ready)
      primary=ready.primary
      secondary=ready.secondary
    END

    EXEC.FreeMem(BYTE POINTER(ready),SHELLSESSIONMESSAGE_SIZE)
  FI

  IF opened<>0 AND primary=PROCESS.RETURN_OK THEN
    context.shell.lastStatus=context.shell.status
    context.shell.lastError=context.shell.error
    ShellClear(context)
    IF context.shell.done=0 AND ShellClosing(context)=0 THEN
      ShellPrompt(context)
    FI

    WHILE context.shell.done=0 DO
      ShellReadStep(context)
    OD
  FI

  IF context.shell<>NULL THEN
    BEGIN
      LET outcome=ShellFinish(context)
      IF primary=PROCESS.RETURN_OK THEN
        primary=outcome
        secondary=DOS.IoErr()
      FI
    END
  FI

  DOS.SetIoErr(secondary)

RETURN(primary)

; Publish immutable startup data before Start can schedule its admitted entry.
BYTE FUNC ShellSessionSpawn(ShellSession POINTER session LONGCARD unit
    BYTE POINTER directory BYTE flags ShellSessionMessage POINTER request)
  BYTE ARRAY arguments(9)

  IF nextSession=$ffffffff THEN
    DOS.SetIoErr(DOS.ERROR_NO_FREE_STORE)
    RETURN(0)
  FI

  nextSession==+1
  session.control.identity=nextSession
  session.control.port=shellRequests
  session.control.closeRequested=0
  session.startup.identity=nextSession
  session.startup.unit=unit
  session.startup.flags=flags
  STR.strlcpy(session.startup.directory,CSTRING(directory),SESSION_PATH_BYTES)
  session.createRequest=request
  session.readyRequest=NULL
  session.ready=0
  session.result.primary=PROCESS.RETURN_OK
  session.result.secondary=0
  session.state=SESSION_STATE_CREATING
  controllerLive==+1
  ShellHexIdentity(nextSession,arguments)
  session.process=PROCESS.Start(@ShellProcessEntry,arguments,8)
  IF session.process=0 THEN
    session.result.primary=PROCESS.RETURN_FAIL
    session.result.secondary=DOS.IoErr()
    session.state=SESSION_STATE_RETIRING
    RETURN(0)
  FI

RETURN(1)

; Durable close precedes cancellation, including the interval before a scope.
PROC ShellSessionClose(ShellSession POINTER session)
  CARD cancelled

  EXEC.Forbid()
  session.control.closeRequested=1
  IF session.state<>SESSION_STATE_RETIRING THEN
    session.state=SESSION_STATE_CLOSING
  FI

  cancelled=CONSOLE.RequestBreak(session.startup.unit)
  EXEC.Permit()

RETURN

; A query copies controller-owned scalars, never another shell's mutable state.
PROC ShellSessionQueryReply(ShellSessionMessage POINTER request)
  BYTE index,count

  IF request.capacity<SHELLSESSIONQUERY_SIZE THEN
    ShellSessionReply(request,PROCESS.RETURN_ERROR,DOS.ERROR_BUFFER_OVERFLOW)
    RETURN
  FI

  LET query=ShellSessionQuery POINTER(request.payload)
  A816MEMORY.Clear(BYTE POINTER(query),SHELLSESSIONQUERY_SIZE)
  count=0
  FOR index=0 TO SESSION_CAPACITY-1 DO
    IF sessions(index).state<>SESSION_STATE_FREE THEN
      BEGIN
        LET source=@sessions(index)
        LET target=@query.entries(count)
        target.identity=source.control.identity
        target.unit=source.startup.unit
        target.process=source.process
        target.state=source.state
        target.selected=source.control.identity=selectedSession
        target.primary=source.result.primary
        target.secondary=source.result.secondary
        count==+1
      END
    FI
  OD

  request.value=LONGCARD(count)
  ShellSessionReply(request,PROCESS.RETURN_OK,0)

RETURN

; Admit a fresh view and copy startup data before scheduling the child.
PROC ShellSessionCreate(ShellSessionMessage POINTER request)
  BYTE index,unitZero,started
  LONGCARD unit
  ShellSession POINTER available

  IF controllerLive>=SESSION_CAPACITY OR nextSession=$ffffffff THEN
    ShellSessionReply(request,PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
    RETURN
  FI

  IF request.capacity<SESSION_PATH_BYTES THEN
    ShellSessionReply(request,PROCESS.RETURN_ERROR,DOS.ERROR_BUFFER_OVERFLOW)
    RETURN
  FI

  available=NULL
  unitZero=1
  FOR index=0 TO SESSION_CAPACITY-1 DO
    IF sessions(index).state=SESSION_STATE_FREE THEN
      available=@sessions(index)
    ELSEIF sessions(index).startup.unit=0 THEN
      unitZero=0
    FI
  OD

  unit=0
  IF unitZero=0 THEN
    unit=CONSOLE.Create(CONSOLE.ScreenWidth(),CONSOLE.ScreenHeight())
    IF unit=0 THEN
      ShellSessionReply(request,PROCESS.RETURN_ERROR,DOS.ERROR_NO_FREE_STORE)
      RETURN
    FI
  FI

  ; Failed Start retains ownership until normal controller retirement.
  started=ShellSessionSpawn(available,unit,request.payload,0,request)

RETURN

; Choose the next ready identity in creation order, wrapping at the end.
ShellSession POINTER FUNC ShellSessionNext(LONGCARD identity)
  BYTE index
  ShellSession POINTER first,next

  first=NULL
  next=NULL
  FOR index=0 TO SESSION_CAPACITY-1 DO
    BEGIN
      LET candidate=@sessions(index)
      IF candidate.state=SESSION_STATE_READY THEN
        IF first=NULL OR candidate.control.identity<first.control.identity THEN
          first=candidate
        FI

        IF candidate.control.identity>identity THEN
          IF next=NULL OR candidate.control.identity<next.control.identity THEN
            next=candidate
          FI
        FI
      FI
    END
  OD

  IF next<>NULL THEN
    RETURN(next)
  FI

RETURN(first)

; Requests are bounded by their producers and remain owned until exact reply.
PROC ShellControllerRequests()
  ShellSessionMessage POINTER request
  ShellSession POINTER session

  DO
    request=ShellSessionMessage POINTER(EXEC.GetMsg(shellRequests))
    IF request=NULL THEN
      EXIT
    FI

    session=ShellSessionFind(request.session)
    CASE request.operation OF
    WHEN SESSION_QUERY THEN
      ShellSessionQueryReply(request)

    WHEN SESSION_READY THEN
      IF session=NULL OR session.process<>request.value
          OR session.readyRequest<>NULL OR session.ready<>0 THEN
        ShellSessionReply(request,PROCESS.RETURN_ERROR,
            DOS.ERROR_OBJECT_NOT_FOUND)
      ELSEIF request.primary<>PROCESS.RETURN_OK
          OR request.flags=SESSION_READY_EXIT
          OR session.control.closeRequested<>0 THEN
        IF session.control.closeRequested<>0 THEN
          request.primary=PROCESS.RETURN_ERROR
          request.secondary=DOS.ERROR_BREAK
        FI

        session.result.primary=request.primary
        session.result.secondary=request.secondary
        session.state=SESSION_STATE_CLOSING
        ShellSessionReply(request,request.primary,request.secondary)
      ELSE
        session.readyRequest=request
      FI

    WHEN SESSION_CLOSE THEN
      IF session=NULL THEN
        ShellSessionReply(request,PROCESS.RETURN_ERROR,
            DOS.ERROR_OBJECT_NOT_FOUND)
      ELSE
        ShellSessionClose(session)
        ShellSessionReply(request,PROCESS.RETURN_OK,0)
      FI

    WHEN SESSION_SELECT THEN
      IF session=NULL THEN
        ShellSessionReply(request,PROCESS.RETURN_ERROR,
            DOS.ERROR_OBJECT_NOT_FOUND)
      ELSEIF session.state<>SESSION_STATE_READY
          OR selectionRequest<>NULL THEN
        ShellSessionReply(request,PROCESS.RETURN_ERROR,DOS.ERROR_OBJECT_IN_USE)
      ELSE
        selectionRequest=request
      FI

    WHEN SESSION_CREATE THEN
      ShellSessionCreate(request)

    ELSE
      ShellSessionReply(request,PROCESS.RETURN_ERROR,DOS.ERROR_ACTION_NOT_KNOWN)
    ESAC
  OD

RETURN

; BUSY is retried by the controller loop while other events keep progressing.
CARD FUNC ShellSessionSelect(ShellSession POINTER session)

  IF selectedSession=session.control.identity THEN
    RETURN(CONSOLETYPES.CONTROL_OK)
  FI

  IF selectedSession=0 AND session.startup.unit=0 THEN
    selectedSession=session.control.identity
    RETURN(CONSOLETYPES.CONTROL_OK)
  FI

  LET previous=ShellSessionFind(selectedSession)
  LET oldUnit=IF previous=NULL THEN LONGCARD(0) ELSE previous.startup.unit FI
  LET status=CONSOLE.Activate(oldUnit,session.startup.unit)
  IF status=CONSOLETYPES.CONTROL_OK THEN
    selectedSession=session.control.identity
  FI

RETURN(status)

; READY publication and successful creation follow presentation admission.
PROC ShellControllerReady()
  BYTE index
  CARD status

  FOR index=0 TO SESSION_CAPACITY-1 DO
    BEGIN
      LET session=@sessions(index)
      LET request=session.readyRequest
      IF request<>NULL THEN
        IF session.control.closeRequested<>0 THEN
          session.readyRequest=NULL
          ShellSessionReply(request,PROCESS.RETURN_ERROR,DOS.ERROR_BREAK)
        ELSE
          status=CONSOLETYPES.CONTROL_OK
          IF session.watch.bound=0 THEN
            status=CONSOLE.WatchKey(session.startup.unit,33,3,
                shortcutMask,@session.watch)
          FI

          IF status=CONSOLETYPES.CONTROL_OK THEN
            status=ShellSessionSelect(session)
          FI

          IF status=CONSOLETYPES.CONTROL_BUSY THEN
            controllerRetry=1
          ELSE
            session.readyRequest=NULL
            IF status=CONSOLETYPES.CONTROL_OK THEN
              session.state=SESSION_STATE_READY
              session.ready=1
              ShellSessionReply(request,PROCESS.RETURN_OK,0)
              IF session.createRequest<>NULL THEN
                session.createRequest.value=session.control.identity
                ShellSessionReply(session.createRequest,PROCESS.RETURN_OK,0)
                session.createRequest=NULL
              FI
            ELSE
              session.result.primary=PROCESS.RETURN_FAIL
              session.result.secondary=DOS.ERROR_OBJECT_IN_USE
              ShellSessionClose(session)
              ShellSessionReply(request,PROCESS.RETURN_FAIL,
                  DOS.ERROR_OBJECT_IN_USE)
            FI
          FI
        FI
      FI
    END
  OD

RETURN

; Notices retain the captured session identity even if selection changed.
PROC ShellControllerSelection()
  BYTE index
  CARD status
  CONSOLETYPES.KeyNotice notice

  FOR index=0 TO SESSION_CAPACITY-1 DO
    BEGIN
      LET session=@sessions(index)
      IF session.watch.bound<>0 THEN
        WHILE CONSOLE.TakeKey(@session.watch,@notice)<>0 DO
          ; The established watch retains this exact console incarnation.
          IF notice.unit<>session.startup.unit THEN
            HEAPCORE.Abort($ff94)
          FI

          IF session.state=SESSION_STATE_READY
              OR session.state=SESSION_STATE_CLOSING THEN
            BEGIN
              LET next=ShellSessionNext(session.control.identity)
              IF next<>NULL THEN
                shortcutTarget=next.control.identity
              FI
            END
          FI
        OD
      FI
    END
  OD

  IF selectionRequest=NULL THEN
    BEGIN
      LET target=ShellSessionFind(shortcutTarget)
      IF target<>NULL AND target.state=SESSION_STATE_READY THEN
        status=ShellSessionSelect(target)
        IF status=CONSOLETYPES.CONTROL_BUSY THEN
          controllerRetry=1
          RETURN
        FI
      FI
    END

    shortcutTarget=0
    RETURN
  FI

  shortcutTarget=0
  LET session=ShellSessionFind(selectionRequest.session)
  IF session=NULL THEN
    ShellSessionReply(selectionRequest,PROCESS.RETURN_ERROR,
        DOS.ERROR_OBJECT_NOT_FOUND)
  ELSEIF session.state<>SESSION_STATE_READY THEN
    ShellSessionReply(selectionRequest,PROCESS.RETURN_ERROR,
        DOS.ERROR_OBJECT_IN_USE)
  ELSE
    status=ShellSessionSelect(session)
    IF status=CONSOLETYPES.CONTROL_BUSY THEN
      controllerRetry=1
      RETURN
    FI

    IF status=CONSOLETYPES.CONTROL_OK THEN
      ShellSessionReply(selectionRequest,PROCESS.RETURN_OK,0)
    ELSE
      ShellSessionReply(selectionRequest,PROCESS.RETURN_ERROR,
          DOS.ERROR_OBJECT_IN_USE)
    FI
  FI

  selectionRequest=NULL

RETURN

; Collection removes producers before selecting fallback and retiring views.
PROC ShellControllerCollect()
  BYTE index,pending
  CARD status

  FOR index=0 TO SESSION_CAPACITY-1 DO
    BEGIN
      LET session=@sessions(index)
      IF session.process<>0 THEN
        IF PROCESS.Collect(session.process,@session.result)<>0 THEN
          session.process=0
          session.state=SESSION_STATE_RETIRING
          IF session.watch.bound<>0 THEN
            status=CONSOLE.UnwatchKey(@session.watch)
            IF status<>CONSOLETYPES.CONTROL_OK THEN
              HEAPCORE.Abort($ff94)
            FI
          FI
        ELSEIF DOS.IoErr()<>DOS.ERROR_OBJECT_IN_USE THEN
          HEAPCORE.Abort($ff94)
        FI
      FI
    END
  OD

  LET selected=ShellSessionFind(selectedSession)
  IF selected<>NULL AND selected.state=SESSION_STATE_RETIRING THEN
    BEGIN
      LET fallback=ShellSessionNext(selectedSession)
      IF fallback<>NULL THEN
        status=ShellSessionSelect(fallback)
        IF status=CONSOLETYPES.CONTROL_BUSY THEN
          controllerRetry=1
          RETURN
        ELSEIF status<>CONSOLETYPES.CONTROL_OK THEN
          HEAPCORE.Abort($ff94)
        FI
      ELSE
        pending=0
        FOR index=0 TO SESSION_CAPACITY-1 DO
          IF sessions(index).state=SESSION_STATE_CREATING THEN
            pending=1
          FI
        OD

        ; Keep the visible previous view until a pending READY can replace it.
        IF pending<>0 THEN
          RETURN
        FI
      FI
    END
  FI

  FOR index=0 TO SESSION_CAPACITY-1 DO
    BEGIN
      LET session=@sessions(index)
      IF session.state=SESSION_STATE_RETIRING THEN
        IF session.startup.unit<>0 THEN
          IF CONSOLE.Destroy(session.startup.unit)=0 THEN
            controllerRetry=1
          ELSE
            session.startup.unit=0
          FI
        FI

        IF session.startup.unit=0 THEN
          IF session.readyRequest<>NULL THEN
            HEAPCORE.Abort($ff94)
          FI

          IF session.createRequest<>NULL THEN
            IF session.result.primary=PROCESS.RETURN_OK THEN
              session.result.primary=PROCESS.RETURN_ERROR
              session.result.secondary=DOS.ERROR_BREAK
            FI

          FI

          IF selectedSession=session.control.identity THEN
            selectedSession=0
          FI

          BEGIN
            LET request=session.createRequest
            session.createRequest=NULL
            controllerStatus=session.result.primary
            contexts(index).control=NULL
            session.state=SESSION_STATE_FREE
            controllerLive==-1
            ; Reply may immediately schedule the creator: publish cleanup first.
            IF request<>NULL THEN
              ShellSessionReply(request,session.result.primary,
                  session.result.secondary)
            FI
          END
        FI
      FI
    END
  OD

RETURN

; Union normal port, subscription and Process signals; no child-specific wait.
LONGCARD FUNC ShellControllerStep()
  BYTE index
  LONGCARD mask

  controllerRetry=0
  ShellControllerRequests()
  ShellControllerReady()
  ShellControllerSelection()
  ShellControllerCollect()
  mask=(LONGCARD(1) LSH shellRequests.mp_SigBit) OR shortcutMask
  FOR index=0 TO SESSION_CAPACITY-1 DO
    IF sessions(index).process<>0 THEN
      mask=mask OR PROCESS.CompletionMask(sessions(index).process)
    FI
  OD

  ; Optional desktop children remain owned and collected by root's service.
  LET client=DOSCLIENT.Ensure()
  IF client<>NULL AND client.waitService<>NULL THEN
    client.waitMask=client.waitService()
    mask=mask OR client.waitMask
  FI

RETURN(mask)

; One-time boot owns system setup, then detaches all streams before spawning.
BYTE FUNC ShellControllerStart(BYTE prime)
  LONGINT cleaned
  BYTE POINTER directory

  controllerStatus=PROCESS.RETURN_OK
  shortcutBit=$ff
  IF ShellSystemStart(@systemContext,shellCon)=0 THEN
    cleaned=ShellFinish(@systemContext)
    controllerStatus=PROCESS.RETURN_FAIL
    RETURN(0)
  FI

  bootPrimary=systemContext.shell.status
  bootSecondary=systemContext.shell.error
  firstFlags=SESSION_FIRST_BOOT
  IF prime<>0 THEN
    firstFlags=firstFlags OR SESSION_PRIME
  FI

  IF bootScriptsReady<>0 THEN
    firstFlags=firstFlags OR SESSION_SCRIPTS
  FI

  shellRequests=EXEC.CreateMsgPort()
  shortcutBit=EXEC.AllocSignal($ff)
  IF shellRequests=NULL OR shortcutBit=$ff THEN
    cleaned=ShellFinish(@systemContext)
    controllerStatus=PROCESS.RETURN_FAIL
    RETURN(0)
  FI

  shortcutMask=LONGCARD(1) LSH shortcutBit
  cleaned=ShellFinish(@systemContext)
  IF systemContext.shell<>NULL THEN
    controllerStatus=PROCESS.RETURN_FAIL
    RETURN(0)
  FI

  directory=BYTE POINTER(c"")
  IF bootPrimary=PROCESS.RETURN_OK THEN
    directory=shellRoot
  FI
  IF ShellSessionSpawn(@sessions(0),0,directory,firstFlags,NULL)=0 THEN
    ShellControllerCollect()
    controllerStatus=PROCESS.RETURN_FAIL
    RETURN(0)
  FI

RETURN(1)

; Root remains responsive while the shell reads, runs commands or retires.
LONGINT FUNC ShellControllerRun()
  LONGCARD mask,bits

  WHILE controllerLive<>0 DO
    mask=ShellControllerStep()
    IF controllerLive<>0 THEN
      IF controllerRetry<>0 THEN
        EXEC.Yield()
      ELSE
        bits=EXEC.Wait(mask)
      FI
    FI
  OD

RETURN(controllerStatus)

; Application children have retired before their message port and wake bit.
PROC ShellControllerStop()
  LONGCARD ignored

  IF controllerLive<>0 THEN
    HEAPCORE.Abort($ff94)
  FI

  IF shellRequests<>NULL THEN
    ShellControllerRequests()
    EXEC.DeleteMsgPort(shellRequests)
    shellRequests=NULL
  FI

  IF shortcutMask<>0 THEN
    ignored=EXEC.SetSignal(0,shortcutMask)
    EXEC.FreeSignal(shortcutBit)
    shortcutMask=0
  ELSEIF shortcutBit<>$ff THEN
    ; A failed port allocation may still have admitted the signal.
    EXEC.FreeSignal(shortcutBit)
    shortcutBit=$ff
  FI

  IF DOS.ReleaseContext()=0 THEN
    HEAPCORE.Abort($ff94)
  FI

RETURN
