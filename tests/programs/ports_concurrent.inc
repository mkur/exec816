; Four-task workload 8: bounded completion request plus queued RPC interference.
TYPE PortPacket=[
  EXEC.Message header
  CARD sequence
]

EXEC.MsgPort POINTER completionPort,clientPort,peerPort
EXEC.MsgPort sharedPort
EXEC.MsgPort ARRAY registryPorts(8)
PortPacket completionRequest
PortPacket ARRAY burst(8)
BYTE ARRAY registryNames(272)
BYTE ARRAY registryMiss(34)
BYTE ARRAY seenReplies(8)
CARD portBursts,portReplies,registryRounds,completionReplies,maxOutstanding
LONGCARD rootSignalsBefore

PROC ClientResume(BYTE unused)

RETURN

PROC ManualPort(EXEC.MsgPort POINTER port BYTE action,bit, EXEC.Task POINTER owner)

  port.mp_Node.ln_Type=EXEC.NT_MSGPORT
  port.mp_Flags=action
  port.mp_SigBit=bit
  port.mp_SigTask=owner
  EXECLISTS.NewList(@port.mp_MsgList)

RETURN

PROC PortsPrepare(BYTE unused)
  CARD i,j
  EXEC.MsgPort POINTER port

  rootSignalsBefore=parent.tc_SigAlloc
  completionPort=EXEC.CreateMsgPort()
  clientPort=EXEC.CreateMsgPort()
  HeapRequire(completionPort<>EXEC.MsgPort POINTER(0)
      AND clientPort<>EXEC.MsgPort POINTER(0))
  ManualPort(@sharedPort,EXEC.PA_SIGNAL,clientPort.mp_SigBit,parent)
  completionRequest.header.mn_ReplyPort=completionPort
  completionRequest.header.mn_Length=CARD(SIZEOF(PortPacket))
  FOR i=0 TO 7 DO
    port=@registryPorts(i)
    ManualPort(port,EXEC.PA_IGNORE,255,EXEC.Task POINTER(0))
    port.mp_Node.ln_Name=@registryNames((SIZE(i) LSH 5)+(SIZE(i) LSH 1))
    FOR j=0 TO 31 DO
      port.mp_Node.ln_Name(j)=120
    OD

    port.mp_Node.ln_Name(32)=BYTE(65+i)
    port.mp_Node.ln_Name(33)=0
  OD

  FOR j=0 TO 31 DO
    registryMiss(j)=120
  OD

  registryMiss(32)=90
  registryMiss(33)=0

RETURN

PROC RegistryStep(BYTE unused)
  CARD i
  EXEC.MsgPort POINTER found

  FOR i=0 TO 7 DO
    EXEC.AddPort(@registryPorts(i))
  OD

  EXEC.Forbid()
  found=EXEC.FindPort(@registryMiss)
  HeapRequire(found=EXEC.MsgPort POINTER(0))
  found=EXEC.FindPort(registryPorts(7).mp_Node.ln_Name)
  HeapRequire(found=@registryPorts(7))
  EXEC.Permit()
  FOR i=0 TO 7 DO
    EXEC.RemPort(@registryPorts(i))
  OD

  IF pumpSent<byteCount THEN
    registryRounds==+1
  FI

RETURN

PROC BurstSend(BYTE unused)
  CARD i
  PortPacket POINTER packet

  EXEC.Forbid()
  FOR i=0 TO 7 DO
    seenReplies(i)=0
    packet=@burst(i)
    packet.sequence=i
    packet.header.mn_Length=CARD(SIZEOF(PortPacket))
    packet.header.mn_ReplyPort=clientPort
    IF (i & 1)<>0 THEN
      packet.header.mn_ReplyPort=@sharedPort
    FI

    EXEC.PutMsg(peerPort,@packet.header)
  OD

  maxOutstanding=8
  EXEC.Permit()

RETURN

BYTE FUNC DrainReply(EXEC.MsgPort POINTER port)
  PortPacket POINTER packet

  packet=PortPacket POINTER(EXEC.GetMsg(port))
  IF packet=PortPacket POINTER(0) THEN
    RETURN(0)
  FI

  HeapRequire(packet.sequence<8 AND packet.header.mn_Node.ln_Type=EXEC.NT_REPLYMSG)
  HeapRequire(packet=@burst(packet.sequence) AND seenReplies(packet.sequence)=0)
  seenReplies(packet.sequence)=1
  IF pumpSent<byteCount THEN
    portReplies==+1
  FI

RETURN(1)

PROC PortsClear(BYTE unused)
  BYTE POINTER buffer

  buffer=EXEC.AllocVec(4097,EXEC.MEMF_CLEAR)
  HeapRequire(buffer<>BYTE POINTER(0))
  HeapRequire(buffer^=0 AND buffer(4096)=0)
  buffer^=$d7
  buffer(4096)=$7d
  EXEC.FreeVec(buffer)
  IF pumpSent<byteCount THEN
    heapClears==+1
  FI

RETURN

PROC PortsStep(BYTE unused)
  CARD count
  LONGCARD received

  BurstSend(0)
  count=0
  WHILE count<8 DO
    WHILE DrainReply(clientPort)<>0 DO
      count==+1
    OD

    WHILE DrainReply(@sharedPort)<>0 DO
      count==+1
    OD

    IF count<8 THEN
      received=EXEC.Wait(LONGCARD(1) LSH clientPort.mp_SigBit)
    FI
  OD

  IF pumpSent<byteCount THEN
    portBursts==+1
  FI

  RegistryStep(0)
  HeapAllocateStep()
  PortsClear(0)

RETURN

PROC PortsFinish(BYTE unused)
  EXEC.Message POINTER msg

  msg=EXEC.WaitPort(completionPort)
  msg=EXEC.GetMsg(completionPort)
  HeapRequire(msg=@completionRequest.header
      AND msg.mn_Node.ln_Type=EXEC.NT_REPLYMSG)
  ClientResume(0)
  completionReplies=1
  HeapRequire(EXEC.GetMsg(clientPort)=EXEC.Message POINTER(0))
  HeapRequire(EXEC.GetMsg(@sharedPort)=EXEC.Message POINTER(0))
  EXEC.DeleteMsgPort(clientPort)
  EXEC.DeleteMsgPort(completionPort)
  HeapRequire(parent.tc_SigAlloc=rootSignalsBefore)

RETURN
