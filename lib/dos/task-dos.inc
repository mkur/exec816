; The current private context indexes DOS state directly. No task-list scan,
; public Task field, bank-zero cell or IRQ-side DOS operation is introduced.
INCLUDE "program-kernel.inc"

TYPE DosSlot=[
  BYTE POINTER context
  Task POINTER owner
  LONGINT error
  BYTE active
  BYTE POINTER objects
]

DosSlot POINTER FUNC DosSlotFor(TaskControl POINTER ctx)

RETURN(DosSlot POINTER(ADDRESS(DS_BASE)+(SIZE(ctx.id) LSH 4)))

; Clear a Task slot's DOS identity before it can be reused.
PROC DosReset(TaskControl POINTER ctx Task POINTER owner)
  DosSlot POINTER slot

  slot=DosSlotFor(ctx)
  slot.context=BYTE POINTER(0)
  slot.owner=owner
  slot.error=0
  slot.active=0
  slot.objects=BYTE POINTER(0)

RETURN

; Prevent Task removal while DOS resources still retain its lifetime.
BYTE FUNC DosCanRemove(TaskControl POINTER ctx)
  DosSlot POINTER slot

  slot=DosSlotFor(ctx)
  IF slot.owner<>ctx.item THEN
    RETURN(0)
  FI

RETURN(slot.active=0 AND slot.context=BYTE POINTER(0)
    AND slot.objects=BYTE POINTER(0))

; Expose only the DOS slot owned by the admitted caller.
CARD FUNC DosCurrent(TaskControl POINTER ctx CARD saved)
  DosSlot POINTER slot

  IF ctx.id>=T_CAPACITY THEN
    RETURN(T_FAULT)
  FI

  slot=DosSlotFor(ctx)
  IF slot.owner<>ctx.item THEN
    RETURN(T_FAULT)
  FI

  PointerResult(saved,Task POINTER(slot))

RETURN(saved)

INCLUDE "dos-registry-types.inc"

TYPE DosControlArgs=[
  BYTE operation
  BYTE POINTER argument
]

; Initialize the fixed DOS registry and per-Task ownership slots.
PROC DosInit()
  DosRegistry POINTER registry
  BYTE POINTER bytes,boot
  BYTE index

  registry=DosRegistry POINTER(ADDRESS(DS_SHARED))
  bytes=BYTE POINTER(registry)
  FOR index=0 TO DS_SERVICE_BYTES-1 DO
    bytes(index)=0
  OD

  bytes=BYTE POINTER(ADDRESS(DS_STREAMS))
  FOR index=0 TO DS_STREAM_BYTES-1 DO
    bytes(index)=0
  OD

  boot=BYTE POINTER(ADDRESS(T_BASE+$880))
  registry.entry=ADDRESS(LONGCARD(boot(0))+(LONGCARD(boot(1)) LSH 8)+(LONGCARD(
      boot(2)) LSH 16))
  registry.count=boot(3)
  registry.config=ADDRESS(T_BASE+$900)

RETURN

; Identify the Task retained as the filesystem worker.
BYTE FUNC DosWorkerBound(TaskControl POINTER ctx)
  DosRegistry POINTER registry

  registry=DosRegistry POINTER(ADDRESS(DS_SHARED))

RETURN(registry.worker=BYTE POINTER(ctx) AND registry.state<>4
    AND registry.state<>5)

; Retire DOS slot state when its owning Task leaves the scheduler.
PROC DosRemoved(TaskControl POINTER ctx)
  DosRegistry POINTER registry

  registry=DosRegistry POINTER(ADDRESS(DS_SHARED))
  IF registry.worker=BYTE POINTER(ctx) THEN
    registry.worker=BYTE POINTER(0)
  FI

RETURN

; Prepare a DOS context admission request without publishing it prematurely.
Task POINTER FUNC DosPrepare(TaskControl POINTER ctx DosRegistry POINTER registry)
  Task POINTER worker
  BYTE POINTER bytes
  BYTE index

  bytes=registry.task
  worker=Task POINTER(bytes)
  FOR index=0 TO T_TASK_SIZE-1 DO
    bytes(index)=0
  OD

  worker.tc_Node.ln_Type=T_NT_TASK
  worker.tc_SPLower=ADDRESS(poolStack(ctx.id))
  worker.tc_SPUpper=ADDRESS(ctx.stackTop+2)
  worker.tc_SPReg=ADDRESS(ctx.stackTop)
  EXECLISTS.NewList(@worker.tc_MemEntry)

RETURN(worker)

; Bind prepared DOS ownership to the validated Task incarnation.
Task POINTER FUNC DosAdmit(ADDRESS entry)
  DosRegistry POINTER registry
  TaskControl POINTER ctx
  Task POINTER worker
  BYTE id

  registry=DosRegistry POINTER(ADDRESS(DS_SHARED))
  IF registry.entry=0 OR registry.entry<>entry
      OR registry.worker<>BYTE POINTER(0) THEN
    RETURN(Task POINTER(0))
  FI

  ctx=TaskControl POINTER(0)
  FOR id=1 TO T_CAPACITY-1 DO
    ctx=RecordFor(id)
    IF SlotFree(id)<>0 THEN
      EXIT
    FI

    ctx=TaskControl POINTER(0)
  OD

  IF ctx=TaskControl POINTER(0) THEN
    RETURN(Task POINTER(0))
  FI

  worker=DosPrepare(ctx,registry)
  registry.worker=BYTE POINTER(ctx)
  registry.state=1
  registry.stop=0
  Admit(ctx,worker,entry,0)

RETURN(worker)

; Dispatch DOS ownership operations at the kernel boundary.
CARD FUNC DosControl(TaskControl POINTER caller CARD saved)
  DosControlArgs POINTER args

  args=DosControlArgs POINTER(ArgumentPointer(saved))
  IF args.operation>=PROCESSSTATE.OP_RESERVE
      AND args.operation<=PROCESSSTATE.OP_PREPARED THEN
    RETURN(ProcessControl(caller,saved,args))
  FI

  IF args.operation=1 THEN
    PointerResult(saved,DosAdmit(ADDRESS(args.argument)))
    caller.pending=1
    RETURN(saved)
  FI

  IF args.operation=PROGRAM_PROVIDER_OPERATION THEN
    PointerResult(saved,Task POINTER(ADDRESS(T_BASE+PROGRAM_PROVIDER_OFFSET)))
    RETURN(saved)
  FI

RETURN(T_FAULT)
