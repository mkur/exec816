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

RETURN
