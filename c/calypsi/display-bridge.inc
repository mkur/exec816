; Huge C values are checked before their native 24-bit conversion.
CARD FUNC CDisplayAcquire(LONGCARD value CARD kind)

  IF value>$ffffff THEN
    RETURN(DISPLAY.INVALID_OWNER)
  FI

RETURN(DISPLAY.Acquire(DISPLAY.Lease POINTER(ADDRESS(value)),kind))

CARD FUNC CDisplayActivate(LONGCARD value)

  IF value>$ffffff THEN
    RETURN(DISPLAY.INVALID_OWNER)
  FI

RETURN(DISPLAY.Activate(DISPLAY.Lease POINTER(ADDRESS(value))))

CARD FUNC CDisplayCheck(LONGCARD value)

  IF value>$ffffff THEN
    RETURN(DISPLAY.INVALID_OWNER)
  FI

RETURN(DISPLAY.Check(DISPLAY.Lease POINTER(ADDRESS(value))))

CARD FUNC CDisplayBeginRelease(LONGCARD value)

  IF value>$ffffff THEN
    RETURN(DISPLAY.INVALID_OWNER)
  FI

RETURN(DISPLAY.BeginRelease(DISPLAY.Lease POINTER(ADDRESS(value))))

CARD FUNC CDisplayRelease(LONGCARD value)

  IF value>$ffffff THEN
    RETURN(DISPLAY.INVALID_OWNER)
  FI

RETURN(DISPLAY.Release(DISPLAY.Lease POINTER(ADDRESS(value))))

CARD FUNC CDisplayFault(LONGCARD value)

  IF value>$ffffff THEN
    RETURN(DISPLAY.INVALID_OWNER)
  FI

RETURN(DISPLAY.Fault(DISPLAY.Lease POINTER(ADDRESS(value))))

CARD FUNC CBlitterOpen(LONGCARD value)

  IF value>$ffffff THEN
    RETURN(DISPLAY.INVALID_OWNER)
  FI

RETURN(BLITTER.Open(DISPLAY.Lease POINTER(ADDRESS(value))))

CARD FUNC CBlitterClose(LONGCARD value)

  IF value>$ffffff THEN
    RETURN(DISPLAY.INVALID_OWNER)
  FI

RETURN(BLITTER.Close(DISPLAY.Lease POINTER(ADDRESS(value))))

LONGCARD FUNC CBlitterMask(LONGCARD value)

  IF value>$ffffff THEN
    RETURN(0)
  FI

RETURN(BLITTER.Mask(DISPLAY.Lease POINTER(ADDRESS(value))))

CARD FUNC CDisplayDelegate(LONGCARD value)

RETURN(DISPLAY.Delegate(DISPLAY.Grant POINTER(ADDRESS(value))))

CARD FUNC CDisplayRevoke(LONGCARD value)

RETURN(DISPLAY.Revoke(DISPLAY.Grant POINTER(ADDRESS(value))))

CARD FUNC CDisplayGrantClose(LONGCARD value)

RETURN(DISPLAY.GrantClose(DISPLAY.Grant POINTER(ADDRESS(value))))

CARD FUNC CDisplayEnter(LONGCARD value)

RETURN(DISPLAY.Enter(DISPLAY.Grant POINTER(ADDRESS(value))))

CARD FUNC CDisplayLeave(LONGCARD value)

RETURN(DISPLAY.Leave(DISPLAY.Grant POINTER(ADDRESS(value))))

CARD FUNC CDisplayOwnerEnd(LONGCARD unused CARD dma)

RETURN(DISPLAY.OwnerEnd(dma))

CARD FUNC CDisplayAccessFault(LONGCARD unused CARD unquiesced)

RETURN(DISPLAY.AccessFault(unquiesced))

; The table is private upper data in the checked C image, never a ROM vector.
PROC BindDisplay()

  LET entries=ADDRESS POINTER(C_EXECDISPLAYENTRIES)
  entries(0)=ADDRESS(@CDisplayAcquire)
  entries(1)=ADDRESS(@CDisplayActivate)
  entries(2)=ADDRESS(@CDisplayCheck)
  entries(3)=ADDRESS(@CDisplayBeginRelease)
  entries(4)=ADDRESS(@CDisplayRelease)
  entries(5)=ADDRESS(@CDisplayFault)
  entries(6)=ADDRESS(@DISPLAYBOOT.Known)
  entries(7)=ADDRESS(@DISPLAYADAPTER.Ticks)
  entries(8)=ADDRESS(@DISPLAYADAPTER.ResetRequired)
  entries(9)=ADDRESS(@CBlitterOpen)
  entries(10)=ADDRESS(@CBlitterClose)
  entries(11)=ADDRESS(@CBlitterMask)
  entries(12)=ADDRESS(@BLITTERADAPTER.Arm)
  entries(13)=ADDRESS(@BLITTERADAPTER.State)
  entries(14)=ADDRESS(@BLITTERADAPTER.Reset)
  entries(15)=ADDRESS(@CDisplayDelegate)
  entries(16)=ADDRESS(@CDisplayRevoke)
  entries(17)=ADDRESS(@CDisplayGrantClose)
  entries(18)=ADDRESS(@CDisplayEnter)
  entries(19)=ADDRESS(@CDisplayLeave)
  entries(20)=ADDRESS(@DISPLAY.OwnerEnter)
  entries(21)=ADDRESS(@CDisplayOwnerEnd)
  entries(22)=ADDRESS(@DISPLAY.OwnerWake)
  entries(23)=ADDRESS(@CDisplayAccessFault)
  entries(24)=ADDRESS(@DISPLAY.Delegated)


RETURN
