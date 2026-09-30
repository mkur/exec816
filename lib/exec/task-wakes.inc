; Public platform producer lifecycle and wake queue. Native transactions protect
; links against IRQ posts; SWITCHING excludes other policy activations. A head
; remains CLAIMED after detach until WakeMatch atomically publishes READY or
; releases the claim. Queued nodes are separate from tc_Node.
PUBLIC EXTERNAL PROC IRQWindow()

PUBLIC EXTERNAL BYTE FUNC SerialClaim()

PUBLIC EXTERNAL PROC SerialRelease()

; Retire any queued wake before reusing or removing the Task context.
PROC CancelWake(TaskControl POINTER ctx)

  IF ctx.queued<>0 THEN
    CancelWakeNode(ctx)
  FI

RETURN

; Claim one posted wake and validate its retained recipient before
; publication.
BYTE FUNC DrainOne()

  LET ctx=TakeWake()
  IF ctx=NULL THEN
    RETURN(0)
  FI

  IF ctx=TaskControl POINTER($ffffff) THEN
    RETURN($ff)
  FI

  LET item=ctx.item
  IF Lookup(item)<>ctx THEN
    RETURN($ff)
  FI

  IF WakeMatch(ctx)<>0 THEN
    Ready(ctx)
  FI

RETURN(1)

; Drain pending wakes with IRQ opportunities; zero reports a corrupt queue.
BYTE FUNC DrainWakes()
  BYTE result,count

  count=0
  IRQWindow()
  DO
    result=DrainOne()
    IF result=$ff THEN
      RETURN(0)
    FI

    IF result<>0 THEN
      count==+1
      IRQWindow()
    FI

  UNTIL result=0
  OD

RETURN(count+1)

; Keep any Task retained by a service or serial binding from being removed.
BYTE FUNC BoundProducer(TaskControl POINTER ctx)

  LET binding=SignalBinding POINTER(T_SERIAL_BINDING)
  IF DosWorkerBound(ctx)<>0 OR ConsoleProducerBound(ctx)<>0 THEN
    RETURN(1)
  FI

RETURN(binding.context<>NULL AND (binding.context=ctx OR binding.pad=ctx.id))

; Prevent reuse of signal bits still retained by the serial producer.
BYTE FUNC ProducerSignalBound(TaskControl POINTER ctx LONGCARD mask)

  LET binding=SignalBinding POINTER(T_SERIAL_BINDING)

RETURN(binding.context=ctx AND (binding.mask & mask)<>0)

; Bind, retire or drain the serial producer using the caller's ownership.
CARD FUNC ProducerControl(TaskControl POINTER caller CARD saved BYTE service)
  CARD base

  LET binding=SignalBinding POINTER(T_SERIAL_BINDING)
  IF (Flags(saved) & 4)<>0 OR osBusy<>0 THEN
    RETURN(T_FAULT)
  FI

  IF service=T_SERVICE_RELEASE_PRODUCER THEN
    IF binding.context=NULL THEN
      RETURN(saved)
    FI

    IF binding.context<>caller AND binding.pad<>caller.id THEN
      RETURN(T_FAULT)
    FI

    SerialRelease()
    RETURN(saved)
  FI

  IF service=T_SERVICE_DRAIN_PRODUCER THEN
    IF DrainWakes()=0 THEN
      RETURN(T_FAULT)
    FI

    IF binding.active=0 AND binding.context<>NULL THEN
      IF binding.context<>caller AND binding.pad<>caller.id THEN
        RETURN(T_FAULT)
      FI

      binding.task=NULL
      binding.context=NULL
      binding.mask=0
      binding.pad=0
    FI

    caller.pending=1
    RETURN(Switch(caller,saved))
  FI

  IF binding.context<>NULL THEN
    Result(saved,0)
    RETURN(saved)
  FI

  base=SavedWord(saved,T_FRAME_X)
  IF base<caller.stackFloor OR base>caller.stackTop OR 8>caller.stackTop-base+1 THEN
    RETURN(T_FAULT)
  FI

  LET args=SignalArguments POINTER(ArgumentPointer(saved))
  LET target=Lookup(args.target)
  IF target=NULL THEN
    Result(saved,0)
    RETURN(saved)
  FI

  IF target.holds=0 OR args.bits=0
      OR (args.target.tc_SigAlloc & args.bits)<>args.bits THEN
    Result(saved,0)
    RETURN(saved)
  FI

  binding.task=args.target
  binding.context=target
  binding.mask=args.bits
  binding.pad=caller.id
  base=CARD(SerialClaim())
  IF base=0 THEN
    binding.task=NULL
    binding.context=NULL
    binding.mask=0
    binding.pad=0
  FI

  Result(saved,base)

RETURN(saved)
