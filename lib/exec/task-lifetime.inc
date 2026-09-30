; Public lifetime facilities. All Task-side updates run under SWITCHING.
; A lease is caller-owned, zero-initialized, location-bound and not copyable.
TYPE RetainArguments=[
  Task POINTER task
  TaskLease POINTER lease
]

TYPE LeaseArguments=[TaskLease POINTER lease]

; Require a complete writable lease in caller stack, image or heap storage.
BYTE FUNC LeaseStorage(TaskLease POINTER lease)

  LET location=ADDRESS(lease)
  IF location=0 OR location>ADDRESS($fffff4) THEN
    RETURN(0)
  FI

  LET caller=RecordFor(current)
  IF (location RSH 16)=0 THEN
    IF location>=ADDRESS(caller.stackFloor)
        AND location+SIZE(T_LEASE_SIZE)<=ADDRESS(caller.stackTop)+SIZE(1) THEN
      RETURN(1)
    FI
  FI

  IF Writable(location,SIZE(T_LEASE_SIZE))<>0 THEN
    RETURN(1)
  FI

RETURN(HEAPPOLICY.MemoryType(BYTE POINTER(lease))<>0
      AND HEAPPOLICY.MemoryType(BYTE POINTER(location+SIZE(T_LEASE_SIZE-1)))<>0)

; Count live application contexts, excluding registered resident services.
BYTE FUNC ApplicationCount()
  TaskControl POINTER ctx
  BYTE id,count

  count=0
  FOR id=0 TO T_CAPACITY-1 DO
    ctx=RecordFor(id)
    IF ctx.state<>T_STATE_FREE AND ctx.residentMask=0 THEN
      count==+1
    FI
  OD

RETURN(count)

; Notify registered services when the last application has gone away.
PROC NotifyResidents()
  TaskControl POINTER ctx
  BYTE id,posted

  IF ApplicationCount()<>0 THEN
    RETURN
  FI

  FOR id=0 TO T_CAPACITY-1 DO
    ctx=RecordFor(id)
    IF ctx.state<>T_STATE_FREE AND ctx.residentMask<>0 THEN
      posted=PostSignal(ctx,ctx.residentMask)
    FI
  OD

RETURN

; Bind an empty lease to this Task incarnation and prevent its removal.
BYTE FUNC Retain(Task POINTER item TaskLease POINTER lease)

  IF LeaseStorage(lease)=0 THEN
    RETURN(0)
  FI

  IF lease.task<>NULL OR lease.incarnation<>0 OR lease.identity<>0 THEN
    RETURN(0)
  FI

  LET target=Lookup(item)
  IF target=NULL THEN
    RETURN(0)
  FI

  IF target.holds=$ffff THEN
    RETURN(0)
  FI

  target.holds==+1
  lease.task=item
  lease.incarnation=target.incarnation
  lease.identity=ADDRESS(lease)

RETURN(1)

; Release an original, live lease; reject copies and stale Task incarnations.
BYTE FUNC Release(TaskLease POINTER lease)

  IF LeaseStorage(lease)=0 THEN
    RETURN(0)
  FI

  IF lease.identity<>ADDRESS(lease) OR lease.task=NULL THEN
    RETURN(0)
  FI

  LET target=Lookup(lease.task)
  IF target=NULL THEN
    RETURN(0)
  FI

  IF target.incarnation<>lease.incarnation OR target.holds=0 THEN
    RETURN(0)
  FI

  target.holds==-1
  lease.task=NULL
  lease.incarnation=0
  lease.identity=0

RETURN(1)

; Associate owned signals with a resident that waits for application shutdown.
BYTE FUNC Register(TaskControl POINTER ctx LONGCARD mask)

  LET item=ctx.item
  IF ctx.id=0 OR ctx.id>=T_CAPACITY OR ctx.residentMask<>0 OR mask=0 THEN
    RETURN(0)
  FI

  IF (item.tc_SigAlloc & mask)<>mask THEN
    RETURN(0)
  FI

  ctx.residentMask=mask
  NotifyResidents()

RETURN(1)

; Validate the caller packet and dispatch public Task lifetime operations.
CARD FUNC LifetimeCall(TaskControl POINTER ctx CARD saved BYTE service)
  RetainArguments POINTER args
  LeaseArguments POINTER lease
  LONGCARD POINTER mask
  BYTE outcome
  CARD bytes

  LET base=SavedWord(saved,T_FRAME_X)
  bytes=0
  IF service=T_SERVICE_RETAIN_TASK THEN
    bytes=6

  ELSEIF service=T_SERVICE_RELEASE_TASK THEN
    bytes=3

  ELSEIF service=T_SERVICE_REGISTER_RESIDENT THEN
    bytes=4
  FI

  IF bytes<>0 THEN
    IF base<ctx.stackFloor OR base>ctx.stackTop OR bytes>ctx.stackTop-base+1 THEN
      RETURN(T_FAULT)
    FI
  FI

  IF service=T_SERVICE_RETAIN_TASK THEN
    args=RetainArguments POINTER(ArgumentPointer(saved))
    outcome=Retain(args.task,args.lease)

  ELSEIF service=T_SERVICE_RELEASE_TASK THEN
    lease=LeaseArguments POINTER(ArgumentPointer(saved))
    outcome=Release(lease.lease)

  ELSEIF service=T_SERVICE_REGISTER_RESIDENT THEN
    mask=LONGCARD POINTER(ArgumentPointer(saved))
    outcome=Register(ctx,mask^)

  ELSE
    outcome=ctx.residentMask<>0
    ctx.residentMask=0
  FI

  Result(saved,CARD(outcome))

RETURN(saved)
