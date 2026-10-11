; Observations occupy spare space in the existing upper-memory device arena.
IDEPLUS.Diagnostics POINTER FUNC Observation()

RETURN(IDEPLUS.Diagnostics POINTER(ADDRESS(IDEMETA.DIAGNOSTICS)))

; A fresh admission replaces the previous attempt, under lifetime exclusion.
PROC ResetObservation()

  A816MEMORY.Clear(BYTE POINTER(Observation()),SIZEOF(IDEPLUS.Diagnostics))
  LET info=Observation()
  info.attempted=1
  info.stage=IDEPLUS.STAGE_WORKER
  info.reason=IDEPLUS.REASON_WORKER
  info.slot=$ff

RETURN

; Save a transport failure atomically; later polls and cleanup cannot erase it.
BYTE FUNC TransportFailure(BYTE error,reason)

  EXEC.Forbid()
  LET info=Observation()
  LET c=Control()
  info.reason=reason
  info.status=c.status
  info.ataError=IF error=IDEPLUS.ERROR_ATA THEN c.error ELSE 0 FI
  EXEC.Permit()

RETURN(error)

; Table rejection leaves the current LBA/slot available for a hardware report.
BYTE FUNC RejectTable(BYTE reason)

  LET info=Observation()
  info.reason=reason

RETURN(0)

; Copy the last settled admission, without selecting the PBI or starting I/O.
PUBLIC PROC Diagnostics(IDEPLUS.Diagnostics POINTER target)

  EXEC.Forbid()
  LET bus=DriverBus POINTER(ADDRESS(IDEMETA.BUS))
  IF bus.state=1 THEN
    A816MEMORY.Clear(BYTE POINTER(target),SIZEOF(IDEPLUS.Diagnostics))
    target.attempted=1
    target.stage=IDEPLUS.STAGE_WORKER
    target.slot=$ff
  ELSE
    A816MEMORY.Move(BYTE POINTER(target),BYTE POINTER(Observation()),
        SIZEOF(IDEPLUS.Diagnostics))
  FI

  target.state=bus.state
  target.generation=bus.generation
  EXEC.Permit()

RETURN

; Copy one discovered APT slot, including its skipped/admitted reason.
PUBLIC BYTE FUNC PartitionStatus(BYTE number IDEPLUS.PartitionInfo POINTER target)
  BYTE available

  EXEC.Forbid()
  LET bus=DriverBus POINTER(ADDRESS(IDEMETA.BUS))
  LET info=Observation()
  available=0
  A816MEMORY.Clear(BYTE POINTER(target),SIZEOF(IDEPLUS.PartitionInfo))
  IF number>=1 AND number<=15 AND bus.state<>1 AND info.apt<>0 THEN
    BEGIN
      LET unit=UnitAt(number)
      target.unit=number
      target.reason=unit.pad
      IF unit.enabled<>0 THEN
        target.start=unit.start
        target.sectors=unit.sectors
        target.bytes=unit.bytes
        target.offset=unit.offset
        target.flags=0
        IF info.durable<>0 THEN
          target.flags=IDEPLUS.FLAG_DURABLE
        FI

        IF unit.flags<>0 OR info.durable=0 OR (info.boardStatus & $10)<>0 THEN
          target.flags=target.flags OR IDEPLUS.FLAG_READONLY
        FI
      FI

      available=1
    END
  FI

  EXEC.Permit()

RETURN(available)
