; Task-side renderer arbitration. IRQ/NMI never inspect these records. A queue
; entry is a grant slot plus one; zero reserves the next unit for the owner.
Grant POINTER ARRAY grantSlots(GRANTS)
BYTE ARRAY accessQueue(GRANTS+1)
BYTE accessHead,accessCount,grantCount,physical,ownerQueued,dmaHeld,accessFailed
CARD ownerDepth
LONGCARD accessWake
Grant POINTER borrower

PROC AccessReset()

  accessHead=0
  accessCount=0
  grantCount=0
  physical=0
  ownerQueued=0
  ownerDepth=0
  dmaHeld=0
  accessFailed=0
  accessWake=0
  borrower=NULL

RETURN

PROC Queue(BYTE item)
  BYTE tail

  tail=accessHead+accessCount
  IF tail>GRANTS THEN
    tail==-(GRANTS+1)
  FI

  accessQueue(tail)=item
  accessCount==+1

RETURN

; The caller holds Forbid. Ownership is published before the wake hint.
PROC Next()
  BYTE item

  IF physical<>0 OR accessCount=0 OR sharedState=FAULTED THEN
    RETURN
  FI

  item=accessQueue(accessHead)
  accessHead==+1
  IF accessHead>GRANTS THEN
    accessHead=0
  FI

  accessCount==-1
  IF item=0 THEN
    ownerQueued=0
    physical=1
    EXEC.Signal(current.owner.task,accessWake)
  ELSE
    borrower=grantSlots(item-1)
    borrower.state=GRANT_OWNED
    physical=2
    EXEC.Signal(borrower.task,borrower.mask)
  FI

RETURN

PROC Unqueue(BYTE item)
  BYTE read,write,count,index,value

  read=accessHead
  write=read
  count=accessCount
  index=0
  WHILE index<count DO
    value=accessQueue(read)
    read==+1
    IF read>GRANTS THEN
      read=0
    FI

    IF value<>item THEN
      accessQueue(write)=value
      write==+1
      IF write>GRANTS THEN
        write=0
      FI
    ELSE
      accessCount==-1
    FI

    index==+1
  OD

RETURN

PUBLIC BYTE FUNC Blocked()

RETURN(physical=2)

PUBLIC CARD FUNC Delegated()

RETURN(grantCount)

; Lifetime owner installs its existing hardware/service wake signal once.
PUBLIC CARD FUNC OwnerWake(LONGCARD mask)

  IF current=NULL OR Valid(current)=0 OR mask=0
      OR (mask & current.owner.task.tc_SigAlloc)<>mask THEN
    RETURN(INVALID_OWNER)
  FI

  accessWake=mask

RETURN(OK)

; Delegation admits and retains one borrowing Task, without opening hardware.
PUBLIC CARD FUNC Delegate(Grant POINTER grant)
  BYTE slot

  IF current=NULL OR Valid(current)=0 OR sharedState<>ACTIVE
      OR accessWake=0 THEN
    RETURN(INVALID_OWNER)
  FI

  IF accessFailed<>0 THEN
    RETURN(DEVICE_FAULT)
  FI

  IF grant.state<>GRANT_FREE OR grant.task=NULL OR grant.mask=0
      OR (grant.mask & grant.task.tc_SigAlloc)<>grant.mask THEN
    RETURN(BAD_ARGUMENT)
  FI

  EXEC.Forbid()
  IF grantCount=GRANTS THEN
    EXEC.Permit()
    RETURN(NO_MEMORY)
  FI

  FOR slot=0 TO GRANTS-1 DO
    IF grantSlots(slot)=NULL THEN
      IF EXEC.RetainTask(grant.task,@grant.owner)=0 THEN
        EXEC.Permit()
        RETURN(INVALID_OWNER)
      FI

      grant.generation=generation
      grant.slot=CARD(slot)
      grant.state=GRANT_READY
      grantSlots(slot)=grant
      grantCount==+1
      EXEC.Permit()
      RETURN(OK)
    FI
  OD

  EXEC.Permit()

RETURN(NO_MEMORY)

PUBLIC CARD FUNC OwnerEnter()

  IF current=NULL OR current.owner.task<>EXEC.FindTask(NULL) THEN
    RETURN(INVALID_OWNER)
  FI

  IF sharedState=FAULTED THEN
    RETURN(DEVICE_FAULT)
  FI

  ; Only this owner can publish a new grant. With none admitted there is no
  ; competing queue editor; IRQ/NMI never touch these Task-side fields.
  IF grantCount=0 THEN
    physical=1
    ownerDepth==+1
    RETURN(OK)
  FI

  EXEC.Forbid()
  IF physical=2 OR (physical=0 AND accessCount<>0) THEN
    IF ownerQueued=0 THEN
      Queue(0)
      ownerQueued=1
    FI

    Next()
    EXEC.Permit()
    RETURN(BUSY)
  FI

  physical=1
  ownerDepth==+1
  EXEC.Permit()

RETURN(OK)

; Nested native units share a turn reservation; async DMA pins the owner after
; its last ordinary call returns. Only the owner may retire that pin.
PUBLIC CARD FUNC OwnerDrop()

  IF grantCount=0 THEN
    IF physical<>1 OR ownerDepth=0 THEN
      RETURN(INVALID_OWNER)
    FI

    ownerDepth==-1
    IF ownerDepth=0 AND dmaHeld=0 THEN
      physical=0
    FI

    RETURN(OK)
  FI

  EXEC.Forbid()
  IF physical<>1 OR ownerDepth=0 THEN
    EXEC.Permit()
    RETURN(INVALID_OWNER)
  FI

  ownerDepth==-1
  IF ownerDepth=0 AND dmaHeld=0 THEN
    physical=0
    Next()
  FI

  EXEC.Permit()

RETURN(OK)

PUBLIC CARD FUNC OwnerEnd(CARD dma)

  dmaHeld=BYTE(dma)

RETURN(OwnerDrop())

PUBLIC CARD FUNC Enter(Grant POINTER grant)

  IF grant.task<>EXEC.FindTask(NULL) THEN
    RETURN(INVALID_OWNER)
  FI

  EXEC.Forbid()
  IF accessFailed<>0 THEN
    EXEC.Permit()
    RETURN(DEVICE_FAULT)
  FI

  IF grant.state<>GRANT_READY OR grant.generation<>generation THEN
    EXEC.Permit()
    RETURN(INVALID_OWNER)
  FI

  IF physical=0 AND accessCount=0 THEN
    physical=2
    borrower=grant
    grant.state=GRANT_OWNED
  ELSE
    grant.state=GRANT_QUEUED
    Queue(BYTE(grant.slot+1))
  FI

  WHILE grant.state=GRANT_QUEUED DO
    EXEC.Permit()
    EXEC.Wait(grant.mask)
    EXEC.Forbid()
  OD

  IF grant.state<>GRANT_OWNED THEN
    EXEC.Permit()
    RETURN(IF accessFailed<>0 THEN DEVICE_FAULT ELSE INVALID_OWNER FI)
  FI

  EXEC.Permit()

RETURN(OK)

PUBLIC CARD FUNC Leave(Grant POINTER grant)

  EXEC.Forbid()
  IF physical<>2 OR borrower<>grant OR grant.state<>GRANT_OWNED THEN
    EXEC.Permit()
    RETURN(INVALID_OWNER)
  FI

  grant.state=IF accessFailed<>0 THEN GRANT_REVOKED ELSE GRANT_READY FI
  borrower=NULL
  physical=0
  Next()
  EXEC.Permit()

RETURN(OK)

PUBLIC CARD FUNC Revoke(Grant POINTER grant)

  IF current=NULL OR Valid(current)=0 THEN
    RETURN(INVALID_OWNER)
  FI

  EXEC.Forbid()
  IF grant.state=GRANT_OWNED THEN
    EXEC.Permit()
    RETURN(BUSY)
  FI

  IF grant.state=GRANT_QUEUED THEN
    Unqueue(BYTE(grant.slot+1))
  ELSEIF grant.state<>GRANT_READY AND grant.state<>GRANT_REVOKED THEN
    EXEC.Permit()
    RETURN(INVALID_OWNER)
  FI

  grant.state=GRANT_REVOKED
  EXEC.Signal(grant.task,grant.mask)
  EXEC.Permit()

RETURN(OK)

; The borrower acknowledges revocation or voluntarily closes its idle grant.
; Owner teardown cannot release hardware while any grant still retains a Task.
PUBLIC CARD FUNC GrantClose(Grant POINTER grant)

  IF grant.task<>EXEC.FindTask(NULL) THEN
    RETURN(INVALID_OWNER)
  FI

  EXEC.Forbid()
  IF grant.state<>GRANT_READY AND grant.state<>GRANT_REVOKED THEN
    EXEC.Permit()
    RETURN(BUSY)
  FI

  grantSlots(grant.slot)=NULL
  grantCount==-1
  IF EXEC.ReleaseTask(@grant.owner)=0 THEN
    HEAPCORE.Abort(4)
  FI

  grant.state=GRANT_FREE
  grant.generation=0
  EXEC.Signal(current.owner.task,accessWake)
  EXEC.Permit()

RETURN(OK)

; A quiescent adapter fault revokes admission and wakes queued callers. Hardware
; and its lifetime lease remain with the owner until every grant is collected.
; An unquiesced fault keeps every pin/record and requires reset; it never hands
; the renderer to another Task.
PUBLIC CARD FUNC AccessFault(CARD unquiesced)
  BYTE slot

  EXEC.Forbid()
  accessFailed=1
  IF unquiesced<>0 THEN
    sharedState=FAULTED
    current.state=FAULTED
    EXEC.Permit()
    RETURN(DEVICE_FAULT)
  FI

  accessCount=0
  accessHead=0
  ownerQueued=0
  FOR slot=0 TO GRANTS-1 DO
    IF grantSlots(slot)<>NULL THEN
      IF grantSlots(slot).state<>GRANT_OWNED THEN
        grantSlots(slot).state=GRANT_REVOKED
        EXEC.Signal(grantSlots(slot).task,grantSlots(slot).mask)
      FI
    FI
  OD

  EXEC.Signal(current.owner.task,accessWake)
  EXEC.Permit()

RETURN(DEVICE_FAULT)
