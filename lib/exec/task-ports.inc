; Task-only port operations. SWITCHING serializes links; IRQs can post signals
; but never inspect message queues. Pointer validity/membership belong to users.
; Recognize the public port service family.
BYTE FUNC PortService(BYTE service)

RETURN(service>=P_SERVICE_PUT_MSG AND service<=P_SERVICE_FIND_PORT)

; Initialize the public port registry in its reserved storage.
PROC InitPorts()

  LET registry=EXECLISTS.List POINTER(ADDRESS(PS_BASE))
  EXECLISTS.NewList(registry)
  registry.lh_Type=0
  registry.lh_Pad=0

RETURN

; Reject null or wrapping port records before accessing their fields.
BYTE FUNC PortStorage(MsgPort POINTER port)

  IF port=NULL THEN
    RETURN(0)
  FI

RETURN(LONGCARD(ADDRESS(port))+P_MSGPORT_BYTES<=LONGCARD($1000000))

; Accept complete port records with a supported notification mode.
BYTE FUNC ValidPort(MsgPort POINTER port)

  IF PortStorage(port)=0 THEN
    RETURN(0)
  FI

  IF port.mp_Node.ln_Type<>P_NT_MSGPORT THEN
    RETURN(0)
  FI

  IF port.mp_Flags<>P_PA_SIGNAL AND port.mp_Flags<>P_PA_IGNORE THEN
    RETURN(0)
  FI

RETURN(1)

; Require an aligned message header that cannot wrap the address space.
BYTE FUNC ValidMessage(Message POINTER msg)

  IF msg=NULL OR (ADDRESS(msg) & ADDRESS(1))<>0 THEN
    RETURN(0)
  FI

RETURN(LONGCARD(ADDRESS(msg))+P_MESSAGE_BYTES<=LONGCARD($1000000))

; Publish the message before notifying its recipient of available work.
CARD FUNC SendMessage(TaskControl POINTER caller CARD saved MsgPort POINTER port
    Message POINTER msg BYTE kind)
  TaskControl POINTER target
  LONGCARD mask

  IF ValidPort(port)=0 THEN
    RETURN(T_FAULT)
  FI

  target=NULL
  mask=0
  IF port.mp_Flags=P_PA_SIGNAL THEN
    IF port.mp_SigBit>=32 THEN
      RETURN(T_FAULT)
    FI

    target=Lookup(port.mp_SigTask)
    IF target=NULL THEN
      RETURN(T_FAULT)
    FI

    mask=SignalBit(port.mp_SigBit)
  FI

  msg.mn_Node.ln_Type=kind
  EXECLISTS.AddTail(@port.mp_MsgList,@msg.mn_Node)
  IF target<>NULL THEN
    IF PostSignal(target,mask)<>0 THEN
      caller.pending=1
    FI
  FI

RETURN(saved)

; Inspect a recipient's queue for WaitPort without removing its first message.
CARD FUNC PortHead(TaskControl POINTER caller CARD saved MsgPort POINTER port)
  Message POINTER msg

  IF ValidPort(port)=0 THEN
    RETURN(T_FAULT)
  FI

  IF (Flags(saved) & 4)<>0 OR port.mp_Flags<>P_PA_SIGNAL THEN
    RETURN(T_FAULT)
  FI

  IF port.mp_SigTask<>caller.item OR port.mp_SigBit>=32 THEN
    RETURN(T_FAULT)
  FI

  msg=NULL
  IF EXECLISTS.IsListEmpty(@port.mp_MsgList)=0 THEN
    msg=Message POINTER(port.mp_MsgList.lh_Head)
  FI

  PointerResult(saved,Task POINTER(msg))

RETURN(saved)

; Verify caller ownership, signal allocation and an empty queue before
; deletion.
CARD FUNC PortDelete(TaskControl POINTER caller CARD saved MsgPort POINTER port)

  IF ValidPort(port)=0 THEN
    RETURN(T_FAULT)
  FI

  LET item=caller.item
  IF port.mp_SigTask<>item THEN
    RETURN(T_FAULT)
  FI

  IF port.mp_SigBit<T_USER_SIGNAL_FIRST OR port.mp_SigBit>=32 THEN
    RETURN(T_FAULT)
  FI

  LET mask=SignalBit(port.mp_SigBit)
  IF (item.tc_SigAlloc & mask)=0 THEN
    RETURN(T_FAULT)
  FI

  IF EXECLISTS.IsListEmpty(@port.mp_MsgList)=0 THEN
    RETURN(T_FAULT)
  FI

  Result(saved,CARD(port.mp_SigBit))

RETURN(saved)

; Find, publish or unpublish named ports under the scheduler guard.
CARD FUNC RegistryCall(CARD saved BYTE service BYTE POINTER arg)
  MsgPort POINTER port

  LET registry=EXECLISTS.List POINTER(ADDRESS(PS_BASE))
  IF arg=NULL THEN
    RETURN(T_FAULT)
  FI

  IF service=P_SERVICE_FIND_PORT THEN
    port=MsgPort POINTER(EXECLISTS.FindName(registry,arg))
    PointerResult(saved,Task POINTER(port))
    RETURN(saved)
  FI

  port=MsgPort POINTER(arg)
  IF service=P_SERVICE_REM_PORT THEN
    IF ValidPort(port)=0 THEN
      RETURN(T_FAULT)
    FI

    EXECLISTS.Remove(@port.mp_Node)
    RETURN(saved)
  FI

  IF PortStorage(port)=0 THEN
    RETURN(T_FAULT)
  FI

  IF port.mp_Flags<>P_PA_SIGNAL AND port.mp_Flags<>P_PA_IGNORE THEN
    RETURN(T_FAULT)
  FI

  ; Only inactive, unlinked ports may be published. Membership and producer
  ; quiescence are caller preconditions; no registry scan is added here.
  port.mp_Node.ln_Type=P_NT_MSGPORT
  EXECLISTS.NewList(@port.mp_MsgList)
  port.mp_MsgList.lh_Type=0
  port.mp_MsgList.lh_Pad=0
  EXECLISTS.Enqueue(registry,@port.mp_Node)

RETURN(saved)

; Send a message or return it through its reply port, if one exists.
CARD FUNC QueueCall(TaskControl POINTER caller CARD saved BYTE service
    PortSendArgs POINTER args)
  MsgPort POINTER port
  Message POINTER msg

  IF service=P_SERVICE_PUT_MSG THEN
    msg=args.message
    IF ValidMessage(msg)=0 THEN
      RETURN(T_FAULT)
    FI

    RETURN(SendMessage(caller,saved,args.port,msg,P_NT_MESSAGE))
  FI

  msg=Message POINTER(args.port)
  IF ValidMessage(msg)=0 THEN
    RETURN(T_FAULT)
  FI

  port=msg.mn_ReplyPort
  IF port=NULL THEN
    msg.mn_Node.ln_Type=P_NT_FREEMSG
    RETURN(saved)
  FI

RETURN(SendMessage(caller,saved,port,msg,P_NT_REPLYMSG))

; Validate the port packet and route queue, lifetime or registry operations.
CARD FUNC PortCall(TaskControl POINTER caller CARD saved BYTE service)
  CARD bytes

  LET base=SavedWord(saved,T_FRAME_X)
  bytes=3
  IF service=P_SERVICE_PUT_MSG THEN
    bytes=6
  FI

  IF base<caller.stackFloor OR base>caller.stackTop THEN
    RETURN(T_FAULT)
  FI

  IF bytes>caller.stackTop-base+1 THEN
    RETURN(T_FAULT)
  FI

  LET args=PortSendArgs POINTER(ArgumentPointer(saved))
  IF service>=P_SERVICE_ADD_PORT THEN
    RETURN(RegistryCall(saved,service,BYTE POINTER(args.port)))
  FI

  IF service=P_SERVICE_WAIT_HEAD THEN
    RETURN(PortHead(caller,saved,args.port))
  FI

  IF service=P_SERVICE_DELETE_CHECK THEN
    RETURN(PortDelete(caller,saved,args.port))
  FI

RETURN(QueueCall(caller,saved,service,args))
