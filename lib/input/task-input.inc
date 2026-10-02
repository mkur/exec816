; Fixed source descriptors for source-qualified producer admission.
INCLUDE "input-storage.act.inc"
PUBLIC EXTERNAL BYTE FUNC InputClaim()
PUBLIC EXTERNAL PROC InputRelease()
PUBLIC EXTERNAL BYTE FUNC PointerCaptureClaim()
PUBLIC EXTERNAL PROC PointerCaptureRelease()

PROC InputInit()
  CARD index
  BYTE POINTER bytes

  bytes=BYTE POINTER(ADDRESS(IN_STATE))
  FOR index=0 TO IN_STATE_BYTES-1 DO
    bytes(index)=0
  OD

  bytes=BYTE POINTER(ADDRESS(IN_CAPTURE))
  FOR index=0 TO IN_CAPTURE_BYTES-1 DO
    bytes(index)=0
  OD

  bytes=BYTE POINTER(ADDRESS(IN_POINTER_STATE))
  FOR index=0 TO IN_STATE_BYTES-1 DO
    bytes(index)=0
  OD

  bytes=BYTE POINTER(ADDRESS(IN_POINTER_CAPTURE))
  FOR index=0 TO IN_POINTER_CAPTURE_BYTES-1 DO
    bytes(index)=0
  OD

  bytes=BYTE POINTER(ADDRESS(IN_ACQUISITIONS))
  FOR index=0 TO 3 DO
    bytes(index)=0
  OD

RETURN

SignalBinding POINTER FUNC KeyboardBinding()

RETURN(SignalBinding POINTER(ADDRESS(IN_CAPTURE+16)))

BYTE FUNC KeyboardClaim()

RETURN(InputClaim())

PROC KeyboardRelease()

  InputRelease()

RETURN

SignalBinding POINTER FUNC PointerBinding()

RETURN(SignalBinding POINTER(ADDRESS(IN_POINTER_CAPTURE+16)))

BYTE FUNC PointerClaim()

RETURN(PointerCaptureClaim())

PROC PointerRelease()

  PointerCaptureRelease()

RETURN
