; Caller-context device callbacks run under IOCORE's Forbid region. Worker
; handoff/completion use the same exclusion; IRQ capture never reads requests.
PUBLIC BYTE FUNC Bound(EXEC.IORequest POINTER request)

  IF request.io_Device<>BYTE POINTER(GetService()) THEN
    RETURN(0)
  FI

  LET entry=CONSOLEWINDOWS.Bound(request.io_Unit)
  IF entry=NULL THEN
    RETURN(0)
  FI

  LET instance=CONSOLETYPES.Instance POINTER(entry.instance)

RETURN(instance.open<>0)

; Close must not invalidate an instance still borrowed by any request.
BYTE FUNC Idle(CONSOLETYPES.Service POINTER service CONSOLETYPES.Instance
    POINTER instance)
  EXECLISTS.Node POINTER node
  EXEC.IORequest POINTER request

  IF instance.read<>NULL OR instance.write<>NULL THEN
    RETURN(0)
  FI

  IF service.arrival<>NULL THEN
    request=EXEC.IORequest POINTER(service.arrival)
    IF request.io_Unit=BYTE POINTER(instance) THEN
      RETURN(0)
    FI
  FI

  node=service.port.mp_MsgList.lh_Head
  WHILE node.ln_Succ<>NULL DO
    request=EXEC.IORequest POINTER(node)
    IF request.io_Unit=BYTE POINTER(instance) THEN
      RETURN(0)
    FI

    node=node.ln_Succ
  OD

RETURN(EXECLISTS.IsMinListEmpty(@instance.writes))

; Shared resident endpoints use an independent PA_IGNORE port. Their references
; outlive the first caller; ordinary Task-owned opens retain that caller.
BYTE FUNC RetainOpener(EXEC.IORequest POINTER request CONSOLETYPES.Instance
    POINTER instance)

  LET reply=request.io_Message.mn_ReplyPort
  IF reply<>NULL THEN
    IF reply.mp_Flags=EXEC.PA_IGNORE THEN
      RETURN(1)
    FI
  FI

RETURN(EXEC.RetainTask(EXEC.FindTask(NULL),@instance.lease))

; Admit one terminal endpoint and retain its opener when the port belongs to a
; Task.
PUBLIC INT FUNC Open(BYTE POINTER name LONGCARD unit EXEC.IORequest
    POINTER request LONGCARD flags)
  CONSOLETYPES.Instance POINTER instance
  BYTE error

  LET service=GetService()
  LET entry=CONSOLEWINDOWS.Find(unit)
  error=BYTE(EXEC.IOERR_OPENFAIL)
  IF DISPLAY.Kind()=DISPLAY.VBXE THEN
    request.io_Error=BYTE(EXEC.IOERR_UNITBUSY)
    RETURN(EXEC.IOERR_UNITBUSY)
  FI

  IF service.state=2 AND service.stop=0 AND entry<>NULL AND flags=0 THEN
    instance=CONSOLETYPES.Instance POINTER(entry.instance)
    IF request.io_Message.mn_Length<EXEC.IOSTDREQ_SIZE THEN
      error=BYTE(EXEC.IOERR_BADLENGTH)
    ELSEIF instance.open<>0 THEN
      error=BYTE(EXEC.IOERR_UNITBUSY)
    ELSEIF RetainOpener(request,instance)=0 THEN
      error=BYTE(EXEC.IOERR_OPENFAIL)
    ELSE
      CONSOLECAPTURE.ClearUnit(unit)
      instance.inputHead=0
      instance.inputTail=0
      instance.inputCount=0
      instance.inputLost=0
      instance.lastValid=0
      instance.open=1
      instance.opens=1
      request.io_Device=BYTE POINTER(service)
      request.io_Unit=BYTE POINTER(instance)
      error=0
    FI
  FI

  request.io_Error=error
  IF error>=128 THEN
    RETURN(INT(CARD(error) OR $ff00))
  FI

RETURN(INT(error))

; Release an idle endpoint and its Task lease before allowing another opener.
PUBLIC PROC Close(EXEC.IORequest POINTER request)

  LET service=GetService()
  LET instance=CONSOLETYPES.Instance POINTER(request.io_Unit)
  IF Idle(service,instance)=0 THEN
    HEAPCORE.Abort(4)
  FI

  IF instance.lease.task<>NULL THEN
    IF EXEC.ReleaseTask(@instance.lease)=0 THEN
      HEAPCORE.Abort(4)
    FI
  FI

  instance.open=0
  instance.opens=0
  instance.inputHead=0
  instance.inputTail=0
  instance.inputCount=0
  instance.inputLost=0
  LET entry=CONSOLEWINDOWS.Bound(BYTE POINTER(instance))
  CONSOLECAPTURE.ClearUnit(entry.unit)
  request.io_Device=NULL
  request.io_Unit=NULL
  EXEC.Signal(@service.task,$80000000)

RETURN

; Honor quick completion; queued requests return through their reply port.
PROC Complete(EXEC.IORequest POINTER request)

  IF (request.io_Flags & EXEC.IOF_QUICK)<>0 THEN
    request.io_Message.mn_Node.ln_Type=EXEC.NT_FREEMSG
  ELSE
    EXEC.ReplyMsg(@request.io_Message)
  FI

RETURN

; Reject malformed requests before they enter the worker's queues.
BYTE FUNC Immediate(EXEC.IOStdReq POINTER request)

  IF request.io_Message.mn_Length<EXEC.IOSTDREQ_SIZE THEN
    RETURN(BYTE(EXEC.IOERR_BADLENGTH))
  FI

  request.io_Actual=0
  IF (request.io_Flags & $fe)<>0 THEN
    RETURN(BYTE(EXEC.IOERR_BADLENGTH))
  FI

  IF request.io_Offset<>0 THEN
    RETURN(BYTE(EXEC.IOERR_BADADDRESS))
  FI

  IF request.io_Command=EXEC.CMD_CLEAR THEN
    RETURN(0)
  FI

  IF request.io_Command<>EXEC.CMD_READ AND request.io_Command<>EXEC.CMD_WRITE THEN
    RETURN(BYTE(EXEC.IOERR_NOCMD))
  FI

  IF request.io_Command=EXEC.CMD_WRITE AND request.io_Length=SYS.MAXLONGCARD THEN
    RETURN(BYTE(EXEC.IOERR_BADLENGTH))
  FI

  IF request.io_Length<>0 THEN
    IF request.io_Data=NULL
        OR request.io_Length>LONGCARD($1000000)-LONGCARD(ADDRESS(
        request.io_Data)) THEN
      RETURN(BYTE(EXEC.IOERR_BADADDRESS))
    FI
  FI

RETURN(0)

; Reserve read ownership where needed, then transfer the request to the
; worker.
PUBLIC PROC BeginIO(EXEC.IORequest POINTER request)

  LET service=GetService()
  LET instance=CONSOLETYPES.Instance POINTER(request.io_Unit)
  LET standard=EXEC.IOStdReq POINTER(request)
  request.io_Error=Immediate(standard)
  IF request.io_Error<>0 THEN
    Complete(request)
    RETURN
  FI

  IF service.state<>2 OR service.stop<>0 THEN
    request.io_Error=BYTE(EXEC.IOERR_UNITBUSY)
    Complete(request)
    RETURN
  FI

  IF request.io_Command<>EXEC.CMD_CLEAR AND standard.io_Length=0 THEN
    Complete(request)
    RETURN
  FI

  IF request.io_Command=EXEC.CMD_READ THEN
    IF instance.read<>NULL THEN
      request.io_Error=BYTE(EXEC.IOERR_UNITBUSY)
      Complete(request)
      RETURN
    FI

    instance.read=BYTE POINTER(request)
    instance.readCancel=0
    instance.readReady=0
  FI

  request.io_Flags=request.io_Flags & $fe
  EXEC.PutMsg(@service.port,@request.io_Message)

RETURN

; Cancel retained work or retire an unclaimed request without racing
; completion.
PUBLIC PROC AbortIO(EXEC.IORequest POINTER request)

  IF request.io_Message.mn_Node.ln_Type<>EXEC.NT_MESSAGE THEN
    RETURN
  FI

  LET service=GetService()
  LET instance=CONSOLETYPES.Instance POINTER(request.io_Unit)
  IF instance.write=BYTE POINTER(request) THEN
    instance.writeCancel=1
  ELSEIF service.arrival=BYTE POINTER(request) THEN
    service.arrivalCancel=1
  ELSEIF instance.read=BYTE POINTER(request) AND instance.readReady<>0 THEN
    instance.readCancel=1
  ELSE
    IF instance.read=BYTE POINTER(request) THEN
      instance.read=NULL
    FI

    EXECLISTS.Remove(@request.io_Message.mn_Node)
    request.io_Error=BYTE(EXEC.IOERR_ABORTED)
    Complete(request)
    RETURN
  FI

  EXEC.Signal(@service.task,$80000000)

RETURN

; Move one queued write into instance ownership under the queue exclusion.
EXEC.IOStdReq POINTER FUNC ClaimWrite(CONSOLETYPES.Instance POINTER instance)

  EXEC.Forbid()
  LET request=EXEC.IOStdReq POINTER(EXECLISTS.RemHead(EXECLISTS.List POINTER(
      @instance.writes)))
  instance.write=BYTE POINTER(request)
  instance.writeCancel=0
  EXEC.Permit()

RETURN(request)

; Return a completed write only after retained terminal editing has settled.
PROC FinishWrite(CONSOLETYPES.Instance POINTER instance EXEC.IOStdReq
    POINTER request)

  EXEC.Forbid()
  IF instance.write<>BYTE POINTER(request)
      OR instance.operation<>CONSOLETYPES.OP_IDLE THEN
    HEAPCORE.Abort(4)
  FI

  IF instance.writeCancel<>0 THEN
    request.io_Error=BYTE(EXEC.IOERR_ABORTED)
  FI

  instance.write=NULL
  instance.writeCancel=0
  Complete(EXEC.IORequest POINTER(request))
  EXEC.Permit()

RETURN

; Release the instance's read ownership before returning the request.
PROC FinishRead(CONSOLETYPES.Instance POINTER instance EXEC.IOStdReq
    POINTER request)

  EXEC.Forbid()
  IF instance.read<>BYTE POINTER(request) THEN
    HEAPCORE.Abort(4)
  FI

  IF instance.readCancel<>0 THEN
    request.io_Error=BYTE(EXEC.IOERR_ABORTED)
  FI

  instance.read=NULL
  instance.readCancel=0
  instance.readReady=0
  Complete(EXEC.IORequest POINTER(request))
  EXEC.Permit()

RETURN

; Classify one new request; clear operations retain their cancellation
; identity.
PROC Arrival(CONSOLETYPES.Service POINTER service)
  CONSOLETYPES.Instance POINTER instance
  BYTE clear

  IF EXECLISTS.IsListEmpty(@service.port.mp_MsgList)<>0 THEN
    RETURN
  FI

  EXEC.Forbid()
  LET request=EXEC.IOStdReq POINTER(EXEC.GetMsg(@service.port))
  clear=0
  IF request<>NULL THEN
    instance=CONSOLETYPES.Instance POINTER(request.io_Unit)
    CASE request.io_Command OF
    WHEN EXEC.CMD_READ THEN
      instance.readReady=1
    WHEN EXEC.CMD_WRITE THEN
      EXECLISTS.AddTail(EXECLISTS.List POINTER(@instance.writes),
          @request.io_Message.mn_Node)
    ELSE
      service.arrival=BYTE POINTER(request)
      service.arrivalCancel=0
      clear=1
    ESAC
  FI

  EXEC.Permit()
  IF clear=0 THEN
    RETURN
  FI

  IF service.arrivalCancel=0 THEN
    CONSOLEINPUT.Clear(instance)
  FI

  EXEC.Forbid()
  IF service.arrivalCancel<>0 THEN
    request.io_Error=BYTE(EXEC.IOERR_ABORTED)
  FI

  service.arrival=NULL
  service.arrivalCancel=0
  Complete(EXEC.IORequest POINTER(request))
  EXEC.Permit()

RETURN

; Keep the worker awake while any admitted terminal still has useful work.
BYTE FUNC Runnable(CONSOLETYPES.Service POINTER service)
  BYTE index

  IF CONSOLEINPUT.Pending()<>0 OR service.stop<>0
      OR EXECLISTS.IsListEmpty(@service.port.mp_MsgList)=0 THEN
    RETURN(1)
  FI

  LET windows=CONSOLEWINDOWS.Registry()
  FOR index=0 TO CONSOLETYPES.WINDOW_SLOTS-1 DO
    IF windows.items(index).state=CONSOLETYPES.WIN_LIVE THEN
      IF CONSOLEWINDOWS.Runnable(@windows.items(index))<>0 THEN
        RETURN(1)
      FI
    FI
  OD

RETURN(0)
