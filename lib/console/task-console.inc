; Private keyboard producer admission; called only with SWITCHING held.
INCLUDE "console-storage-action.inc"
INCLUDE "console-action.inc"

PUBLIC EXTERNAL BYTE FUNC ConsoleClaim()

PUBLIC EXTERNAL PROC ConsoleRelease()

; Initialize kernel-side console admission and producer ownership.
PROC ConsoleInit()
  BYTE POINTER bytes
  CARD index

  bytes=BYTE POINTER(ADDRESS(CS_BASE))
  FOR index=0 TO CS_BYTES-1 DO
    bytes(index)=0
  OD

  bytes=BYTE POINTER(ADDRESS(CS_CAPTURE))
  FOR index=0 TO CON_CAPTURE_SIZE-1 DO
    bytes(index)=0
  OD

  ConsoleNames()

RETURN

BYTE FUNC ConsoleService(BYTE service)

RETURN(service>=CON_PRIVATE_BIND AND service<=CON_PRIVATE_RELEASE)

; Identify the Task retained as the console event producer.
BYTE FUNC ConsoleProducerBound(TaskControl POINTER ctx)
  SignalBinding POINTER binding

  binding=SignalBinding POINTER(ADDRESS(CS_CAPTURE+CON_CAPTURE_BINDING))

RETURN(binding.active<>0 AND binding.context=ctx)

; Clear producer authority before the bound Task can disappear.
PROC ConsoleForgetBinding()
  SignalBinding POINTER binding

  binding=SignalBinding POINTER(ADDRESS(CS_CAPTURE+CON_CAPTURE_BINDING))
  binding.task=Task POINTER(0)
  binding.context=TaskControl POINTER(0)
  binding.mask=0

RETURN

; Check the caller's control packet before borrowing its addresses.
BYTE FUNC ConsolePacketValid(TaskControl POINTER caller CARD saved CARD bytes)
  CARD base

  base=SavedWord(saved,T_FRAME_X)
  IF base<caller.stackFloor OR base>caller.stackTop THEN
    RETURN(0)
  FI

RETURN(bytes<=caller.stackTop-base+1)

; Retire producer binding only when its kernel-side obligations are settled.
CARD FUNC ConsoleUnbind(TaskControl POINTER caller CARD saved SignalBinding
    POINTER binding)
  LONGCARD previous

  IF binding.active<>0 AND binding.context<>caller THEN
    RETURN(T_FAULT)
  FI

  ConsoleRelease()
  IF DrainWakes()=0 THEN
    RETURN(T_FAULT)
  FI

  previous=SignalChange(caller.item,0,binding.mask)
  ConsoleForgetBinding()

RETURN(saved)

; Authorize console producer transitions against the current Task.
CARD FUNC ConsoleProducerControl(TaskControl POINTER caller CARD saved BYTE service)
  SignalBinding POINTER binding
  SignalArguments POINTER args
  BYTE claimed

  binding=SignalBinding POINTER(ADDRESS(CS_CAPTURE+CON_CAPTURE_BINDING))
  IF (Flags(saved) & 4)<>0 OR osBusy<>0 THEN
    RETURN(T_FAULT)
  FI

  IF service=CON_PRIVATE_RELEASE THEN
    RETURN(ConsoleUnbind(caller,saved,binding))
  FI

  IF binding.active<>0 THEN
    Result(saved,0)
    RETURN(saved)
  FI

  IF ConsolePacketValid(caller,saved,8)=0 THEN
    RETURN(T_FAULT)
  FI

  args=SignalArguments POINTER(ArgumentPointer(saved))
  IF args.target<>caller.item OR args.bits=0 THEN
    Result(saved,0)
    RETURN(saved)
  FI

  IF (args.bits & caller.item.tc_SigAlloc)<>args.bits THEN
    Result(saved,0)
    RETURN(saved)
  FI

  binding.task=caller.item
  binding.context=caller
  binding.mask=args.bits
  claimed=ConsoleClaim()
  IF claimed=0 THEN
    ConsoleForgetBinding()
  FI

  Result(saved,CARD(claimed))

RETURN(saved)

; Recognize supported console device names at the kernel boundary.
PROC ConsoleNames()
  CARD POINTER words
  BYTE POINTER name

  words=CARD POINTER(ADDRESS(CS_BASE+CON_SERVICE_NAME))
  words(0)=$6f63
  words(1)=$736e
  words(2)=$6c6f
  words(3)=$2e65
  words(4)=$6564
  words(5)=$6976
  words(6)=$6563
  name=BYTE POINTER(words)
  name(14)=0

RETURN

BYTE FUNC ConsoleName(BYTE POINTER name)

RETURN(IOName(name,BYTE POINTER(ADDRESS(CS_BASE+CON_SERVICE_NAME))))

BYTE FUNC ConsoleDevice(IORequest POINTER request)

RETURN(request.io_Device=BYTE POINTER(ADDRESS(CS_BASE)))
