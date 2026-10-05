; Sixteen equal deadlines expire while the serial pump and port workers run.
EXEC.MsgPort POINTER timerPort
TIMER.TimerClockRequest POINTER timerClock
EXEC.IORequest POINTER ARRAY timerRequests(16)
CARD timerReplies

PROC TimerPrepare(BYTE unused)
  BYTE index
  TIMER.TimerClockRequest POINTER request

  timerPort=EXEC.CreateMsgPort()
  HeapRequire(timerPort<>NULL)
  timerClock=TIMER.TimerClockRequest POINTER(EXEC.CreateIORequest(timerPort,38))
  HeapRequire(timerClock<>NULL)
  HeapRequire(EXEC.OpenDevice(BYTE POINTER(c"timer.device"),TIMER.UNIT_VBLANK,
      @timerClock.tc_Request,0)=0)
  timerClock.tc_Request.io_Command=TIMER.TD_READCLOCK
  HeapRequire(EXEC.DoIO(@timerClock.tc_Request)=0)
  timerClock.ticks_lo==+8
  FOR index=0 TO 15 DO
    timerRequests(index)=EXEC.CreateIORequest(timerPort,38)
    HeapRequire(timerRequests(index)<>NULL)
    request=TIMER.TimerClockRequest POINTER(timerRequests(index))
    request.tc_Request.io_Device=timerClock.tc_Request.io_Device
    request.tc_Request.io_Unit=timerClock.tc_Request.io_Unit
    request.tc_Request.io_Command=TIMER.TD_WAITUNTIL
    request.ticks_hi=timerClock.ticks_hi
    request.ticks_lo=timerClock.ticks_lo
    EXEC.SendIO(@request.tc_Request)
  OD

RETURN

PROC TimerFinish(BYTE unused)
  BYTE index

  FOR index=0 TO 15 DO
    HeapRequire(timerRequests(index).io_Message.mn_Node.ln_Type=EXEC.NT_REPLYMSG)
    HeapRequire(EXEC.WaitIO(timerRequests(index))=0)
    timerReplies==+1
    timerRequests(index).io_Device=NULL
    timerRequests(index).io_Unit=NULL
    EXEC.DeleteIORequest(timerRequests(index))
  OD

  EXEC.CloseDevice(@timerClock.tc_Request)
  EXEC.DeleteIORequest(@timerClock.tc_Request)
  EXEC.DeleteMsgPort(timerPort)

RETURN
