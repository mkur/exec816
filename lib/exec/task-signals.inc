; Included by taskpolicy.act after the common Task and mask helpers.
; Called only in the guarded kernel activation. Native transactions synchronize
; the received masks and wait publication with IRQ producers.
TYPE SignalArguments=[
  Task POINTER target
  LONGCARD bits
]

; Called immediately before restoring a READY signal waiter's continuation.
; Posts while READY therefore join this result. No other task runs here.
BYTE FUNC CompleteWait(TaskControl POINTER ctx)

  IF ctx.waitReason<>T_WAIT_SIGNAL THEN
    RETURN(1)
  FI

  LET result=WaitComplete(ctx)
  IF result=0 THEN
    RETURN(0)
  FI

  MaskResult(ctx.savedS,result)

RETURN(1)

; Consume matching signals immediately or suspend the caller until delivery.
CARD FUNC WaitTask(TaskControl POINTER ctx CARD saved)

  IF (Flags(saved) & 4)<>0 THEN
    RETURN(T_FAULT)
  FI

  LET argument=LONGCARD POINTER(ArgumentPointer(saved))
  LET mask=argument^
  LET result=WaitBegin(ctx,mask)
  IF result<>0 THEN
    MaskResult(saved,result)
    RETURN(saved)
  FI

; Forbid belongs to this suspended context, not to the entire processor.
; Keep both nesting representations unchanged for continuation resumption.
RETURN(Select(ctx))

; The enclosing service chooses when scheduling is safe. Port publication
; completes its links before posting; public Signal still switches on a wake.
BYTE FUNC PostSignal(TaskControl POINTER target LONGCARD bits)

  LET ignored=SignalChange(target.item,bits,bits)
  IF WakeMatch(target)<>0 THEN
    Ready(target)
    RETURN(1)
  FI

RETURN(0)

; Post signals to a live Task and reconsider scheduling when it becomes ready.
CARD FUNC SignalTask(TaskControl POINTER caller CARD saved)
  TaskControl POINTER target

  LET args=SignalArguments POINTER(ArgumentPointer(saved))
  LET item=args.target
  target=Lookup(item)
  IF target=NULL THEN
    RETURN(T_FAULT)
  FI

  LET bits=args.bits
  IF bits=0 THEN
    RETURN(saved)
  FI

  IF PostSignal(target,bits)<>0 THEN
    caller.pending=1
    RETURN(Switch(caller,saved))
  FI

RETURN(saved)
