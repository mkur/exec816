; Only the native classifier enters here: busy Obtain or final queued Release,
; before any ownership mutation. SWITCHING excludes other Task activations;
; IRQ producers never inspect semaphore objects or tc_Node resource links.
CARD FUNC SemaphoreCall(TaskControl POINTER ctx CARD saved BYTE service)

  LET semaphore=NativeSemaphore POINTER(ArgumentPointer(saved))
  LET item=ctx.item
  IF service=SEM_SERVICE_OBTAIN_SEMAPHORE THEN
    IF ctx.semaphoreOwned=$ffff OR (Flags(saved) & 4)<>0 THEN
      RETURN(T_FAULT)
    FI

    item.tc_Node.ln_Succ=NULL
    item.tc_Node.ln_Pred=EXECLISTS.Node POINTER(semaphore.tail)
    IF semaphore.tail=NULL THEN
      semaphore.head=item
    ELSE
      semaphore.tail.tc_Node.ln_Succ=@item.tc_Node
    FI
    semaphore.tail=item
    ctx.semaphoreWait=BYTE POINTER(semaphore)
    ctx.waitReason=T_WAIT_SEMAPHORE
    SetState(ctx,T_STATE_SEMAPHORE_WAIT,T_TS_WAIT)

    ; Switch would requeue this blocked caller. Select retires its activation.
    RETURN(Select(ctx))
  FI

  LET recipient=semaphore.head
  LET incoming=TaskControl POINTER(recipient.tc_ExecPrivate)
  semaphore.head=Task POINTER(recipient.tc_Node.ln_Succ)
  IF semaphore.head=NULL THEN
    semaphore.tail=NULL
  ELSE
    semaphore.head.tc_Node.ln_Pred=NULL
  FI
  recipient.tc_Node.ln_Succ=NULL
  recipient.tc_Node.ln_Pred=NULL
  ctx.semaphoreOwned==-1
  incoming.semaphoreOwned==+1
  semaphore.owner=recipient
  semaphore.depth=1
  incoming.semaphoreWait=NULL
  incoming.waitReason=T_WAIT_NONE

  ; No object access follows Ready: ownership already bars recipient removal.
  Ready(incoming)
  ctx.pending=1

RETURN(Switch(ctx,saved))
