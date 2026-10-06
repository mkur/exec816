; Console setup and the fixed keyboard backend; called with SWITCHING held.
INCLUDE "console-storage-action.inc"
INCLUDE "console-action.inc"

; Initialize kernel-side console admission and producer ownership.
PROC ConsoleInit()
  BYTE POINTER bytes
  CARD index

  bytes=BYTE POINTER(ADDRESS(CS_BASE))
  FOR index=0 TO CS_BYTES-1 DO
    bytes(index)=0
  OD

  ConsoleNames()

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
