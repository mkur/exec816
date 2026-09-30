; All Process publication and lease changes run inside the existing guarded
; kernel activation. IRQ/NMI paths never inspect this table.
TYPE ProcessAdmission=[
  LONGINT FUNC POINTER entry()
  PROC POINTER trampoline(),finalizer()
]

; Resolve a process record against its owning Task incarnation.
PROCESSSTATE.Entry POINTER FUNC ProcessFor(BYTE id)
  PROCESSSTATE.Table POINTER table

  table=PROCESSSTATE.Registry()

RETURN(@table.entries(id))

; Require all process ownership to retire before reusing its slot.
BYTE FUNC SlotFree(BYTE id)
  TaskControl POINTER ctx
  PROCESSSTATE.Entry POINTER process

  ctx=RecordFor(id)
  process=ProcessFor(id)

RETURN(ctx.state=T_STATE_FREE AND ctx.incarnation<>LONGCARD($ffffffff)
    AND process.state=PROCESSSTATE.STATE_FREE)

; Reset a retired process slot without retaining stale identities.
PROC ProcessClear(PROCESSSTATE.Entry POINTER process)
  BYTE POINTER bytes
  CARD index

  bytes=BYTE POINTER(process)
  FOR index=0 TO PROCESSSTATE.RECORD_BYTES-1 DO
    bytes(index)=0
  OD

RETURN

; Initialize the fixed process record pool.
PROC ProcessInit()
  BYTE id
  PROCESSSTATE.Table POINTER table

  table=PROCESSSTATE.Registry()
  table.nextIdentity=0
  FOR id=0 TO T_CAPACITY-1 DO
    ProcessClear(ProcessFor(id))
  OD

RETURN

; Check capacity before admitting another process lifetime.
BYTE FUNC ProcessRecordAvailable(Task POINTER item)
  ADDRESS first,last,startAddress

  first=ADDRESS(ProcessFor(0))
  last=first+(SIZE(T_CAPACITY) LSH 7)
  startAddress=ADDRESS(item)

RETURN(startAddress>=last OR startAddress+SIZE(T_TASK_SIZE)<=first)

; Validate a resident process entry against the supported execution domain.
ADDRESS FUNC ProcessResident(BYTE offset)
  BYTE POINTER bytes

  bytes=BYTE POINTER(ADDRESS(T_BASE+$880)+SIZE(offset))

RETURN(ADDRESS(LONGCARD(bytes(0))+(LONGCARD(bytes(1)) LSH 8)+(LONGCARD(bytes(
    2)) LSH 16)))

; Reject an entry that cannot be launched through the current native ABI.
BYTE FUNC ValidProcessEntry(ADDRESS entry)
  BYTE POINTER descriptor
  BYTE index,count

  descriptor=BYTE POINTER(ADDRESS(T_BASE+$880))
  count=descriptor(PROCESSSTATE.RESIDENT_COUNT_OFFSET)
  IF count>PROCESSSTATE.RESIDENT_CAPACITY THEN
    RETURN(0)
  FI

  index=0
  WHILE index<count DO
    IF ProcessResident(PROCESSSTATE.RESIDENT_ENTRIES_OFFSET+index*3)=entry THEN
      RETURN(1)
    FI

    index==+1
  OD

RETURN(0)

; Reserve a process identity before making its Task runnable.
PROCESSSTATE.Entry POINTER FUNC ProcessReserve(TaskControl POINTER caller
    ProcessAdmission POINTER admission)
  PROCESSSTATE.Entry POINTER process
  DosSlot POINTER owner
  PROCESSSTATE.Table POINTER table
  BYTE id

  owner=DosSlotFor(caller)
  table=PROCESSSTATE.Registry()
  owner.error=DOS_ERROR_BAD_NUMBER
  IF ValidProcessEntry(ADDRESS(admission.entry))=0 THEN
    RETURN(PROCESSSTATE.Entry POINTER(0))
  FI

  IF ADDRESS(admission.trampoline)=0
      OR ADDRESS(admission.trampoline)<>ProcessResident(8) THEN
    RETURN(PROCESSSTATE.Entry POINTER(0))
  FI

  IF ADDRESS(admission.finalizer)=0
      OR ADDRESS(admission.finalizer)<>ProcessResident(11) THEN
    RETURN(PROCESSSTATE.Entry POINTER(0))
  FI

  IF ADDRESS(admission.entry)=ADDRESS(admission.trampoline)
      OR ADDRESS(admission.entry)=ADDRESS(admission.finalizer) THEN
    RETURN(PROCESSSTATE.Entry POINTER(0))
  FI

  IF ValidEntry(ADDRESS(admission.trampoline))=0
      OR ValidEntry(ADDRESS(admission.finalizer))=0 THEN
    RETURN(PROCESSSTATE.Entry POINTER(0))
  FI

  owner.error=DOS_ERROR_NO_FREE_STORE
  IF table.nextIdentity=LONGCARD($ffffffff) THEN
    RETURN(PROCESSSTATE.Entry POINTER(0))
  FI

  FOR id=1 TO T_CAPACITY-1 DO
    IF SlotFree(id)<>0 THEN
      process=ProcessFor(id)
      ProcessClear(process)
      table.nextIdentity==+1
      process.identity=table.nextIdentity
      process.owner=BYTE POINTER(caller.item)
      process.entry=admission.entry
      process.trampoline=admission.trampoline
      process.finalizer=admission.finalizer
      process.signalBit=$ff
      process.slot=id
      process.state=PROCESSSTATE.STATE_PREPARING
      owner.error=0
      RETURN(process)
    FI
  OD

RETURN(PROCESSSTATE.Entry POINTER(0))

; Require the caller's ownership before exposing a child process record.
PROCESSSTATE.Entry POINTER FUNC ProcessOwned(TaskControl POINTER caller BYTE
    POINTER identity)
  BYTE id
  PROCESSSTATE.Entry POINTER process

  FOR id=1 TO T_CAPACITY-1 DO
    process=ProcessFor(id)
    IF BYTE POINTER(process)=identity
        AND process.owner=BYTE POINTER(caller.item)
        AND process.state<>PROCESSSTATE.STATE_FREE THEN
      RETURN(process)
    FI
  OD

RETURN(PROCESSSTATE.Entry POINTER(0))

; Find a process by its public identity without accepting a reused slot.
PROCESSSTATE.Entry POINTER FUNC ProcessFind(TaskControl POINTER caller
    LONGCARD identity)
  BYTE id
  PROCESSSTATE.Entry POINTER process

  FOR id=1 TO T_CAPACITY-1 DO
    process=ProcessFor(id)
    IF process.identity=identity AND identity<>0
        AND process.owner=BYTE POINTER(caller.item)
        AND process.state<>PROCESSSTATE.STATE_FREE THEN
      RETURN(process)
    FI
  OD

RETURN(PROCESSSTATE.Entry POINTER(0))

; Return the process associated with the current Task.
PROCESSSTATE.Entry POINTER FUNC ProcessCurrent(TaskControl POINTER caller)
  PROCESSSTATE.Entry POINTER process

  process=ProcessFor(caller.id)
  IF BYTE POINTER(caller.item)<>@process.task(0) THEN
    RETURN(PROCESSSTATE.Entry POINTER(0))
  FI

  IF process.state<>PROCESSSTATE.STATE_RUNNING
      AND process.state<>PROCESSSTATE.STATE_QUIESCING THEN
    RETURN(PROCESSSTATE.Entry POINTER(0))
  FI

RETURN(process)

; Transfer a prepared process into scheduler ownership.
BYTE FUNC ProcessLaunch(TaskControl POINTER caller PROCESSSTATE.Entry
    POINTER process)
  TaskControl POINTER ctx
  Task POINTER item

  ctx=RecordFor(process.slot)
  IF process.state<>PROCESSSTATE.STATE_PREPARING OR ctx.state<>T_STATE_FREE THEN
    RETURN(0)
  FI

  IF ADDRESS(process.entry)=ProcessResident(14) THEN
    IF process.image=BYTE POINTER(0) THEN
      RETURN(0)
    FI
  ELSEIF process.image<>BYTE POINTER(0) THEN
    RETURN(0)
  FI

  IF process.arguments=BYTE POINTER(0) OR process.length>255
      OR process.signalBit<T_USER_SIGNAL_FIRST
      OR process.signalBit>=T_SIGNAL_COUNT THEN
    RETURN(0)
  FI

  IF process.mask<>SignalBit(process.signalBit)
      OR (caller.item.tc_SigAlloc & process.mask)=0 THEN
    RETURN(0)
  FI

  item=Task POINTER(@process.task(0))
  IF Writable(ADDRESS(item),SIZE(T_TASK_SIZE))=0 THEN
    RETURN(0)
  FI

  item.tc_Node.ln_Type=T_NT_TASK
  item.tc_SPLower=ADDRESS(poolStack(ctx.id))
  item.tc_SPUpper=ADDRESS(poolStack(ctx.id)+poolSize(ctx.id))
  item.tc_SPReg=item.tc_SPUpper-SIZE(2)
  EXECLISTS.NewList(@item.tc_MemEntry)
  process.state=PROCESSSTATE.STATE_RUNNING
  Admit(ctx,item,ADDRESS(process.trampoline),ADDRESS(process.finalizer))
  caller.pending=1

RETURN(1)

; Keep the Task alive while process state still needs its context.
BYTE FUNC ProcessCanRemove(TaskControl POINTER caller,target)
  BYTE id
  PROCESSSTATE.Entry POINTER process
  ; A parent owns completion records until collection, including preparation
  ; failures still rolling back. Its Task identity must remain valid.
  FOR id=1 TO T_CAPACITY-1 DO
    process=ProcessFor(id)
    IF process.state<>PROCESSSTATE.STATE_FREE
        AND process.owner=BYTE POINTER(target.item) THEN
      RETURN(0)
    FI
  OD

  process=ProcessFor(target.id)
  IF process.state=PROCESSSTATE.STATE_FREE THEN
    RETURN(1)
  FI

RETURN(target=caller AND process.state=PROCESSSTATE.STATE_QUIESCING
    AND process.retireReady<>0 AND @process.task(0)=BYTE POINTER(target.item))

; Publish process retirement when its Task is removed.
PROC ProcessRemoved(TaskControl POINTER target)
  PROCESSSTATE.Entry POINTER process
  TaskControl POINTER parent
  BYTE posted

  process=ProcessFor(target.id)
  IF process.state=PROCESSSTATE.STATE_FREE THEN
    RETURN
  FI

  parent=Lookup(Task POINTER(process.owner))
  process.state=PROCESSSTATE.STATE_RETIRED
  ; Removal has cleared the Task/context binding. Execution is on the kernel
  ; stack; the child can never resume. The lease lasts through collection.
  posted=PostSignal(parent,process.mask)

RETURN

BYTE FUNC ProcessStorageEmpty(PROCESSSTATE.Entry POINTER process)

RETURN(process.arguments=BYTE POINTER(0) AND process.mask=0
    AND process.input=BYTE POINTER(0) AND
      process.output=BYTE POINTER(0) AND process.directory=BYTE POINTER(0)
          AND process.console=BYTE POINTER(0) AND
      process.parentClient=BYTE POINTER(0)
          AND process.parentScope=BYTE POINTER(0) AND process.foreground=0 AND
      process.image=BYTE POINTER(0) AND process.groupScope=BYTE POINTER(0))

; Apply an authorized process lifetime transition.
PROCESSSTATE.Entry POINTER FUNC ProcessChange(TaskControl POINTER caller
    BYTE operation BYTE POINTER argument)
  PROCESSSTATE.Entry POINTER process
  LONGCARD POINTER identity
  DosSlot POINTER owner

  owner=DosSlotFor(caller)
  IF operation=PROCESSSTATE.OP_CURRENT THEN
    RETURN(ProcessCurrent(caller))
  FI

  owner.error=305
  IF operation=PROCESSSTATE.OP_RESERVE THEN
    RETURN(ProcessReserve(caller,ProcessAdmission POINTER(argument)))
  FI

  IF operation=PROCESSSTATE.OP_FIND OR operation=PROCESSSTATE.OP_CLAIM
      OR operation=PROCESSSTATE.OP_PREPARED THEN
    identity=LONGCARD POINTER(argument)
    process=ProcessFind(caller,identity^)
  ELSE
    process=ProcessOwned(caller,argument)
    IF operation=PROCESSSTATE.OP_QUIESCE
        OR operation=PROCESSSTATE.OP_RETIRE_READY THEN
      process=ProcessCurrent(caller)
      IF BYTE POINTER(process)<>argument THEN
        RETURN(PROCESSSTATE.Entry POINTER(0))
      FI
    FI
  FI

  IF process=PROCESSSTATE.Entry POINTER(0) THEN
    RETURN(process)
  FI

  owner.error=DOS_ERROR_OBJECT_IN_USE
  CASE operation OF
  WHEN PROCESSSTATE.OP_LAUNCH THEN
    IF ProcessLaunch(caller,process)=0 THEN
      RETURN(PROCESSSTATE.Entry POINTER(0))
    FI
  WHEN PROCESSSTATE.OP_ROLLBACK THEN
    IF process.state<>PROCESSSTATE.STATE_PREPARING
        OR ProcessStorageEmpty(process)=0 THEN
      RETURN(PROCESSSTATE.Entry POINTER(0))
    FI

    ProcessClear(process)
  WHEN PROCESSSTATE.OP_PREPARED THEN
    IF process.state<>PROCESSSTATE.STATE_PREPARING THEN
      RETURN(PROCESSSTATE.Entry POINTER(0))
    FI
  WHEN PROCESSSTATE.OP_FIND THEN
    IF process.state<>PROCESSSTATE.STATE_RUNNING
        AND process.state<>PROCESSSTATE.STATE_QUIESCING
        AND process.state<>PROCESSSTATE.STATE_RETIRED THEN
      RETURN(PROCESSSTATE.Entry POINTER(0))
    FI
  WHEN PROCESSSTATE.OP_QUIESCE THEN
    IF process.state<>PROCESSSTATE.STATE_RUNNING THEN
      RETURN(PROCESSSTATE.Entry POINTER(0))
    FI

    process.state=PROCESSSTATE.STATE_QUIESCING
  WHEN PROCESSSTATE.OP_RETIRE_READY THEN
    IF process.state<>PROCESSSTATE.STATE_QUIESCING OR DosCanRemove(caller)=0
        OR process.input<>BYTE POINTER(0) OR process.output<>BYTE POINTER(0)
        OR process.directory<>BYTE POINTER(0)
        OR process.console<>BYTE POINTER(0) THEN
      RETURN(PROCESSSTATE.Entry POINTER(0))
    FI

    process.retireReady=1
  WHEN PROCESSSTATE.OP_CLAIM THEN
    IF process.state<>PROCESSSTATE.STATE_RETIRED THEN
      RETURN(PROCESSSTATE.Entry POINTER(0))
    FI

    process.state=PROCESSSTATE.STATE_COLLECTING
  WHEN PROCESSSTATE.OP_RELEASE THEN
    IF process.state<>PROCESSSTATE.STATE_COLLECTING
        OR ProcessStorageEmpty(process)=0 THEN
      RETURN(PROCESSSTATE.Entry POINTER(0))
    FI

    ProcessClear(process)
  ELSE
    RETURN(PROCESSSTATE.Entry POINTER(0))
  ESAC

  owner.error=0

RETURN(process)

; Validate and dispatch process gateway operations for the caller.
CARD FUNC ProcessControl(TaskControl POINTER caller CARD saved DosControlArgs
    POINTER args)
  PROCESSSTATE.Entry POINTER process

  process=ProcessChange(caller,args.operation,args.argument)
  PointerResult(saved,Task POINTER(process))

RETURN(saved)
