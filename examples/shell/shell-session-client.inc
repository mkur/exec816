; The caller retains this upper-RAM request and payload through exact reply.
BYTE FUNC ShellSessionExchange(ShellSessionControl POINTER control
    ShellSessionMessage POINTER request)
  EXEC.Message POINTER reply

  LET port=EXEC.CreateMsgPort()
  IF port=NULL THEN
    request.primary=PROCESS.RETURN_FAIL
    request.secondary=DOS.ERROR_NO_FREE_STORE
    RETURN(0)
  FI

  request.message.mn_Node.ln_Type=EXEC.NT_MESSAGE
  request.message.mn_ReplyPort=port
  request.message.mn_Length=SHELLSESSIONMESSAGE_SIZE
  EXEC.PutMsg(control.port,@request.message)
  DO
    reply=EXEC.GetMsg(port)
    IF reply<>NULL THEN
      EXIT
    FI

    reply=EXEC.WaitPort(port)
  OD

  IF reply<>@request.message THEN
    HEAPCORE.Abort($ff94)
  FI

  EXEC.DeleteMsgPort(port)

RETURN(1)
