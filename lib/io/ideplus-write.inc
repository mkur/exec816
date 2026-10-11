; Cache-free media is durable after terminal status; cached media must flush.
BYTE FUNC Durability(CARD POINTER words)

  IF (words(82) & $20)=0 THEN
    RETURN(1)
  FI
  IF (words(83) & $d000)=$5000 THEN
    RETURN(2)
  FI

RETURN(0)

; Flush is required only when IDENTIFY advertises a volatile write cache.
BYTE FUNC FlushPhysical()

  LET c=Control()
  IF c.durable=1 THEN
    RETURN(0)
  FI
  IF c.durable<>2 THEN
    RETURN(IDEPLUS.ERROR_UNSUPPORTED)
  FI

  LET error=Ready(0,0)
  IF error<>0 THEN
    RETURN(error)
  FI
  IDEPLUSNATIVE.WriteRegister(IDEPLUS.REG_COMMAND,IDEPLUS.ATA_FLUSH)

RETURN(Ready(0,0))

; Unit protection includes APT policy, the board switch and durable admission.
CARD FUNC AccessFlags(Partition POINTER partition)
  CARD flags

  LET c=Control()
  flags=0
  IF c.durable<>0 THEN
    flags=IDEPLUS.FLAG_DURABLE
  FI
  IF partition.number=0 OR partition.flags<>0 OR c.durable=0
      OR (IDEPLUSNATIVE.ReadRegister(IDEPLUS.REG_CARD) & $10)<>0 THEN
    flags=flags OR IDEPLUS.FLAG_READONLY
  FI

RETURN(flags)

; Drain one bounded ATA write and settle any required cache flush.
BYTE FUNC WriteLogical(Partition POINTER partition EXEC.IOStdReq POINTER request)
  BYTE error,index,count

  LET bus=DriverBus POINTER(ADDRESS(IDEMETA.BUS))
  IF (AccessFlags(partition) & IDEPLUS.FLAG_READONLY)<>0 THEN
    RETURN(IDEPLUS.ERROR_PROTECTED)
  FI

  LET sector=partition.start+request.io_Offset
  error=Ready(0,0)
  IF error<>0 THEN
    RETURN(error)
  FI
  IF bus.cancelled<>0 THEN
    RETURN(BYTE(EXEC.IOERR_ABORTED))
  FI
  count=BYTE(request.io_Length RSH 9)
  AddressRange(sector,count)
  EXEC.Forbid()
  IF bus.cancelled<>0 THEN
    EXEC.Permit()
    RETURN(BYTE(EXEC.IOERR_ABORTED))
  FI
  bus.phase=3
  IDEPLUSNATIVE.WriteRegister(IDEPLUS.REG_COMMAND,IDEPLUS.ATA_WRITE)
  EXEC.Permit()
  FOR index=0 TO count-1 DO
    error=Ready($08,0)
    IF error<>0 THEN
      RETURN(error)
    FI
    IDEPLUSNATIVE.WriteWords(request.io_Data+(SIZE(index) LSH 9))
  OD
  error=Ready(0,0)
  IF error<>0 THEN
    RETURN(error)
  FI

RETURN(FlushPhysical())
