; Waiters keep their caller and stack alive while startup or retirement runs.
TYPE ConsoleWaiter=[
  ConsoleWaiter POINTER next
  EXEC.Task POINTER task
  LONGCARD mask
  EXEC.TaskLease lease
  BYTE bit
]

PROC POINTER noFinal()
CONST STOP_MASK=$20000000, LAST_GENERATION=$ffff

; Observe startup or shutdown while serializing with worker state changes.
PUBLIC BYTE FUNC State()

  EXEC.Forbid()
  LET service=GetService()
  LET state=service.state
  EXEC.Permit()

RETURN(state)

; Wake callers waiting for the next service lifetime transition.
PROC Notify(CONSOLETYPES.Service POINTER service)
  ConsoleWaiter POINTER waiter,next

  waiter=ConsoleWaiter POINTER(service.waiters)
  service.waiters=NULL
  WHILE waiter<>NULL DO
    next=waiter.next
    waiter.next=NULL
    EXEC.Signal(waiter.task,waiter.mask)
    waiter=next
  OD

RETURN

; Keep a waiting caller and its private wake signal alive together.
BYTE FUNC PrepareWaiter(ConsoleWaiter POINTER waiter)

  LET bit=EXEC.AllocSignal(-1)
  IF bit=$ff THEN
    RETURN(0)
  FI

  waiter.task=EXEC.FindTask(NULL)
  waiter.mask=LONGCARD(1) LSH bit
  waiter.bit=bit
  waiter.lease.task=NULL
  waiter.lease.incarnation=0
  waiter.lease.identity=0
  IF EXEC.RetainTask(waiter.task,@waiter.lease)=0 THEN
    EXEC.FreeSignal(bit)
    RETURN(0)
  FI

RETURN(1)

; Release the signal and Task lease after the wait has ended.
PROC FreeWaiter(ConsoleWaiter POINTER waiter)

  EXEC.FreeSignal(waiter.bit)
  IF EXEC.ReleaseTask(@waiter.lease)=0 THEN
    HEAPCORE.Abort(4)
  FI

RETURN

; Sleep on a published waiter without opening a lost-wakeup window.
PROC WaitChange(CONSOLETYPES.Service POINTER service ConsoleWaiter POINTER waiter)
  LONGCARD bits

  waiter.next=ConsoleWaiter POINTER(service.waiters)
  service.waiters=BYTE POINTER(waiter)
  ; Wait preserves caller Forbid nesting; a signal posted before it is durable.
  bits=EXEC.Wait(waiter.mask)

RETURN

; Prepare and retain the console Task before making it schedulable.
BYTE FUNC AdmitWorker(CONSOLETYPES.Service POINTER service)
  EXEC.Task POINTER added
  BYTE slot

  IF service.generation=LAST_GENERATION THEN
    RETURN(0)
  FI

  LET item=@service.task
  LET instance=GetInstance()
  A816MEMORY.Clear(BYTE POINTER(item),SIZE(EXEC.TASK_SIZE))
  item.tc_Node.ln_Type=EXEC.NT_TASK
  item.tc_Node.ln_Name=@service.name(0)
  EXECLISTS.NewList(@item.tc_MemEntry)
  service.state=1
  service.stop=0
  service.error=0
  service.worker=BYTE POINTER(item)
  service.instance=BYTE POINTER(instance)
  EXECLISTS.NewList(@service.port.mp_MsgList)
  service.port.mp_Node.ln_Type=EXEC.NT_MSGPORT
  service.port.mp_Flags=EXEC.PA_SIGNAL
  service.port.mp_SigBit=31
  service.port.mp_SigTask=item
  EXECLISTS.NewMinList(@instance.writes)

  added=NULL
  FOR slot=1 TO TASKSTACKS.CAPACITY-1 DO
    IF CONSOLEBITMAP.Enabled()=0 OR
        TASKSTACKS.StackUpper(slot)-TASKSTACKS.StackLower(slot)>=2560 THEN
      item.tc_SPLower=ADDRESS(TASKSTACKS.StackLower(slot))
      item.tc_SPUpper=ADDRESS(TASKSTACKS.StackUpper(slot))
      item.tc_SPReg=item.tc_SPUpper-SIZE(2)
      added=EXEC.AddTask(item,@Worker,noFinal)
      IF added<>NULL THEN
        EXIT
      FI
    FI
  OD

  IF added=NULL THEN
    service.worker=NULL
    service.state=0
    RETURN(0)
  FI

  IF EXEC.RetainTask(item,@service.lease)=0 THEN
    EXEC.RemTask(item)
    service.worker=NULL
    service.state=0
    RETURN(0)
  FI

  service.generation==+1

RETURN(1)

; Start the console worker or join an already pending startup.
PUBLIC BYTE FUNC Start()
  ConsoleWaiter waiter
  BYTE okay
  CARD generation

  EXEC.Forbid()
  LET service=GetService()
  IF service.state=2 AND service.stop=0 THEN
    okay=CONSOLEBITMAP.Failed()=0
    EXEC.Permit()
    RETURN(okay)
  FI

  IF (service.state<>0 AND service.state<>1) OR service.stop<>0 THEN
    EXEC.Permit()
    RETURN(0)
  FI

  IF PrepareWaiter(@waiter)=0 THEN
    EXEC.Permit()
    RETURN(0)
  FI

  okay=1
  IF service.state=0 THEN
    okay=AdmitWorker(service)
  FI

  IF okay<>0 THEN
    generation=service.generation
    WHILE service.state=1 AND service.generation=generation DO
      WaitChange(service,@waiter)
    OD

    okay=service.state=2 AND service.stop=0 AND service.generation=generation
  FI

  FreeWaiter(@waiter)
  EXEC.Permit()

RETURN(okay)

; Require all endpoint activity to settle before accepting service shutdown.
BYTE FUNC AllIdle(CONSOLETYPES.Service POINTER service)
  BYTE index
  CONSOLETYPES.Instance POINTER instance

  LET windows=CONSOLEWINDOWS.Registry()
  IF windows.presenting<>0 THEN
    RETURN(0)
  FI

  FOR index=0 TO CONSOLETYPES.WINDOW_SLOTS-1 DO
    IF windows.items(index).state<>CONSOLETYPES.WIN_FREE THEN
      IF index<>0 THEN
        RETURN(0)
      FI

      instance=CONSOLETYPES.Instance POINTER(windows.items(index).instance)
      IF instance.open<>0 OR Idle(service,instance)=0 THEN
        RETURN(0)
      FI
    FI
  OD

RETURN(1)

; Refuse shutdown while live console ownership still needs the worker.
BYTE FUNC RequestStop(CONSOLETYPES.Service POINTER service)

  IF AllIdle(service)=0 THEN
    RETURN(0)
  FI

  IF service.worker<>NULL THEN
    service.stop=1
    IF service.state<>1 THEN
      service.state=3
    FI

    EXEC.Signal(@service.task,STOP_MASK)
  FI

RETURN(1)

; Wait for worker shutdown while preserving each waiting caller's lifetime.
PUBLIC BYTE FUNC Stop()
  ConsoleWaiter waiter
  CARD generation

  EXEC.Forbid()
  LET service=GetService()
  IF service.state=0 THEN
    EXEC.Permit()
    RETURN(1)
  FI

  IF AllIdle(service)=0 OR PrepareWaiter(@waiter)=0 THEN
    EXEC.Permit()
    RETURN(0)
  FI

  generation=service.generation
  LET accepted=RequestStop(service)
  WHILE service.state<>0 AND service.generation=generation DO
    WaitChange(service,@waiter)
  OD

  FreeWaiter(@waiter)
  EXEC.Permit()

RETURN(accepted)

; Caller holds Forbid: publication, notification, final release and removal
; are indivisible to Tasks. Waiters resume only after actual removal.
PROC RetireWorker(CONSOLETYPES.Service POINTER service)

  service.state=0
  service.stop=0
  service.worker=NULL
  Notify(service)
  IF EXEC.ReleaseTask(@service.lease)=0 THEN
    HEAPCORE.Abort(4)
  FI

  EXEC.RemTask(NULL)
  HEAPCORE.Abort(4)

RETURN
