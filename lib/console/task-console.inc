; Console setup and the fixed keyboard backend; called with SWITCHING held.
INCLUDE "console-storage-action.inc"
INCLUDE "console-action.inc"

PUBLIC EXTERNAL BYTE FUNC ConsoleClaim()

PUBLIC EXTERNAL PROC ConsoleRelease()

; Initialize kernel-side console admission and producer ownership.
PROC ConsoleInit()
  BYTE POINTER bytes
  CARD index

  bytes=BYTE POINTER(ADDRESS(CS_BASE))
  FOR index=0 TO CS_BYTES-1 DO
    bytes(index)=0
  OD

  bytes=BYTE POINTER(ADDRESS(CS_CAPTURE))
  FOR index=0 TO CON_CAPTURE_SIZE-1 DO
    bytes(index)=0
  OD

  ConsoleNames()

RETURN

; Fixed keyboard backend for the public source-qualified producer API.
SignalBinding POINTER FUNC KeyboardBinding()

RETURN(SignalBinding POINTER(ADDRESS(CS_CAPTURE+CON_CAPTURE_BINDING)))

BYTE FUNC KeyboardClaim()

RETURN(ConsoleClaim())

PROC KeyboardRelease()

  ConsoleRelease()

RETURN

; Recognize supported console device names at the kernel boundary.
PROC ConsoleNames()
  CARD POINTER words
  BYTE POINTER name

  words=CARD POINTER(ADDRESS(CS_BASE+CON_SERVICE_NAME))
  words(0)=$6f63
  words(1)=$736e
  words(2)=$6c6f
  words(3)=$2e65
  words(4)=$6564
  words(5)=$6976
  words(6)=$6563
  name=BYTE POINTER(words)
  name(14)=0

RETURN

BYTE FUNC ConsoleName(BYTE POINTER name)

RETURN(IOName(name,BYTE POINTER(ADDRESS(CS_BASE+CON_SERVICE_NAME))))

BYTE FUNC ConsoleDevice(IORequest POINTER request)

RETURN(request.io_Device=BYTE POINTER(ADDRESS(CS_BASE)))
