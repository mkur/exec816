; Include after globals. These are test setup helpers, not public conveniences.
PROC PrepareTask(EXEC.Task POINTER item CARD base BYTE POINTER name)
  BYTE POINTER bytes
  CARD index

  bytes=BYTE POINTER(item)
  FOR index=0 TO EXEC.TASK_SIZE-1 DO
    bytes(index)=0
  OD

  item.tc_Node.ln_Type=EXEC.NT_TASK
  item.tc_Node.ln_Name=name
  item.tc_SPLower=ADDRESS(base)
  item.tc_SPUpper=ADDRESS(base+$600)
  item.tc_SPReg=ADDRESS(base+$5fe)
  EXECLISTS.NewList(@item.tc_MemEntry)

RETURN

PROC AwaitRemoval(EXEC.Task POINTER item)
  CARD status

  WHILE item.tc_State<>EXEC.TS_REMOVED DO
    status=EXECTASKS.Sleep(1)
  OD

RETURN
