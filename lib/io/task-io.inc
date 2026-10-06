; Policy runs under SWITCHING with IRQs enabled. Open admission returns a
; route; established resident dispatch runs in the caller. Request ownership
; and settled Close/Delete are caller preconditions.
BYTE FUNC IOService(BYTE service)

RETURN(service>=IO_SERVICE_OPEN_DEVICE AND service<=IO_SERVICE_TEST_STEP)

; NUL-terminated resident names occupy bytes 32..62 of the upper arena.
; Store packed character pairs so the compiler emits no near string literals.
PROC InitIONames()
  CARD POINTER words

  words=CARD POINTER(ADDRESS(IS_BASE+32))
  words(0)=$6d69
  words(1)=$656d
  words(2)=$6964
  words(3)=$7461
  words(4)=$2e65
  words(5)=$6564
  words(6)=$6976
  words(7)=$6563
  words(8)=$7100
  words(9)=$6575
  words(10)=$6575
  words(11)=$2e64
  words(12)=$6564
  words(13)=$6976
  words(14)=$6563
  words(15)=$0000

RETURN

; Initialize kernel-side resident-device state and queue ownership.
BYTE FUNC InitIO()
  IOResident POINTER device
  IOQueue POINTER queue

  IF SIZEOF(IOResident)<>4 OR SIZEOF(IOQueue)<>24 OR IS_BYTES<>256 THEN
    RETURN(0)
  FI

  device=IOResident POINTER(ADDRESS(IS_BASE))
  device.opens=0
  device.unit=0
  device=IOResident POINTER(ADDRESS(IS_BASE+4))
  device.opens=0
  device.unit=0
  queue=IOQueue POINTER(ADDRESS(IS_BASE+8))
  EXECLISTS.NewList(@queue.pending)
  queue.pending.lh_Type=0
  queue.pending.lh_Pad=0
  queue.active=IORequest POINTER(0)
  queue.phase=0
  queue.cancelled=0
  queue.worker=TaskControl POINTER(0)
  queue.mask=0
  InitResidentStorage()
  IF IS_TEST_DEVICE<>0 THEN
    InitIONames()
  FI

RETURN(1)

; Validate a request extent before the kernel interprets its fields.
BYTE FUNC IOExtent(IORequest POINTER request CARD size)
  Message POINTER msg

  msg=Message POINTER(request)
  IF ValidMessage(msg)=0 THEN
    RETURN(0)
  FI

  IF msg.mn_Length<size THEN
    RETURN(0)
  FI

RETURN(LONGCARD(ADDRESS(request))+LONGCARD(msg.mn_Length)<=LONGCARD($1000000))

; Publish an admission error using the public request error representation.
CARD FUNC IOError(CARD saved BYTE error)
  CARD value

  value=CARD(error)
  IF error>=128 THEN
    value=value OR $ff00
  FI

  MaskResult(saved,LONGCARD(value))

RETURN(saved)

; Recognize a supported resident name within the caller's mapped extent.
BYTE FUNC IOName(BYTE POINTER name BYTE POINTER expected)

  IF name=BYTE POINTER(0) THEN
    RETURN(0)
  FI

RETURN(SameName(name,expected))

; Validate caller storage before admitting an ordinary resident-device open.
CARD FUNC IOOpen(CARD saved IOOpenArgs POINTER args)
  IORequest POINTER request

  request=args.request
  IF IOExtent(request,IO_IOREQUEST_BYTES)=0 THEN
    RETURN(T_FAULT)
  FI

  request.io_Device=BYTE POINTER(0)
  request.io_Unit=BYTE POINTER(0)
  IF IOName(args.name,BYTE POINTER(ADDRESS(TIMERMETA.NAME)))<>0 THEN
    MaskResult(saved,LONGCARD(IO_ROUTE_TIMER))
    RETURN(saved)
  FI

  IF ConsoleName(args.name)<>0 THEN
    MaskResult(saved,LONGCARD(IO_ROUTE_CONSOLE))
    RETURN(saved)
  FI

  IF IOName(args.name,BYTE POINTER(ADDRESS(IS_BASE+224)))<>0 THEN
    MaskResult(saved,LONGCARD(IO_ROUTE_SIO))
    RETURN(saved)
  FI

  IF IS_TEST_DEVICE<>0 THEN
    IF IOName(args.name,BYTE POINTER(ADDRESS(IS_BASE+32)))<>0 THEN
      MaskResult(saved,LONGCARD(IO_ROUTE_IMMEDIATE))
      RETURN(saved)
    FI
  FI

RETURN(IOOpenTest(saved,args))

; Admit the diagnostic resident only for the configured test profile.
CARD FUNC IOOpenTest(CARD saved IOOpenArgs POINTER args)
  IORequest POINTER request
  IOResident POINTER device
  BYTE error

  request=args.request
  error=BYTE(IO_IOERR_OPENFAIL)
  device=IOResident POINTER(0)
  IF IS_TEST_DEVICE<>0 AND args.unit=0 AND args.flags=0 THEN
    IF IOName(args.name,BYTE POINTER(ADDRESS(IS_BASE+49)))<>0 THEN
      IF request.io_Message.mn_Length<IO_IOSTDREQ_BYTES THEN
        error=BYTE(IO_IOERR_BADLENGTH)
      ELSE
        device=IOResident POINTER(ADDRESS(IS_BASE+4))
      FI
    FI

    IF device<>IOResident POINTER(0) THEN
      IF device.opens<>$ffff THEN
        device.opens==+1
        request.io_Device=BYTE POINTER(device)
        request.io_Unit=@device.unit
        error=0
      FI
    FI
  FI

  request.io_Error=error

RETURN(IOError(saved,error))

; Publish completion according to quick or message-reply ownership.
CARD FUNC IOComplete(TaskControl POINTER caller CARD saved IORequest
    POINTER request)

  IF (request.io_Flags & IO_IOF_QUICK)<>0 THEN
    request.io_Message.mn_Node.ln_Type=P_NT_FREEMSG
    RETURN(IOError(saved,request.io_Error))
  FI

; This is the last access to request. SendMessage only retains task metadata
; after link publication; the native wrapper returns without rereading it.
RETURN(SendMessage(caller,saved,request.io_Message.mn_ReplyPort,
    @request.io_Message,P_NT_REPLYMSG))

; Return ownership of a settled request to its waiting caller.
CARD FUNC IOCollect(TaskControl POINTER caller CARD saved IORequest POINTER request)

  LET kind=PortCollect(@request.io_Message)
  IF kind=P_NT_MESSAGE THEN
    MaskResult(saved,LONGCARD($10000)
        OR LONGCARD(request.io_Message.mn_ReplyPort.mp_SigBit))
    RETURN(saved)
  FI

  IF kind<>P_NT_REPLYMSG AND kind<>P_NT_FREEMSG THEN
    RETURN(T_FAULT)
  FI

RETURN(IOError(saved,request.io_Error))

; Transfer a request into the resident's pending queue.
CARD FUNC IOEnqueue(TaskControl POINTER caller CARD saved IORequest POINTER request)
  IOQueue POINTER queue
  IOStdReq POINTER standard

  queue=IOQueue POINTER(ADDRESS(IS_BASE+8))
  standard=IOStdReq POINTER(request)
  request.io_Flags=request.io_Flags & $fe
  IF queue.worker=TaskControl POINTER(0) THEN
    request.io_Error=BYTE(IO_IOERR_UNITBUSY)
    RETURN(IOComplete(caller,saved,request))
  FI

  IF standard.io_Length=0 THEN
    request.io_Error=BYTE(IO_IOERR_BADLENGTH)
    RETURN(IOComplete(caller,saved,request))
  FI

  IF standard.io_Data=BYTE POINTER(0)
      OR standard.io_Length>LONGCARD($1000000)-LONGCARD(ADDRESS(
      standard.io_Data)) THEN
    request.io_Error=BYTE(IO_IOERR_BADADDRESS)
    RETURN(IOComplete(caller,saved,request))
  FI

  EXECLISTS.AddTail(@queue.pending,@request.io_Message.mn_Node)
  IF PostSignal(queue.worker,queue.mask)<>0 THEN
    caller.pending=1
  FI

RETURN(saved)

; Start a deterministic diagnostic operation through the normal request
; protocol.
CARD FUNC IOTestBegin(TaskControl POINTER caller CARD saved IORequest
    POINTER request)
  IOStdReq POINTER standard

  IF request.io_Command=IO_CMD_READ OR request.io_Command=IO_CMD_WRITE THEN
    IF request.io_Message.mn_Length<IO_IOSTDREQ_BYTES THEN
      request.io_Error=BYTE(IO_IOERR_BADLENGTH)
    ELSE
      standard=IOStdReq POINTER(request)
      standard.io_Actual=0
      IF request.io_Command=IO_CMD_WRITE THEN
        request.io_Error=9
      ELSEIF request.io_Device=BYTE POINTER(ADDRESS(IS_BASE+4)) THEN
        RETURN(IOEnqueue(caller,saved,request))
      FI
    FI
  ELSEIF request.io_Command<>IO_CMD_RESET THEN
    request.io_Error=BYTE(IO_IOERR_NOCMD)
  FI

RETURN(IOComplete(caller,saved,request))

; Cancel a request through its owning resident's supported path.
CARD FUNC IOAbort(TaskControl POINTER caller CARD saved IORequest POINTER request)
  IOQueue POINTER queue

  IF request.io_Message.mn_Node.ln_Type<>P_NT_MESSAGE THEN
    RETURN(saved)
  FI

  IF request.io_Device<>BYTE POINTER(ADDRESS(IS_BASE+4)) THEN
    RETURN(T_FAULT)
  FI

  queue=IOQueue POINTER(ADDRESS(IS_BASE+8))
  IF queue.active=request THEN
    queue.cancelled=1
    RETURN(saved)
  FI

  EXECLISTS.Remove(@request.io_Message.mn_Node)
  request.io_Error=BYTE(IO_IOERR_ABORTED)

RETURN(IOComplete(caller,saved,request))

; Test-only worker control. It cannot be imported or dispatched in a normal
; image. Take and active/preparing publication are one guarded transaction.
CARD FUNC IOWorkerControl(TaskControl POINTER caller CARD saved IOQueue
    POINTER queue BYTE operation)

  IF operation=0 THEN
    IF queue.worker<>TaskControl POINTER(0)
        OR (caller.item.tc_SigAlloc & LONGCARD($80000000))=0 THEN
      RETURN(T_FAULT)
    FI

    queue.worker=caller
    queue.mask=LONGCARD($80000000)
  ELSE
    IF queue.worker<>caller THEN
      RETURN(T_FAULT)
    FI

    IF queue.active<>IORequest POINTER(0)
        OR EXECLISTS.IsListEmpty(@queue.pending)=0 THEN
      RETURN(T_FAULT)
    FI

    queue.worker=TaskControl POINTER(0)
    queue.mask=0
  FI

  MaskResult(saved,0)

RETURN(saved)

; Transfer one pending request into active worker ownership.
CARD FUNC IOClaim(CARD saved IOQueue POINTER queue)
  IORequest POINTER request

  IF queue.active<>IORequest POINTER(0) THEN
    RETURN(T_FAULT)
  FI

  request=IORequest POINTER(EXECLISTS.RemHead(@queue.pending))
  queue.active=request
  queue.phase=1
  queue.cancelled=0
  IF request=IORequest POINTER(0) THEN
    queue.phase=0
  FI

  MaskResult(saved,LONGCARD(ADDRESS(request)))

RETURN(saved)

; Advance diagnostic-device work at its bounded service point.
CARD FUNC IOTest(TaskControl POINTER caller CARD saved BYTE operation)
  IOQueue POINTER queue

  queue=IOQueue POINTER(ADDRESS(IS_BASE+8))
  IF IS_TEST_DEVICE=0 THEN
    RETURN(T_FAULT)
  FI

  IF operation=0 OR operation=4 THEN
    RETURN(IOWorkerControl(caller,saved,queue,operation))
  FI

  IF queue.worker<>caller THEN
    RETURN(T_FAULT)
  FI

  IF operation=1 THEN
    RETURN(IOClaim(saved,queue))
  FI

  IF queue.active=IORequest POINTER(0) THEN
    RETURN(T_FAULT)
  FI

  IF operation=2 THEN
    IF queue.phase<>1 THEN
      RETURN(T_FAULT)
    FI

    queue.phase=2
    ; In particular, do not clear a cancellation latched during preparation.
    MaskResult(saved,LONGCARD(queue.cancelled))
    RETURN(saved)
  FI

  IF operation<>3 THEN
    RETURN(T_FAULT)
  FI

RETURN(IOTestFinish(caller,saved,queue))

; Retire a diagnostic operation through the common completion protocol.
CARD FUNC IOTestFinish(TaskControl POINTER caller CARD saved IOQueue POINTER queue)
  IORequest POINTER request
  IOStdReq POINTER standard

  request=queue.active
  IF queue.phase<>2 THEN
    RETURN(T_FAULT)
  FI

  standard=IOStdReq POINTER(request)
  IF queue.cancelled<>0 THEN
    request.io_Error=BYTE(IO_IOERR_ABORTED)
  ELSE
    standard.io_Data^=$5a
    standard.io_Actual=1
    request.io_Error=0
  FI

  queue.active=IORequest POINTER(0)
  queue.phase=0
  queue.cancelled=0
  MaskResult(saved,0)

RETURN(IOComplete(caller,saved,request))

; Dispatch public I/O services after validating the caller's gateway packet.
CARD FUNC IOCall(TaskControl POINTER caller CARD saved BYTE service)
  IOPointerArgs POINTER args
  IORequest POINTER request
  CARD base,bytes

  base=SavedWord(saved,T_FRAME_X)
  bytes=3
  IF service=IO_SERVICE_OPEN_DEVICE THEN
    bytes=16
  FI

  IF service=IO_SERVICE_TEST_STEP THEN
    bytes=1
  FI

  IF base<caller.stackFloor OR base>caller.stackTop THEN
    RETURN(T_FAULT)
  FI

  IF bytes>caller.stackTop-base+1 THEN
    RETURN(T_FAULT)
  FI

  args=IOPointerArgs POINTER(ArgumentPointer(saved))
  IF service=IO_SERVICE_TEST_STEP THEN
    RETURN(IOTest(caller,saved,BYTE POINTER(args)^))
  FI

  IF service=IO_SERVICE_CREATE_CHECK THEN
    Result(saved,CARD(ValidPort(MsgPort POINTER(args.request))))
    RETURN(saved)
  FI

  IF service=IO_SERVICE_OPEN_DEVICE THEN
    RETURN(IOOpen(saved,IOOpenArgs POINTER(args)))
  FI

  request=args.request
  IF service=IO_SERVICE_DELETE_CHECK THEN
    Result(saved,request.io_Message.mn_Length)
    RETURN(saved)
  FI

RETURN(IORequestCall(caller,saved,service,request))

; Collect a request; resident dispatch and observation are caller-side.
CARD FUNC IORequestCall(TaskControl POINTER caller CARD saved BYTE service
    IORequest POINTER request)
  IOResident POINTER device

  IF service=IO_SERVICE_WAIT_REQUEST THEN
    RETURN(IOCollect(caller,saved,request))
  FI

  ; Only the queued fixture retains a kernel-owned device protocol.
  IF IS_TEST_DEVICE=0 THEN
    RETURN(T_FAULT)
  FI

  MaskResult(saved,0)
  CASE service OF
  WHEN IO_SERVICE_TEST_BEGIN THEN
    RETURN(IOTestBegin(caller,saved,request))

  WHEN IO_SERVICE_TEST_ABORT THEN
    RETURN(IOAbort(caller,saved,request))

  WHEN IO_SERVICE_TEST_CLOSE THEN
    device=IOResident POINTER(request.io_Device)
    device.opens==-1
    request.io_Device=NULL
    request.io_Unit=NULL
    RETURN(saved)
  ESAC

RETURN(T_FAULT)
