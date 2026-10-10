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

; Serialize physical RMW, durable status and verification as one request owner.
BYTE FUNC WriteLogical(Partition POINTER partition EXEC.IOStdReq POINTER request)
  BYTE error
  CARD index
  LET bus=DriverBus POINTER(ADDRESS(IDEMETA.BUS))

  LET c=Control()
  IF (AccessFlags(partition) & IDEPLUS.FLAG_READONLY)<>0 THEN
    RETURN(IDEPLUS.ERROR_PROTECTED)
  FI
  LET sector=PhysicalSector(partition,request.io_Offset)
  error=ReadPhysical(sector)
  IF error<>0 THEN
    RETURN(error)
  FI
  IF bus.cancelled<>0 THEN
    RETURN(BYTE(EXEC.IOERR_ABORTED))
  FI
  FOR index=0 TO CARD(request.io_Length)-1 DO
    c.buffer(PackedIndex(partition,request.io_Offset,index))=request.io_Data(index)
  OD
  AddressSector(sector)
  EXEC.Forbid()
  IF bus.cancelled<>0 THEN
    EXEC.Permit()
    RETURN(BYTE(EXEC.IOERR_ABORTED))
  FI
  bus.phase=3
  IDEPLUSNATIVE.WriteRegister(IDEPLUS.REG_COMMAND,IDEPLUS.ATA_WRITE)
  EXEC.Permit()
  error=Ready($08,0)
  IF error<>0 THEN
    RETURN(error)
  FI
  IDEPLUSNATIVE.WriteWords(c.buffer)
  error=Ready(0,0)
  IF error<>0 THEN
    RETURN(error)
  FI
  error=FlushPhysical()
  IF error<>0 THEN
    RETURN(error)
  FI
  error=ReadPhysical(sector)
  IF error<>0 THEN
    RETURN(error)
  FI
  FOR index=0 TO CARD(request.io_Length)-1 DO
    IF c.buffer(PackedIndex(partition,request.io_Offset,index))<>request.io_Data(index) THEN
      RETURN(IDEPLUS.ERROR_VERIFY)
    FI
  OD

RETURN(0)
