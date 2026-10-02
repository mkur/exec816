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

; Fixed source dispatch uses resident binding storage, never caller callbacks.
SignalBinding POINTER FUNC ProducerBinding(CARD source)

  IF source=T_PRODUCER_SERIAL THEN
    RETURN(SignalBinding POINTER(T_SERIAL_BINDING))
  FI

  IF source=T_PRODUCER_KEYBOARD THEN
    RETURN(KeyboardBinding())
  FI

RETURN(NULL)

; Keep both the recipient and controller alive until inactive wakes retire.
BYTE FUNC BoundProducer(TaskControl POINTER ctx)
  CARD source

  IF DosWorkerBound(ctx)<>0 THEN
    RETURN(1)
  FI

  FOR source=T_PRODUCER_SERIAL TO T_PRODUCER_KEYBOARD DO
    BEGIN
      LET binding=ProducerBinding(source)
      IF binding<>NULL THEN
        IF binding.context<>NULL
            AND (binding.context=ctx OR binding.pad=ctx.id) THEN
          RETURN(1)
        FI
      FI
    END
  OD

RETURN(0)

; Released bindings still protect their signal until Drain removes the hold.
BYTE FUNC ProducerSignalBound(TaskControl POINTER ctx LONGCARD mask)
  CARD source

  FOR source=T_PRODUCER_SERIAL TO T_PRODUCER_KEYBOARD DO
    BEGIN
      LET binding=ProducerBinding(source)
      IF binding<>NULL THEN
        IF binding.context=ctx AND (binding.mask & mask)<>0 THEN
          RETURN(1)
        FI
      FI
    END
  OD

RETURN(0)

; Bind, release or drain one source through the caller's retained authority.
CARD FUNC ProducerControl(TaskControl POINTER caller CARD saved BYTE service)
  CARD base,bytes

  IF (Flags(saved) & 4)<>0 OR osBusy<>0 THEN
    RETURN(T_FAULT)
  FI

  bytes=2
  IF service=T_SERVICE_BIND_PRODUCER THEN
    bytes=T_PRODUCER_BYTES
  FI

  base=SavedWord(saved,T_FRAME_X)
  IF base<caller.stackFloor OR base>caller.stackTop
      OR bytes>caller.stackTop-base+1 THEN
    RETURN(T_FAULT)
  FI

  LET args=ProducerArguments POINTER(ArgumentPointer(saved))
  LET source=args.source
  LET binding=ProducerBinding(source)
  IF binding=NULL THEN
    IF service=T_SERVICE_BIND_PRODUCER THEN
      Result(saved,0)
      RETURN(saved)
    FI

    RETURN(T_FAULT)
  FI

  IF service<>T_SERVICE_BIND_PRODUCER AND binding.context<>NULL
      AND binding.context<>caller AND binding.pad<>caller.id THEN
    RETURN(T_FAULT)
  FI

  IF service=T_SERVICE_RELEASE_PRODUCER THEN
    IF binding.context<>NULL THEN
      IF source=T_PRODUCER_SERIAL THEN
        SerialRelease()
      ELSE
        KeyboardRelease()
      FI
    FI

    RETURN(saved)
  FI

  IF service=T_SERVICE_DRAIN_PRODUCER THEN
    IF DrainWakes()=0 THEN
      RETURN(T_FAULT)
    FI

    IF binding.active=0 AND binding.context<>NULL THEN
      binding.task=NULL
      binding.context=NULL
      binding.mask=0
      binding.pad=0
    FI

    caller.pending=1
    RETURN(Switch(caller,saved))
  FI

  IF binding.context<>NULL OR args.pad<>0 THEN
    Result(saved,0)
    RETURN(saved)
  FI

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
  IF source=T_PRODUCER_SERIAL THEN
    base=CARD(SerialClaim())
  ELSE
    base=CARD(KeyboardClaim())
  FI
  IF base=0 THEN
    binding.task=NULL
    binding.context=NULL
    binding.mask=0
    binding.pad=0
  FI

  Result(saved,base)

RETURN(saved)
