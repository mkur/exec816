; A disk binding prevents filesystem admission and existing users from racing
; an image change. The control binding already excludes other Fuji clients.
BYTE FUNC ClaimDisk()

  phase=c"drive open (unmount first)"
  wireError=SIO.Open(drive,SIO.SIO_OPEN_EXCLUSIVE,BYTE POINTER(@disk))
  IF wireError<>0 THEN
    cause=LONGINT(wireError)
    RETURN(0)
  FI

  diskOpen=1

RETURN(1)

BYTE FUNC DriveResult(CSTRING description)

  ; A collected successful mutation wins over a late BREAK. Suppress its
  ; optional report rather than turn completion into cancellation.
  IF COMMAND.BreakPending()<>0 THEN
    RETURN(1)
  FI

  StartRow()
  Text(c"D")
  Number(LONGCARD(drive-DRIVE_FIRST+1))
  Text(c": ")
  Text(description)

RETURN(Emit())

; There is no firmware transaction across set-path and attach. Retain the
; configured-state distinction if the second operation fails.
BYTE FUNC Attach()
  CARD mode,index

  IF ClaimDisk()=0 THEN
    RETURN(0)
  FI

  IF Frame(FUJINET.CMD_DISKS,FUJINET.DISK_TABLE_BYTES,SIO.SIODIR_READ,
      0,0,c"disk slots")=0 THEN
    RETURN(0)
  FI

  index=(drive-DRIVE_FIRST)*FUJINET.DISK_BYTES
  IF scratch(index+FUJINET.DISK_FILE)<>0 THEN
    cause=COMMAND.ERROR_OBJECT_IN_USE
    RETURN(0)
  FI

  IF Frame(FUJINET.CMD_HOSTS,FUJINET.HOST_TABLE_BYTES,SIO.SIODIR_READ,
      0,0,c"host slots")=0 THEN
    RETURN(0)
  FI

  IF ValidText(@scratch(host*FUJINET.HOST_BYTES),FUJINET.HOST_BYTES)=0 THEN
    RETURN(0)
  FI

  IF scratch(host*FUJINET.HOST_BYTES)=0 THEN
    cause=COMMAND.ERROR_OBJECT_NOT_FOUND
    RETURN(0)
  FI

  IF Frame(FUJINET.CMD_MOUNT_HOST,0,SIO.SIODIR_NONE,host,0,
      c"host mount")=0 THEN
    RETURN(0)
  FI

  PathFrame(CSTRING(BYTE POINTER(values(4))))

  mode=IF values(5)=0 THEN FUJINET.MODE_READ ELSE FUJINET.MODE_WRITE FI
  IF Frame(FUJINET.CMD_SET_PATH,FUJINET.PATH_BYTES,SIO.SIODIR_WRITE,
      drive-DRIVE_FIRST,(host LSH 4) OR mode,c"image configuration")=0 THEN
    RETURN(0)
  FI

  committed=1
  IF Frame(FUJINET.CMD_ATTACH,0,SIO.SIODIR_NONE,drive-DRIVE_FIRST,mode,
      c"image attach (slot configured)")=0 THEN
    RETURN(0)
  FI

  IF mode=FUJINET.MODE_READ THEN
    RETURN(DriveResult(c"image attached RO"))
  FI

RETURN(DriveResult(c"image attached RW"))

BYTE FUNC Eject()

  IF ClaimDisk()=0 THEN
    RETURN(0)
  FI

  IF Frame(FUJINET.CMD_EJECT,0,SIO.SIODIR_NONE,drive-DRIVE_FIRST,0,
      c"image eject")=0 THEN
    RETURN(0)
  FI

RETURN(DriveResult(c"image ejected"))
