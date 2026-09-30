; Test-only blocking driver for the production parser's bounded steps.
; The provider supplies sector bytes; all decoding stays in MyDOS.
INCLUDE "../block/driver.inc"

BYTE POINTER FUNC ReadPhysical(FSBTYPES.Workspace POINTER work CARD sector)

  LET adapter=BLOCKTYPES.Adapter POINTER(work.volume.block.adapter)
  work.operations==+1
  work.ioError=BlockFetch(adapter,work.volume.block,LONGCARD(sector))
  IF work.ioError<>0 THEN
    work.error=ERROR_DISK_NOT_VALIDATED
    RETURN(NULL)
  FI

RETURN(adapter.buffer)

BYTE FUNC Mount(FSBTYPES.Workspace POINTER work)

  IF MYDOS.BeginMount(work)=FSSTATUS.ERROR THEN
    RETURN(FSSTATUS.ERROR)
  FI

  IF ReadPhysical(work,work.neededSector)=NULL THEN
    RETURN(FSSTATUS.ERROR)
  FI

RETURN(MYDOS.MountBuffered(work))

BYTE FUNC GetEntry(FSBTYPES.Workspace POINTER work CARD directory BYTE ordinal)

  LET status=MYDOS.BeginEntry(work,directory,ordinal)
  IF status<>FSSTATUS.NEED_IO THEN
    RETURN(status)
  FI

  IF ReadPhysical(work,work.neededSector)=NULL THEN
    RETURN(FSSTATUS.ERROR)
  FI

RETURN(MYDOS.BufferedEntry(work))

BYTE FUNC Resolve(FSBTYPES.Workspace POINTER work BYTE POINTER path)
  BYTE status

  status=MYDOS.StartResolve(work,path)
  WHILE status=FSSTATUS.NEED_IO OR status=FSSTATUS.NEXT_COMPONENT DO
    IF status=FSSTATUS.NEXT_COMPONENT THEN
      status=MYDOS.ResolveComponent(work)

    ELSE
      IF ReadPhysical(work,work.neededSector)=NULL THEN
        RETURN(FSSTATUS.ERROR)
      FI

      status=MYDOS.ResolveStep(work)
    FI
  OD

RETURN(status)
