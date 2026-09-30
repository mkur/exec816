; Driver-owned lifetime. The worker Task, lease and bus remain in the existing
; upper device arena. Waiter records live on retained callers' stacks.
CONST STOP_MASK=$20000000, WAKE_MASK=$e0000000
PROC POINTER noFinal()

; Allow bus reuse only after the previous worker Task has actually been
; removed.
PROC Reap(DriverBus POINTER bus)

  IF bus.state=4 AND bus.worker<>EXEC.Task POINTER(0) THEN
    IF bus.worker.tc_State=EXEC.TS_REMOVED THEN
      bus.worker=EXEC.Task POINTER(0)
      bus.state=0
      bus.stop=0
    FI
  FI

RETURN

; Observe bus lifetime under the same exclusion used by startup and shutdown.
PUBLIC BYTE FUNC State()
  DriverBus POINTER bus
  BYTE state

  EXEC.Forbid()
  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  Reap(bus)
  state=bus.state
  IF state=2 AND bus.stop<>0 THEN
    state=3
  FI

  EXEC.Permit()

RETURN(state)

; Expose the adapter's persistent offline status to filesystem callers.
PUBLIC BYTE FUNC Unavailable()
  BYTE POINTER offline

  offline=BYTE POINTER(SD_OFFLINE)

RETURN(offline^)

; Wake all callers retained for a bus lifetime transition.
PROC Notify(DriverBus POINTER bus)
  DriverWaiter POINTER waiter,next

  waiter=bus.waiters
  bus.waiters=DriverWaiter POINTER(0)
  WHILE waiter<>DriverWaiter POINTER(0) DO
    next=waiter.next
    waiter.next=DriverWaiter POINTER(0)
    EXEC.Signal(waiter.task,waiter.mask)
    waiter=next
  OD

RETURN

; Reserve a private wake signal and keep its waiting Task alive.
BYTE FUNC PrepareWaiter(DriverWaiter POINTER waiter)
  BYTE bit

  bit=EXEC.AllocSignal(-1)
  IF bit=$ff THEN
    RETURN(0)
  FI

  waiter.task=EXEC.FindTask(BYTE POINTER(0))
  waiter.mask=LONGCARD(1) LSH bit
  waiter.bit=bit
  waiter.lease.task=EXEC.Task POINTER(0)
  waiter.lease.incarnation=0
  waiter.lease.identity=0
  IF EXEC.RetainTask(waiter.task,@waiter.lease)=0 THEN
    EXEC.FreeSignal(bit)
    RETURN(0)
  FI

RETURN(1)

; Retire the waiter's signal and Task lease after notification is collected.
PROC FreeWaiter(DriverWaiter POINTER waiter)
  BYTE okay

  EXEC.FreeSignal(waiter.bit)
  okay=EXEC.ReleaseTask(@waiter.lease)
  IF okay=0 THEN
    HEAPCORE.Abort(4)
  FI

RETURN

; Publish the waiter before sleeping so a lifetime transition cannot be
; missed.
PROC WaitChange(DriverBus POINTER bus DriverWaiter POINTER waiter)
  LONGCARD bits

  waiter.next=bus.waiters
  bus.waiters=waiter
  ; Links are complete. Wait releases this Task while preserving its Forbid
  ; nesting, including any exclusion inherited from the Open/Stop caller.
  bits=EXEC.Wait(waiter.mask)

RETURN

; Prepare the bus worker's Task, stack and lease before scheduler admission.
BYTE FUNC AdmitWorker(DriverBus POINTER bus)
  EXEC.Task POINTER item,result
  BYTE POINTER bytes
  BYTE slot,index,okay

  item=EXEC.Task POINTER(ADDRESS(IS_BASE+160))
  bytes=BYTE POINTER(item)
  IF bus.generation=LONGCARD($ffffffff) THEN
    RETURN(0)
  FI

  FOR index=0 TO EXEC.TASK_SIZE-1 DO
    bytes(index)=0
  OD

  item.tc_Node.ln_Type=EXEC.NT_TASK
  item.tc_Node.ln_Name=BYTE POINTER(ADDRESS(IS_BASE+224))
  EXECLISTS.NewList(@item.tc_MemEntry)
  bus.state=1
  bus.stop=0
  bus.worker=item
  bus.active=EXEC.IORequest POINTER(0)
  bus.phase=0
  bus.cancelled=0
  EXECLISTS.NewList(@bus.port.mp_MsgList)
  bus.port.mp_Node.ln_Type=EXEC.NT_MSGPORT
  bus.port.mp_Flags=EXEC.PA_SIGNAL
  bus.port.mp_SigBit=31
  bus.port.mp_SigTask=item
  result=EXEC.Task POINTER(0)
  FOR slot=1 TO TASKSTACKS.CAPACITY-1 DO
    item.tc_SPLower=ADDRESS(TASKSTACKS.StackLower(slot))
    item.tc_SPUpper=ADDRESS(TASKSTACKS.StackUpper(slot))
    item.tc_SPReg=item.tc_SPUpper-SIZE(2)
    result=EXEC.AddTask(item,@Worker,noFinal)
    IF result<>EXEC.Task POINTER(0) THEN
      EXIT
    FI
  OD

  IF result=EXEC.Task POINTER(0) THEN
    bus.worker=EXEC.Task POINTER(0)
    bus.state=0
    RETURN(0)
  FI

  IF EXEC.RetainTask(item,@bus.lease)=0 THEN
    EXEC.RemTask(item)
    bus.worker=EXEC.Task POINTER(0)
    bus.state=0
    RETURN(0)
  FI

  bus.generation==+1

RETURN(1)

; Start or join bus initialization without publishing a partially ready
; worker.
PUBLIC BYTE FUNC Start()
  DriverBus POINTER bus
  DriverWaiter waiter
  LONGCARD generation
  BYTE okay

  EXEC.Forbid()
  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  Reap(bus)
  IF bus.state=2 AND bus.stop=0 THEN
    EXEC.Permit()
    RETURN(1)
  FI

  IF (bus.state<>0 AND bus.state<>1) OR bus.stop<>0 THEN
    EXEC.Permit()
    RETURN(0)
  FI

  IF PrepareWaiter(@waiter)=0 THEN
    EXEC.Permit()
    RETURN(0)
  FI

  okay=1
  IF bus.state=0 THEN
    okay=AdmitWorker(bus)
  FI

  IF okay<>0 THEN
    generation=bus.generation
    WHILE bus.state=1 AND bus.generation=generation DO
      WaitChange(bus,@waiter)
    OD

    Reap(bus)
    okay=bus.state=2 AND bus.stop=0 AND bus.generation=generation
  FI

  FreeWaiter(@waiter)
  EXEC.Permit()

RETURN(okay)

; Request shutdown and wait until retained bus ownership has settled.
PUBLIC PROC Stop()
  DriverBus POINTER bus
  DriverWaiter waiter
  LONGCARD generation

  EXEC.Forbid()
  bus=DriverBus POINTER(ADDRESS(IS_BASE+64))
  Reap(bus)
  IF bus.state=0 THEN
    EXEC.Permit()
    RETURN
  FI

  IF bus.opens<>0 OR bus.active<>EXEC.IORequest POINTER(0)
      OR EXECLISTS.IsListEmpty(@bus.port.mp_MsgList)=0 THEN
    HEAPCORE.Abort(4)
  FI

  IF PrepareWaiter(@waiter)=0 THEN
    HEAPCORE.Abort(4)
  FI

  generation=bus.generation
  bus.stop=1
  ; Starting workers publish readiness before observing the stop flag.
  IF bus.state<>1 THEN
    bus.state=3
  FI

  EXEC.Signal(bus.worker,LONGCARD(STOP_MASK))
  DO
    WaitChange(bus,@waiter)
    Reap(bus)
  UNTIL bus.state=0 OR bus.generation<>generation
  OD

  FreeWaiter(@waiter)
  EXEC.Permit()

RETURN

; Check shutdown readiness while protecting worker and request ownership.
BYTE FUNC Stopping(DriverBus POINTER bus EXEC.Task POINTER self LONGCARD received)
  LONGCARD bits
  BYTE stopped

  EXEC.Forbid()
  IF ((self.tc_SigRecvd OR received) & LONGCARD(STOP_MASK))<>0 THEN
    bits=EXEC.SetSignal(0,LONGCARD(STOP_MASK))
    bus.stop=1
  FI

  stopped=bus.stop<>0 AND bus.opens=0 AND bus.active=EXEC.IORequest POINTER(0)
      AND EXECLISTS.IsListEmpty(@bus.port.mp_MsgList)<>0
  IF stopped<>0 THEN
    bus.state=3
  FI

  EXEC.Permit()

RETURN(stopped)

; Publish terminal bus state and notify retained lifetime waiters.
PROC RetireWorker(DriverBus POINTER bus)
  BYTE okay

  bus.state=4
  Notify(bus)
  okay=EXEC.ReleaseTask(@bus.lease)
  IF okay=0 THEN
    HEAPCORE.Abort(4)
  FI

  ; Still under Forbid: no observer can run between final lease release and
  ; actual Task removal. Notification recipients resume after removal.
  EXEC.RemTask(EXEC.Task POINTER(0))
  HEAPCORE.Abort(4)

RETURN
