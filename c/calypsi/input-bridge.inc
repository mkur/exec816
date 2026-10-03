; Uniform three-LONGCARD C packets preserve full huge addresses until these
; checks pass. No invalid value is truncated into a native pointer.
CARD FUNC CInputAcquire(LONGCARD lease,recordValue,value)

  IF INPUT.Extent(lease,INPUT.LEASE_BYTES)=0
      OR INPUT.Extent(recordValue,INPUT.CONFIG_BYTES)=0 THEN
    RETURN(INPUT.BAD_ARGUMENT)
  FI

RETURN(INPUT.Acquire(INPUT.Lease POINTER(ADDRESS(lease)),
    INPUT.Config POINTER(ADDRESS(recordValue))))

CARD FUNC CInputCreateRoute(LONGCARD lease,recordValue,value)

  IF INPUT.Extent(lease,INPUT.LEASE_BYTES)=0
      OR INPUT.Extent(recordValue,4)=0 OR value>$ffff THEN
    RETURN(INPUT.BAD_ARGUMENT)
  FI

RETURN(INPUT.CreateRoute(INPUT.Lease POINTER(ADDRESS(lease)),CARD(value),
    LONGCARD POINTER(ADDRESS(recordValue))))

CARD FUNC CInputPublishRoute(LONGCARD lease,recordValue,value)

  IF INPUT.Extent(lease,INPUT.LEASE_BYTES)=0 THEN
    RETURN(INPUT.BAD_ARGUMENT)
  FI

RETURN(INPUT.PublishRoute(INPUT.Lease POINTER(ADDRESS(lease)),value))

CARD FUNC CInputRetireRoute(LONGCARD lease,recordValue,value)

  IF INPUT.Extent(lease,INPUT.LEASE_BYTES)=0 THEN
    RETURN(INPUT.BAD_ARGUMENT)
  FI

RETURN(INPUT.RetireRoute(INPUT.Lease POINTER(ADDRESS(lease)),value))

CARD FUNC CInputDiscard(LONGCARD lease,recordValue,value)

  IF INPUT.Extent(lease,INPUT.LEASE_BYTES)=0 THEN
    RETURN(INPUT.BAD_ARGUMENT)
  FI

RETURN(INPUT.Discard(INPUT.Lease POINTER(ADDRESS(lease)),value))

CARD FUNC CInputPending(LONGCARD lease,recordValue,value)

  IF INPUT.Shape(lease,INPUT.LEASE_BYTES)=0
      OR INPUT.Shape(recordValue,2)=0 THEN
    RETURN(INPUT.BAD_ARGUMENT)
  FI

RETURN(INPUT.Pending(INPUT.Lease POINTER(ADDRESS(lease)),
    CARD POINTER(ADDRESS(recordValue))))

CARD FUNC CInputTake(LONGCARD lease,recordValue,value)

  IF INPUT.Shape(lease,INPUT.LEASE_BYTES)=0
      OR INPUT.Shape(recordValue,INPUT.EVENT_BYTES)=0 THEN
    RETURN(INPUT.BAD_ARGUMENT)
  FI

RETURN(INPUT.Take(INPUT.Lease POINTER(ADDRESS(lease)),
    INPUT.Event POINTER(ADDRESS(recordValue))))

CARD FUNC CInputRelease(LONGCARD lease,recordValue,value)

  IF INPUT.Extent(lease,INPUT.LEASE_BYTES)=0 THEN
    RETURN(INPUT.BAD_ARGUMENT)
  FI

RETURN(INPUT.Release(INPUT.Lease POINTER(ADDRESS(lease))))

PROC BindInput()

  LET entries=ADDRESS POINTER(C_EXECINPUTENTRIES)
  entries(0)=ADDRESS(@CInputAcquire)
  entries(1)=ADDRESS(@CInputCreateRoute)
  entries(2)=ADDRESS(@CInputPublishRoute)
  entries(3)=ADDRESS(@CInputRetireRoute)
  entries(4)=ADDRESS(@CInputDiscard)
  entries(5)=ADDRESS(@CInputPending)
  entries(6)=ADDRESS(@CInputTake)
  entries(7)=ADDRESS(@CInputRelease)

RETURN
