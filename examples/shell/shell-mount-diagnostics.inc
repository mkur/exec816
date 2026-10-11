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

  WHEN IDEPLUS.REASON_VERIFY THEN
    RETURN(c"write verification mismatch")

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

; Register bytes use fixed hexadecimal width for reproducible hardware reports.
PROC ShellHexByte(DOS.FileHandle POINTER output BYTE value)
  BYTE digit

  LET buffer=ShellDrawBuffer()
  digit=value RSH 4
  buffer(0)=IF digit<10 THEN digit+48 ELSE digit+55 FI
  digit=value & 15
  buffer(1)=IF digit<10 THEN digit+48 ELSE digit+55 FI
  ShellWrite(output,buffer,2)

RETURN

; Ordinary DOS faults explain filesystem codes; ATA codes use driver context.
PROC ShellMountError(DOS.FileHandle POINTER output LONGINT error)

  IF error>=DOS.ERROR_NO_FREE_STORE THEN
    BEGIN
      LET count=DOS.Fault(error,NULL,ShellScratch(),SCRATCH_CAPACITY-1)
      IF count>0 THEN
        ShellWrite(output,ShellScratch(),CARD(count))
      FI
    END
  ELSE
    ShellText(output,c"error ")
    ShellNumber(output,error)
  FI

  ShellByte(output,ASCII.LF)

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

  IDEPLUSDRIVER.Diagnostics(@info)
  ShellText(output,c"MOUNT REASON  =")
  IF info.reason<>IDEPLUS.REASON_NONE THEN
    ShellText(output,ShellIdeReason(info.reason))
  ELSEIF info.state=5 THEN
    ShellText(output,c"controller offline; reset")
  ELSEIF IDEPLUSDRIVER.PartitionStatus(unit,@partition)<>0 THEN
    CASE partition.reason OF
    WHEN IDEPLUS.SLOT_EMPTY THEN
      ShellText(output,c"empty APT slot")
    WHEN IDEPLUS.SLOT_DELETED THEN
      ShellText(output,c"deleted APT slot")
    WHEN IDEPLUS.SLOT_NOT_DOS THEN
      ShellText(output,c"non-DOS APT slot")
    WHEN IDEPLUS.SLOT_INACTIVE THEN
      ShellText(output,c"inactive APT slot")
    WHEN IDEPLUS.SLOT_SECTOR_SIZE THEN
      ShellText(output,c"APT slot is not 512B")
    ELSE
      ShellText(output,c"unit open rejected")
    ESAC
  ELSE
    ShellText(output,c"controller not ready")
  FI

  ShellByte(output,ASCII.LF)

RETURN

; Retained startup/remount failures survive destruction of their mount objects.
PROC ShellMountFailureReport(DOS.FileHandle POINTER output)
  FSINSPECT.Failure failure
  IDEPLUS.PartitionInfo partition

  IF FSINSPECT.LastFailure(@failure)=0 THEN
    RETURN
  FI

  ShellText(output,c"MOUNT FAILED  =")
  IF failure.name(0)<>0 THEN
    IF ShellLength(@failure.name(0))>24 THEN
      ShellByte(output,ASCII.LF)
    FI

    ShellText(output,CSTRING(@failure.name(0)))
    ShellByte(output,CHAR_COLON)
  ELSE
    ShellText(output,c"filesystem service")
  FI

  ShellByte(output,ASCII.LF)
  ShellText(output,c"MOUNT PHASE   =")
  ShellText(output,ShellMountPhase(failure.stage))
  ShellByte(output,ASCII.LF)
  ShellText(output,c"MOUNT ERROR   =")
  ShellMountError(output,failure.error)
  IF failure.name(0)=0 THEN
    RETURN
  FI

  ShellText(output,c"MOUNT DEVICE  =")
  IF failure.backend=BLOCKTYPES.BACKEND_IDEPLUS THEN
    ShellText(output,c"ideplus.device/")
    ShellNumber(output,LONGINT(failure.unit))
  ELSE
    ShellText(output,c"sio.device/D")
    ShellNumber(output,LONGINT(failure.unit-48))
  FI

  ShellByte(output,ASCII.LF)
  IF failure.backend=BLOCKTYPES.BACKEND_IDEPLUS
      AND failure.stage=BLOCKTYPES.ADMIT_OPEN THEN
    ShellMountOpenReason(output,failure.unit)
  FI

  IF failure.stage=BLOCKTYPES.ADMIT_BYTES OR failure.stage=BLOCKTYPES.ADMIT_COUNT THEN
    ShellText(output,c"  expected ")
    ShellNumber(output,LONGINT(failure.sectors))
    ShellText(output,c" x ")
    ShellNumber(output,LONGINT(failure.bytes))
    ShellText(output,c"B\n")
    IF failure.backend=BLOCKTYPES.BACKEND_IDEPLUS THEN
      IF IDEPLUSDRIVER.PartitionStatus(failure.unit,@partition)<>0
          AND partition.reason=IDEPLUS.SLOT_READY THEN
        ShellText(output,c"  actual   ")
        ShellNumber(output,LONGINT(partition.sectors))
        ShellText(output,c" x ")
        ShellNumber(output,LONGINT(partition.bytes))
        ShellText(output,c"B\n")
      FI
    FI
  FI

RETURN

; Reprint the last observed controller and APT state, with no probes or retries.
PROC ShellIdeReport(DOS.FileHandle POINTER output BYTE showUnattempted)
  IDEPLUS.Diagnostics info
  IDEPLUS.PartitionInfo partition
  BYTE unit

  IDEPLUSDRIVER.Diagnostics(@info)
  IF info.attempted=0 THEN
    IF showUnattempted<>0 THEN
      ShellText(output,c"IDE CTRL      =UNATTEMPTED\n")
    FI

    RETURN
  FI

  ShellText(output,c"IDE CTRL      =")
  IF info.controller<>0 THEN
    ShellText(output,c"DETECTED (PBI ID 0)\n")
  ELSEIF info.stage<IDEPLUS.STAGE_CONTROLLER THEN
    ShellText(output,c"NOT CHECKED\n")
  ELSE
    ShellText(output,c"NOT DETECTED (PBI ID 0)\n")
  FI

  ShellText(output,c"IDE PHASE     =")
  ShellText(output,ShellIdePhase(info.stage))
  ShellByte(output,ASCII.LF)
  ShellText(output,c"IDE STATE     =")
  ShellNumber(output,LONGINT(info.state))
  ShellText(output,c" GEN ")
  ShellNumber(output,LONGINT(info.generation))
  ShellByte(output,ASCII.LF)
  IF info.stage>=IDEPLUS.STAGE_CONTROLLER THEN
    ShellText(output,c"IDE CARD      =$")
    ShellHexByte(output,info.boardStatus)
    ShellByte(output,ASCII.LF)
  FI

  IF info.disk<>0 THEN
    ShellText(output,c"IDE SECTORS   =")
    ShellNumber(output,LONGINT(info.sectors))
    ShellByte(output,ASCII.LF)
    ShellText(output,c"IDE CAPACITY  =")
    ShellNumber(output,LONGINT(info.sectors RSH 11))
    ShellText(output,c" MiB (512B)\n")
    ShellText(output,c"IDE WRITES    =")
    IF info.durable=0 THEN
      ShellText(output,c"NO DURABLE SUPPORT\n")
    ELSEIF (info.boardStatus & $10)<>0 THEN
      ShellText(output,c"BOARD PROTECTED\n")
    ELSE
      ShellText(output,c"DURABLE\n")
    FI
  ELSE
    ShellText(output,c"IDE DISK      =NOT IDENTIFIED\n")
  FI

  IF info.reason<>IDEPLUS.REASON_NONE THEN
    ShellText(output,c"IDE ERROR     =")
    ShellText(output,ShellIdeReason(info.reason))
    ShellByte(output,ASCII.LF)
    IF info.reason=IDEPLUS.REASON_ATA OR info.reason=IDEPLUS.REASON_TIMEOUT
        OR info.reason=IDEPLUS.REASON_DISK_ABSENT THEN
      ShellText(output,c"IDE ATA       =STATUS $")
      ShellHexByte(output,info.status)
      ShellText(output,c" ERROR $")
      ShellHexByte(output,info.ataError)
      ShellByte(output,ASCII.LF)
    FI

    IF info.stage=IDEPLUS.STAGE_APT OR info.stage=IDEPLUS.STAGE_TRANSFER THEN
      ShellText(output,c"IDE FAULT LBA =")
      ShellNumber(output,LONGINT(info.lba))
      IF info.slot<>255 THEN
        ShellText(output,c" UNIT ")
        ShellNumber(output,LONGINT(info.slot))
      FI

      ShellByte(output,ASCII.LF)
    FI
  FI

  ShellText(output,c"APT STATUS    =")
  IF info.apt<>0 THEN
    ShellText(output,c"VALID\n")
  ELSEIF info.disk=0 THEN
    ShellText(output,c"NOT CHECKED\n")
    RETURN
  ELSE
    ShellText(output,c"FAILED\n")
    RETURN
  FI

  FOR unit=1 TO 15 DO
    IF IDEPLUSDRIVER.PartitionStatus(unit,@partition)<>0
        AND partition.reason<>IDEPLUS.SLOT_EMPTY THEN
      ShellText(output,c"APT UNIT      =")
      ShellNumber(output,LONGINT(unit))
      IF partition.reason=IDEPLUS.SLOT_READY THEN
        IF (partition.flags & IDEPLUS.FLAG_READONLY)<>0 THEN
          ShellText(output,c" RO 512B\n")
        ELSE
          ShellText(output,c" RW 512B\n")
        FI

        ShellText(output,c"  LBA ")
        ShellNumber(output,LONGINT(partition.start))
        ShellText(output,c" SECTORS ")
        ShellNumber(output,LONGINT(partition.sectors))
        ShellByte(output,ASCII.LF)
      ELSE
        ShellText(output,c" SKIPPED: ")
        CASE partition.reason OF
        WHEN IDEPLUS.SLOT_DELETED THEN
          ShellText(output,c"deleted")
        WHEN IDEPLUS.SLOT_NOT_DOS THEN
          ShellText(output,c"non-DOS")
        WHEN IDEPLUS.SLOT_INACTIVE THEN
          ShellText(output,c"inactive")
        ELSE
          ShellText(output,c"not 512B")
        ESAC

        ShellByte(output,ASCII.LF)
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
