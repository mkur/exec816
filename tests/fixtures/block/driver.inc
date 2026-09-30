; Test-only ownership and blocking I/O around the production adapter steps.
INCLUDE "../../../lib/dos/dos-types.inc"

; Fixtures own their volume allocation; the filesystem worker preallocates it.
BLOCKTYPES.Volume POINTER FUNC BlockAttach(BLOCKTYPES.Adapter POINTER adapter
    CARD unit,profile LONGCARD sectors CARD dataBytes BYTE boot LONGCARD generation)

  adapter.error=0
  IF adapter.busy<>0 OR adapter.owners=$ffff THEN
    adapter.error=ERROR_OBJECT_IN_USE
    RETURN(NULL)
  FI

  IF BLOCKIO.Geometry(unit,profile,sectors,dataBytes,boot,generation)=0 THEN
    adapter.error=EXEC.IOERR_BADLENGTH
    RETURN(NULL)
  FI

  LET volume=BLOCKTYPES.Volume POINTER(EXEC.AllocMem(
      BLOCKTYPES.VOLUME_SIZE,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
  IF volume=NULL THEN
    adapter.error=ERROR_NO_FREE_STORE
    RETURN(NULL)
  FI

  volume.adapter=BYTE POINTER(adapter)
  volume.unit=BYTE(unit)
  volume.profile=BYTE(profile)
  volume.sectors=sectors
  volume.dataBytes=dataBytes
  volume.boot=boot
  volume.generation=generation
  IF BLOCKIO.OpenVolume(adapter,volume)=NULL THEN
    EXEC.FreeMem(BYTE POINTER(volume),BLOCKTYPES.VOLUME_SIZE)
    RETURN(NULL)
  FI

RETURN(volume)

; Standalone tests collect the transfer synchronously, without an FS worker.
LONGINT FUNC BlockFetch(BLOCKTYPES.Adapter POINTER adapter
    BLOCKTYPES.Volume POINTER volume LONGCARD sector)

  LET status=BLOCKIO.BeginFetch(adapter,volume,sector)
  IF status<>2 THEN
    RETURN(adapter.error)
  FI

  LET error=BLOCKWIRE.Transfer(adapter.request,NULL,NULL)

RETURN(BLOCKIO.FinishFetch(adapter,volume,sector,LONGINT(error)))

; A rejected destination invalidates scratch, preserving retained cache tags.
LONGINT FUNC BlockReadSector(BLOCKTYPES.Adapter POINTER adapter
    BLOCKTYPES.Volume POINTER volume LONGCARD sector
    BYTE POINTER destination LONGCARD capacity)
  CARD index

  LET expected=BLOCKIO.SectorBytes(volume,sector)
  IF expected=0 OR capacity<LONGCARD(expected) THEN
    adapter.valid=0
    adapter.cached=NULL
    adapter.error=EXEC.IOERR_BADLENGTH
    RETURN(adapter.error)
  FI

  IF BLOCKIO.Mapped(destination,LONGCARD(expected))=0 THEN
    adapter.valid=0
    adapter.cached=NULL
    adapter.error=EXEC.IOERR_BADADDRESS
    RETURN(adapter.error)
  FI

  LET error=BlockFetch(adapter,volume,sector)
  IF error<>0 THEN
    RETURN(error)
  FI

  FOR index=0 TO expected-1 DO
    destination(index)=adapter.buffer(index)
  OD

RETURN(0)
