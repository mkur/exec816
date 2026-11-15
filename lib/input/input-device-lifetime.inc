; All rendezvous storage belongs to a live waiting caller and its retained Task.
TYPE StartWaiter=[
  StartWaiter POINTER next
  EXEC.Task POINTER task
  LONGCARD mask
  EXEC.TaskLease owner
  BYTE bit,queued
]

PROC Notify(STATE.Service POINTER service)
  StartWaiter POINTER waiter,next

  waiter=StartWaiter POINTER(service.waiters)
  service.waiters=NULL
  WHILE waiter<>NULL DO
    next=waiter.next
    waiter.next=NULL
    waiter.queued=0
    EXEC.Signal(waiter.task,waiter.mask)
    waiter=next
  OD

RETURN

BYTE FUNC PrepareWaiter(StartWaiter POINTER waiter)

  waiter.bit=EXEC.AllocSignal(-1)
  IF waiter.bit=$ff THEN
    RETURN(0)
  FI
  waiter.task=EXEC.FindTask(NULL)
  waiter.queued=0
  waiter.mask=LONGCARD(1) LSH waiter.bit
  waiter.owner.task=NULL
  waiter.owner.incarnation=0
  waiter.owner.identity=0
  IF EXEC.RetainTask(waiter.task,@waiter.owner)=0 THEN
    EXEC.FreeSignal(waiter.bit)
    RETURN(0)
  FI

RETURN(1)

PROC FreeWaiter(StartWaiter POINTER waiter)

  EXEC.FreeSignal(waiter.bit)
  IF EXEC.ReleaseTask(@waiter.owner)=0 THEN
    HEAPCORE.Abort($fca1)
  FI

RETURN

PROC WaitChange(STATE.Service POINTER service StartWaiter POINTER waiter)

  IF waiter.queued=0 THEN
    waiter.next=StartWaiter POINTER(service.waiters)
    service.waiters=BYTE POINTER(waiter)
    waiter.queued=1
  FI
  EXEC.Wait(waiter.mask)

RETURN

; Start only when the boot/controller selects this input owner. Open/query alone
; does not start a second production owner alongside the old console worker.
PUBLIC BYTE FUNC Start()
  StartWaiter waiter
  EXEC.Task POINTER created
  BYTE okay

  LET service=STATE.Get()
  IF SIZEOF(STATE.Binding)<>INPUTDEVICE.BINDING_BYTES
      OR SIZEOF(STATE.Source)<>INPUTDEVICE.SOURCE_BYTES
      OR SIZEOF(STATE.Service)>224 THEN
    RETURN(0)
  FI
  IF service.state=INPUTDEVICE.RUNNING THEN
    RETURN(service.stopping=0)
  FI
  IF PrepareWaiter(@waiter)=0 THEN
    RETURN(0)
  FI
  EXEC.Forbid()
  IF service.state=INPUTDEVICE.STOPPED THEN
    service.stopping=0
    service.error=0
    service.state=INPUTDEVICE.STARTING
    created=EXEC.CreateTask(c"input.device",0,@Worker,1312)
    IF created<>NULL THEN
      IF EXEC.RetainTask(created,@service.workerLease)=0 THEN
        EXEC.RemTask(created)
        created=NULL
      FI
    FI
    IF created=NULL THEN
      service.state=INPUTDEVICE.STOPPED
      service.error=CARD(EXEC.IOERR_OPENFAIL)
    FI
  FI
  WHILE service.state=INPUTDEVICE.STARTING DO
    WaitChange(service,@waiter)
  OD
  okay=service.state=INPUTDEVICE.RUNNING
  EXEC.Permit()
  FreeWaiter(@waiter)

RETURN(okay)

; Live opens and unfinished controls keep their owner alive; Stop never steals.
PUBLIC BYTE FUNC Stop()
  StartWaiter waiter
  BYTE okay

  LET service=STATE.Get()
  IF service.state=INPUTDEVICE.STOPPED THEN
    RETURN(1)
  FI
  IF PrepareWaiter(@waiter)=0 THEN
    RETURN(0)
  FI
  EXEC.Forbid()
  okay=service.opens=0 AND service.active=NULL
  IF okay<>0 AND service.state<>INPUTDEVICE.STOPPED THEN
    service.stopping=1
    EXEC.Signal(service.workerLease.task,INPUTDEVICE.STOP_MASK)
    WHILE service.state<>INPUTDEVICE.STOPPED DO
      WaitChange(service,@waiter)
    OD
  FI
  EXEC.Permit()
  FreeWaiter(@waiter)

RETURN(okay)
