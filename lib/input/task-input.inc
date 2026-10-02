; Fixed keyboard backend for source-qualified producer admission.
INCLUDE "input-storage.act.inc"
PUBLIC EXTERNAL BYTE FUNC InputClaim()
PUBLIC EXTERNAL PROC InputRelease()

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

RETURN

SignalBinding POINTER FUNC KeyboardBinding()

RETURN(SignalBinding POINTER(ADDRESS(IN_CAPTURE+16)))

BYTE FUNC KeyboardClaim()

RETURN(InputClaim())

PROC KeyboardRelease()

  InputRelease()

RETURN
