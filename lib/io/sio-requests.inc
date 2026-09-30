; Task-side resident records reuse the existing 64-byte upper-RAM bus slot.
; IRQ code never reads this record; the worker is an ordinary public Task.
TYPE DriverWaiter=[
  DriverWaiter POINTER next
  EXEC.Task POINTER task
  LONGCARD mask
  EXEC.TaskLease lease
  BYTE bit
]

TYPE DriverBus=[
  CARD opens
  BYTE state,stop
  EXEC.Task POINTER worker
  EXEC.IORequest POINTER active
  BYTE phase,cancelled
  EXEC.MsgPort port
  LONGCARD generation
  EXEC.TaskLease lease
  DriverWaiter POINTER waiters
]

TYPE DriverUnit=[
  CARD opens
  BYTE unit
]

; Require a live bus and unit binding before interpreting a device request.
PUBLIC BYTE FUNC Bound(EXEC.IORequest POINTER request)
  DriverBus POINTER bus
  DriverUnit POINTER unit
  LONGCARD unitAddress

  IF request.io_Device<>BYTE POINTER(ADDRESS(IS_BASE+64)) THEN
    RETURN(0)
  FI

  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  unitAddress=LONGCARD(ADDRESS(request.io_Unit))
  IF unitAddress<LONGCARD(IS_BASE+130) OR unitAddress>LONGCARD(IS_BASE+158) THEN
    RETURN(0)
  FI

  IF ((unitAddress-LONGCARD(IS_BASE+130)) & 3)<>0 THEN
    RETURN(0)
  FI

  unit=DriverUnit POINTER(ADDRESS(request.io_Unit)-SIZE(2))

RETURN(bus.opens<>0 AND unit.opens<>0 AND (bus.state=2 OR bus.state=5))

; Retain a supported physical unit only while the SIO worker accepts opens.
PUBLIC INT FUNC Open(BYTE POINTER name LONGCARD number EXEC.IORequest
    POINTER request LONGCARD flags)
  DriverBus POINTER bus
  DriverUnit POINTER unit
  BYTE error
  BYTE POINTER offline

  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  offline=BYTE POINTER(SD_OFFLINE)
  error=BYTE(EXEC.IOERR_OPENFAIL)
  IF offline^<>0 THEN
    bus.state=5
  FI

  IF bus.state=5 THEN
    error=EXEC.SIOERR_BUSUNAVAILABLE
  ELSEIF bus.state=2 AND bus.stop=0 AND number>=49 AND number<=56 AND flags=0 THEN
    IF request.io_Message.mn_Length<EXEC.IOSIOREQ_SIZE THEN
      error=BYTE(EXEC.IOERR_BADLENGTH)
    ELSEIF bus.opens<>$ffff THEN
      unit=DriverUnit POINTER(ADDRESS(IS_BASE+128)+(SIZE(number-49) LSH 2))
      bus.opens==+1
      unit.opens==+1
      unit.unit=BYTE(number)
      request.io_Device=BYTE POINTER(bus)
      request.io_Unit=@unit.unit
      error=0
    FI
  FI

  request.io_Error=error
  IF error>=128 THEN
    RETURN(INT(CARD(error) OR $ff00))
  FI

RETURN(INT(error))

; Drop the unit binding and wake shutdown when the final opener leaves.
PUBLIC PROC Close(EXEC.IORequest POINTER request)
  DriverBus POINTER bus
  DriverUnit POINTER unit

  bus=DriverBus POINTER(request.io_Device)
  unit=DriverUnit POINTER(ADDRESS(request.io_Unit)-SIZE(2))
  unit.opens==-1
  bus.opens==-1
  request.io_Device=BYTE POINTER(0)
  request.io_Unit=BYTE POINTER(0)
  IF bus.opens=0 AND bus.stop<>0 THEN
    EXEC.Signal(bus.worker,LONGCARD($20000000))
  FI

RETURN

; Transfer accepted requests to the worker or reply with the current bus
; error.
PUBLIC PROC BeginIO(EXEC.IORequest POINTER request)
  DriverBus POINTER bus
  BYTE POINTER offline

  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  offline=BYTE POINTER(SD_OFFLINE)
  request.io_Flags=request.io_Flags & $fe
  IF offline^<>0 THEN
    bus.state=5
  FI

  IF bus.state=5 THEN
    request.io_Error=EXEC.SIOERR_BUSUNAVAILABLE
  ELSEIF bus.state<>2 OR bus.stop<>0 THEN
    request.io_Error=BYTE(EXEC.IOERR_UNITBUSY)
  ELSE
    EXEC.PutMsg(@bus.port,@request.io_Message)
    RETURN
  FI

  EXEC.ReplyMsg(@request.io_Message)

RETURN

; Distinguish active hardware cancellation from removal of an unclaimed
; request.
PUBLIC PROC AbortIO(EXEC.IORequest POINTER request)
  DriverBus POINTER bus

  IF request.io_Message.mn_Node.ln_Type<>EXEC.NT_MESSAGE THEN
    RETURN
  FI

  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  IF bus.active=request THEN
    bus.cancelled=1
    SIOADAPTER.Cancel()
    RETURN
  FI

  EXECLISTS.Remove(@request.io_Message.mn_Node)
  request.io_Error=BYTE(EXEC.IOERR_ABORTED)
  EXEC.ReplyMsg(@request.io_Message)

RETURN

; Accept cancellation only before the operation crosses its protected SIO
; phase.
PUBLIC BYTE FUNC TryCancel(EXEC.IORequest POINTER request)
  DriverBus POINTER bus
  BYTE POINTER started,phase
  BYTE accepted

  EXEC.Forbid()
  IF Bound(request)=0 THEN
    HEAPCORE.Abort(4)
  FI

  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  started=BYTE POINTER(SD_STARTED)
  phase=BYTE POINTER(SD_PHASE)
  accepted=0
  IF request.io_Message.mn_Node.ln_Type=EXEC.NT_MESSAGE THEN
    IF bus.active<>request OR bus.phase<>2 OR phase^=0 OR started^=0 THEN
      AbortIO(request)
      accepted=1
    FI
  FI

  EXEC.Permit()

RETURN(accepted)

; Take one queued request and establish its worker-owned cancellation state.
EXEC.IORequest POINTER FUNC Claim()
  DriverBus POINTER bus
  EXEC.IORequest POINTER request
  BYTE POINTER cancel,offline

  EXEC.Forbid()
  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  cancel=BYTE POINTER(SD_CANCEL)
  offline=BYTE POINTER(SD_OFFLINE)
  IF offline^<>0 THEN
    bus.state=5
  FI

  IF bus.active<>EXEC.IORequest POINTER(0) THEN
    HEAPCORE.Abort(4)
  FI

  request=EXEC.IORequest POINTER(EXEC.GetMsg(@bus.port))
  bus.active=request
  bus.phase=0
  bus.cancelled=0
  cancel^=0
  IF request<>EXEC.IORequest POINTER(0) THEN
    bus.phase=1
  FI

  EXEC.Permit()

RETURN(request)

; Mark a claimed request active before starting the hardware transaction.
PROC Activate()
  DriverBus POINTER bus
  BYTE POINTER checkpoint
  CARD status
  BYTE pause

  pause=0
  EXEC.Forbid()
  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  IF bus.phase<>1 OR bus.active=EXEC.IORequest POINTER(0) THEN
    HEAPCORE.Abort(4)
  FI

  bus.phase=2
  IF IS_TEST_DEVICE<>0 THEN
    checkpoint=BYTE POINTER(ADDRESS(SIO_STATE+90))
    IF checkpoint^=1 THEN
      checkpoint^=2
      pause=1
    FI
  FI

  EXEC.Permit()
  IF pause<>0 THEN
    status=EXECTASKS.Sleep(1)
  FI

RETURN

; Publish the terminal result and clear worker ownership before replying.
PROC Finish(BYTE hardware)
  DriverBus POINTER bus
  EXEC.IORequest POINTER request
  EXEC.IOSIOReq POINTER sio
  Descriptor POINTER desc

  EXEC.Forbid()
  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  request=bus.active
  IF request=EXEC.IORequest POINTER(0) THEN
    HEAPCORE.Abort(4)
  FI

  sio=EXEC.IOSIOReq POINTER(request)
  desc=Descriptor POINTER(SIO_STATE)
  IF hardware<>0 THEN
    IF bus.phase<>2 THEN
      HEAPCORE.Abort(4)
    FI

    request.io_Error=desc.error
    sio.io_Actual=LONGCARD(desc.actual)
  ELSEIF bus.cancelled<>0 THEN
    request.io_Error=BYTE(EXEC.IOERR_ABORTED)
    sio.io_Actual=0
  FI

  bus.active=EXEC.IORequest POINTER(0)
  bus.phase=0
  bus.cancelled=0
  EXEC.ReplyMsg(@request.io_Message)
  EXEC.Permit()

RETURN
