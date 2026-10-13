; Translate retained numeric reasons; reporting never accesses hardware.
CSTRING FUNC ShellIdeReason(BYTE value)

  CASE value OF
  WHEN IDEPLUS.REASON_NONE THEN
    RETURN(c"none")

  WHEN IDEPLUS.REASON_WORKER THEN
    RETURN(c"no worker slot or signal")

  WHEN IDEPLUS.REASON_RESOURCES THEN
    RETURN(c"no driver resources")

  WHEN IDEPLUS.REASON_TIMER THEN
    RETURN(c"timer unavailable")

  WHEN IDEPLUS.REASON_CONTROLLER_ABSENT THEN
    RETURN(c"controller absent")

  WHEN IDEPLUS.REASON_DISK_ABSENT THEN
    RETURN(c"disk absent")

  WHEN IDEPLUS.REASON_TIMEOUT THEN
    RETURN(c"ATA readiness timeout")

  WHEN IDEPLUS.REASON_ATA THEN
    RETURN(c"ATA command error")

  WHEN IDEPLUS.REASON_NOT_LBA THEN
    RETURN(c"not an LBA28 ATA disk")

  WHEN IDEPLUS.REASON_SECTOR_SIZE THEN
    RETURN(c"physical sectors !=512B")

  WHEN IDEPLUS.REASON_CAPACITY THEN
    RETURN(c"capacity exceeds LBA28")

  WHEN IDEPLUS.REASON_NO_APT THEN
    RETURN(c"APT/MBR signature absent")

  WHEN IDEPLUS.REASON_CONTAINER THEN
    RETURN(c"invalid MBR APT container")

  WHEN IDEPLUS.REASON_HEADER THEN
    RETURN(c"invalid APT header or offset")

  WHEN IDEPLUS.REASON_LINK THEN
    RETURN(c"invalid APT link or bounds")

  WHEN IDEPLUS.REASON_CYCLE THEN
    RETURN(c"APT link cycle")

  WHEN IDEPLUS.REASON_ENTRY THEN
    RETURN(c"invalid APT extent/id")

  WHEN IDEPLUS.REASON_TABLE_OVERLAP THEN
    RETURN(c"partition overlaps table")

  WHEN IDEPLUS.REASON_PARTITION_OVERLAP THEN
    RETURN(c"partitions overlap")

  WHEN IDEPLUS.REASON_CHAIN_SHORT THEN
    RETURN(c"APT chain incomplete")

  WHEN IDEPLUS.REASON_REVISION THEN
    RETURN(c"unsupported APT revision")

  ELSE
    RETURN(c"unknown")
  ESAC

RETURN(c"unknown")

; Translate retained numeric reasons; reporting never accesses hardware.
CSTRING FUNC ShellIdePhase(BYTE value)

  CASE value OF
  WHEN IDEPLUS.STAGE_NONE THEN
    RETURN(c"unattempted")

  WHEN IDEPLUS.STAGE_WORKER THEN
    RETURN(c"worker admission")

  WHEN IDEPLUS.STAGE_RESOURCES THEN
    RETURN(c"driver resources")

  WHEN IDEPLUS.STAGE_TIMER THEN
    RETURN(c"timer open")

  WHEN IDEPLUS.STAGE_CONTROLLER THEN
    RETURN(c"controller detection")

  WHEN IDEPLUS.STAGE_IDENTIFY THEN
    RETURN(c"IDENTIFY")

  WHEN IDEPLUS.STAGE_APT THEN
    RETURN(c"APT discovery")

  WHEN IDEPLUS.STAGE_READY THEN
    RETURN(c"ready")

  WHEN IDEPLUS.STAGE_TRANSFER THEN
    RETURN(c"ATA transfer")

  ELSE
    RETURN(c"unknown")
  ESAC

RETURN(c"unknown")

; Append fixed-width hexadecimal register bytes to a diagnostic row.
CARD FUNC ShellRowHexByte(DOS.FileHandle POINTER output CARD used BYTE value)
  BYTE digit

  digit=value RSH 4
  used=ShellRowByte(output,used,IF digit<10 THEN digit+48 ELSE digit+55 FI)
  digit=value & 15

RETURN(ShellRowByte(output,used,IF digit<10 THEN digit+48 ELSE digit+55 FI))

; Ordinary DOS faults explain filesystem codes; ATA codes use driver context.
PROC ShellMountError(DOS.FileHandle POINTER output CARD used LONGINT error)

  IF error>=DOS.ERROR_NO_FREE_STORE THEN
    BEGIN
      LET count=DOS.Fault(error,NULL,ShellScratch(),SCRATCH_CAPACITY-1)
      IF count>0 THEN
        used=ShellRowBytes(output,used,ShellScratch(),CARD(count))
      FI
    END
  ELSE
    used=ShellRowText(output,used,c"error ")
    used=ShellRowNumber(output,used,error)
  FI

  ShellRowEnd(output,used)

RETURN

; Preserve a failed mount's phase independently of driver lifetime.
CSTRING FUNC ShellMountPhase(BYTE value)

  CASE value OF
  WHEN FSTYPES.MOUNT_CONFIG THEN
    RETURN(c"invalid configuration")

  WHEN FSTYPES.MOUNT_RESOURCES THEN
    RETURN(c"filesystem resources")

  WHEN BLOCKTYPES.ADMIT_ALLOCATE THEN
    RETURN(c"mount allocation")

  WHEN BLOCKTYPES.ADMIT_OPEN THEN
    RETURN(c"device open")

  WHEN BLOCKTYPES.ADMIT_GEOMETRY THEN
    RETURN(c"geometry query")

  WHEN BLOCKTYPES.ADMIT_BYTES THEN
    RETURN(c"sector size mismatch")

  WHEN BLOCKTYPES.ADMIT_COUNT THEN
    RETURN(c"sector count mismatch")

  WHEN BLOCKTYPES.ADMIT_PROTECTED THEN
    RETURN(c"partition/board protected")

  WHEN BLOCKTYPES.ADMIT_DURABLE THEN
    RETURN(c"durable writes unavailable")

  WHEN FSTYPES.MOUNT_BOOT_READ THEN
    RETURN(c"read sector 1")

  WHEN FSTYPES.MOUNT_STATUS THEN
    RETURN(c"disk STATUS")

  WHEN FSTYPES.MOUNT_PERCOM THEN
    RETURN(c"PERCOM GET")

  WHEN FSTYPES.MOUNT_DISCOVERY THEN
    RETURN(c"disk geometry")

  WHEN FSTYPES.MOUNT_RECOGNIZE THEN
    RETURN(c"filesystem recognition")

  WHEN FSTYPES.MOUNT_READ THEN
    RETURN(c"filesystem header read")

  ELSE
    RETURN(c"filesystem startup")
  ESAC

RETURN(c"filesystem startup")

; Explain a generic IDE open rejection using the retained controller and slot.
PROC ShellMountOpenReason(DOS.FileHandle POINTER output BYTE unit)
  IDEPLUS.Diagnostics info
  IDEPLUS.PartitionInfo partition
  CARD used

  used=0
  IDEPLUSDRIVER.Diagnostics(@info)
  used=ShellRowText(output,used,c"MOUNT REASON  =")
  IF info.reason<>IDEPLUS.REASON_NONE THEN
    used=ShellRowText(output,used,ShellIdeReason(info.reason))
  ELSEIF info.state=5 THEN
    used=ShellRowText(output,used,c"controller offline; reset")
  ELSEIF IDEPLUSDRIVER.PartitionStatus(unit,@partition)<>0 THEN
    CASE partition.reason OF
    WHEN IDEPLUS.SLOT_EMPTY THEN
      used=ShellRowText(output,used,c"empty APT slot")
    WHEN IDEPLUS.SLOT_DELETED THEN
      used=ShellRowText(output,used,c"deleted APT slot")
    WHEN IDEPLUS.SLOT_NOT_DOS THEN
      used=ShellRowText(output,used,c"non-DOS APT slot")
    WHEN IDEPLUS.SLOT_INACTIVE THEN
      used=ShellRowText(output,used,c"inactive APT slot")
    WHEN IDEPLUS.SLOT_SECTOR_SIZE THEN
      used=ShellRowText(output,used,c"APT slot is not 512B")
    ELSE
      used=ShellRowText(output,used,c"unit open rejected")
    ESAC
  ELSE
    used=ShellRowText(output,used,c"controller not ready")
  FI

  ShellRowEnd(output,used)
  used=0

RETURN

CSTRING FUNC ShellDiscoveryReason(BYTE reason)

  CASE reason OF
  WHEN FSDISCOVER.BAD_SIZE THEN
    RETURN(c"unsupported sector size")
  WHEN FSDISCOVER.BAD_DENSITY THEN
    RETURN(c"STATUS/PERCOM conflict")
  WHEN FSDISCOVER.BAD_CAPACITY THEN
    RETURN(c"invalid PERCOM capacity")
  WHEN FSDISCOVER.BAD_LENGTH THEN
    RETURN(c"short discovery reply")
  WHEN FSDISCOVER.NO_FALLBACK THEN
    RETURN(c"DD capacity needs PERCOM")
  WHEN FSDISCOVER.BAD_PROFILE THEN
    RETURN(c"profile/geometry conflict")
  ESAC

RETURN(c"none")

; Retained startup/remount failures survive destruction of their mount objects.
PROC ShellMountFailureReport(DOS.FileHandle POINTER output)
  FSINSPECT.Failure failure
  IDEPLUS.PartitionInfo partition
  CARD used
  BYTE index,part

  IF FSINSPECT.LastFailure(@failure)=0 THEN
    RETURN
  FI

  used=0
  used=ShellRowText(output,used,c"MOUNT FAILED  =")
  IF failure.name(0)<>0 THEN
    IF ShellLength(@failure.name(0))>24 THEN
      ShellRowEnd(output,used)
      used=0
    FI

    used=ShellRowText(output,used,CSTRING(@failure.name(0)))
    used=ShellRowByte(output,used,CHAR_COLON)
  ELSE
    used=ShellRowText(output,used,c"filesystem service")
  FI

  ShellRowEnd(output,used)
  used=0
  used=ShellRowText(output,used,c"MOUNT PHASE   =")
  used=ShellRowText(output,used,ShellMountPhase(failure.stage))
  ShellRowEnd(output,used)
  used=0
  used=ShellRowText(output,used,c"MOUNT ERROR   =")
  ShellMountError(output,used,failure.error)
  used=0
  IF failure.name(0)=0 THEN
    RETURN
  FI

  used=ShellRowText(output,used,c"MOUNT DEVICE  =")
  IF failure.backend=BLOCKTYPES.BACKEND_IDEPLUS THEN
    used=ShellRowText(output,used,c"ideplus.device/")
    used=ShellRowNumber(output,used,LONGINT(failure.unit))
  ELSE
    used=ShellRowText(output,used,c"sio.device/D")
    used=ShellRowNumber(output,used,LONGINT(failure.unit-48))
  FI

  ShellRowEnd(output,used)
  used=0
  IF failure.backend=BLOCKTYPES.BACKEND_IDEPLUS
      AND failure.stage=BLOCKTYPES.ADMIT_OPEN THEN
    ShellMountOpenReason(output,failure.unit)
  FI

  IF failure.reason<>0 THEN
    used=ShellRowText(output,0,c"MOUNT REASON  =")
    ShellRowEnd(output,ShellRowText(output,used,ShellDiscoveryReason(failure.reason)))
  FI

  IF failure.stage>=FSTYPES.MOUNT_BOOT_READ OR failure.source<>0 THEN
    used=ShellRowText(output,0,c"MOUNT STATUS  =")
    FOR index=0 TO 3 DO
      used=ShellRowHexByte(output,used,failure.status(index))
      used=ShellRowByte(output,used,ASCII.SPACE)
    OD

    ShellRowEnd(output,used)
    FOR part=0 TO 1 DO
      used=ShellRowText(output,0,c"MOUNT PERCOM  =")
      FOR index=0 TO 5 DO
        used=ShellRowHexByte(output,used,failure.percom(part*6+index))
        used=ShellRowByte(output,used,ASCII.SPACE)
      OD

      ShellRowEnd(output,used)
    OD
  FI

  IF failure.stage=BLOCKTYPES.ADMIT_BYTES OR failure.stage=BLOCKTYPES.ADMIT_COUNT THEN
    used=ShellRowText(output,used,c"  expected ")
    used=ShellRowNumber(output,used,LONGINT(failure.sectors))
    used=ShellRowText(output,used,c" x ")
    used=ShellRowNumber(output,used,LONGINT(failure.bytes))
    used=ShellRowText(output,used,c"B")
    ShellRowEnd(output,used)
    used=0
    IF failure.backend=BLOCKTYPES.BACKEND_IDEPLUS THEN
      IF IDEPLUSDRIVER.PartitionStatus(failure.unit,@partition)<>0
          AND partition.reason=IDEPLUS.SLOT_READY THEN
        used=ShellRowText(output,used,c"  actual   ")
        used=ShellRowNumber(output,used,LONGINT(partition.sectors))
        used=ShellRowText(output,used,c" x ")
        used=ShellRowNumber(output,used,LONGINT(partition.bytes))
        used=ShellRowText(output,used,c"B")
        ShellRowEnd(output,used)
        used=0
      FI
    FI
  FI

RETURN

; Reprint the last observed controller and APT state, with no probes or retries.
PROC ShellIdeReport(DOS.FileHandle POINTER output BYTE showUnattempted)
  IDEPLUS.Diagnostics info
  IDEPLUS.PartitionInfo partition
  CARD used
  BYTE unit

  used=0
  IDEPLUSDRIVER.Diagnostics(@info)
  IF info.attempted=0 THEN
    IF showUnattempted<>0 THEN
      used=ShellRowText(output,used,c"IDE CTRL      =UNATTEMPTED")
      ShellRowEnd(output,used)
      used=0
    FI

    RETURN
  FI

  used=ShellRowText(output,used,c"IDE CTRL      =")
  IF info.controller<>0 THEN
    used=ShellRowText(output,used,c"DETECTED (PBI ID 0)")
    ShellRowEnd(output,used)
    used=0
  ELSEIF info.stage<IDEPLUS.STAGE_CONTROLLER THEN
    used=ShellRowText(output,used,c"NOT CHECKED")
    ShellRowEnd(output,used)
    used=0
  ELSE
    used=ShellRowText(output,used,c"NOT DETECTED (PBI ID 0)")
    ShellRowEnd(output,used)
    used=0
  FI

  used=ShellRowText(output,used,c"IDE PHASE     =")
  used=ShellRowText(output,used,ShellIdePhase(info.stage))
  ShellRowEnd(output,used)
  used=0
  used=ShellRowText(output,used,c"IDE STATE     =")
  used=ShellRowNumber(output,used,LONGINT(info.state))
  used=ShellRowText(output,used,c" GEN ")
  used=ShellRowNumber(output,used,LONGINT(info.generation))
  ShellRowEnd(output,used)
  used=0
  IF info.stage>=IDEPLUS.STAGE_CONTROLLER THEN
    used=ShellRowText(output,used,c"IDE CARD      =$")
    used=ShellRowHexByte(output,used,info.boardStatus)
    ShellRowEnd(output,used)
    used=0
  FI

  IF info.disk<>0 THEN
    used=ShellRowText(output,used,c"IDE SECTORS   =")
    used=ShellRowNumber(output,used,LONGINT(info.sectors))
    ShellRowEnd(output,used)
    used=0
    used=ShellRowText(output,used,c"IDE CAPACITY  =")
    used=ShellRowNumber(output,used,LONGINT(info.sectors RSH 11))
    used=ShellRowText(output,used,c" MiB (512B)")
    ShellRowEnd(output,used)
    used=0
    used=ShellRowText(output,used,c"IDE WRITES    =")
    IF info.durable=0 THEN
      used=ShellRowText(output,used,c"NO DURABLE SUPPORT")
      ShellRowEnd(output,used)
      used=0
    ELSEIF (info.boardStatus & $10)<>0 THEN
      used=ShellRowText(output,used,c"BOARD PROTECTED")
      ShellRowEnd(output,used)
      used=0
    ELSE
      used=ShellRowText(output,used,c"DURABLE")
      ShellRowEnd(output,used)
      used=0
    FI
  ELSE
    used=ShellRowText(output,used,c"IDE DISK      =NOT IDENTIFIED")
    ShellRowEnd(output,used)
    used=0
  FI

  IF info.reason<>IDEPLUS.REASON_NONE THEN
    used=ShellRowText(output,used,c"IDE ERROR     =")
    used=ShellRowText(output,used,ShellIdeReason(info.reason))
    ShellRowEnd(output,used)
    used=0
    IF info.reason=IDEPLUS.REASON_ATA OR info.reason=IDEPLUS.REASON_TIMEOUT
        OR info.reason=IDEPLUS.REASON_DISK_ABSENT THEN
      used=ShellRowText(output,used,c"IDE ATA       =STATUS $")
      used=ShellRowHexByte(output,used,info.status)
      used=ShellRowText(output,used,c" ERROR $")
      used=ShellRowHexByte(output,used,info.ataError)
      ShellRowEnd(output,used)
      used=0
    FI

    IF info.stage=IDEPLUS.STAGE_APT OR info.stage=IDEPLUS.STAGE_TRANSFER THEN
      used=ShellRowText(output,used,c"IDE FAULT LBA =")
      used=ShellRowNumber(output,used,LONGINT(info.lba))
      IF info.slot<>255 THEN
        used=ShellRowText(output,used,c" UNIT ")
        used=ShellRowNumber(output,used,LONGINT(info.slot))
      FI

      ShellRowEnd(output,used)
      used=0
    FI
  FI

  used=ShellRowText(output,used,c"APT STATUS    =")
  IF info.apt<>0 THEN
    used=ShellRowText(output,used,c"VALID")
    ShellRowEnd(output,used)
    used=0
  ELSEIF info.disk=0 THEN
    used=ShellRowText(output,used,c"NOT CHECKED")
    ShellRowEnd(output,used)
    used=0
    RETURN
  ELSE
    used=ShellRowText(output,used,c"FAILED")
    ShellRowEnd(output,used)
    used=0
    RETURN
  FI

  FOR unit=1 TO 15 DO
    IF IDEPLUSDRIVER.PartitionStatus(unit,@partition)<>0
        AND partition.reason<>IDEPLUS.SLOT_EMPTY THEN
      used=ShellRowText(output,used,c"APT UNIT      =")
      used=ShellRowNumber(output,used,LONGINT(unit))
      IF partition.reason=IDEPLUS.SLOT_READY THEN
        IF (partition.flags & IDEPLUS.FLAG_READONLY)<>0 THEN
          used=ShellRowText(output,used,c" RO 512B")
          ShellRowEnd(output,used)
          used=0
        ELSE
          used=ShellRowText(output,used,c" RW 512B")
          ShellRowEnd(output,used)
          used=0
        FI

        used=ShellRowText(output,used,c"  LBA ")
        used=ShellRowNumber(output,used,LONGINT(partition.start))
        used=ShellRowText(output,used,c" SECTORS ")
        used=ShellRowNumber(output,used,LONGINT(partition.sectors))
        ShellRowEnd(output,used)
        used=0
      ELSE
        used=ShellRowText(output,used,c" SKIPPED: ")
        CASE partition.reason OF
        WHEN IDEPLUS.SLOT_DELETED THEN
          used=ShellRowText(output,used,c"deleted")
        WHEN IDEPLUS.SLOT_NOT_DOS THEN
          used=ShellRowText(output,used,c"non-DOS")
        WHEN IDEPLUS.SLOT_INACTIVE THEN
          used=ShellRowText(output,used,c"inactive")
        ELSE
          used=ShellRowText(output,used,c"not 512B")
        ESAC

        ShellRowEnd(output,used)
        used=0
      FI
    FI

    IF shell.done<>0 THEN
      EXIT
    FI
  OD

RETURN

; Output may replace IoErr, but must not erase the mount operation's cause.
PROC ShellMountFailure(DOS.FileHandle POINTER output)

  LET saved=DOS.IoErr()
  ShellMountFailureReport(output)
  DOS.SetIoErr(saved)

RETURN

; Verbose boot and explicit diagnostics share the same observational report.
PROC ShellIdeDiagnostics(DOS.FileHandle POINTER output BYTE showUnattempted)

  LET saved=DOS.IoErr()
  ShellIdeReport(output,showUnattempted)
  DOS.SetIoErr(saved)

RETURN
