INCLUDE "command-write.inc"
INCLUDE "command-files.inc"

CONST TRANSFER_BYTES=512
BYTE ARRAY transferBuffer(TRANSFER_BYTES)

; Append is an ordinary update open followed by Seek; Close still consumes a
; failed output handle, so retain the seek error before releasing it.
BYTE POINTER FUNC CommandOutput(ADDRESS name BYTE append)

  IF CommandReady()=0 THEN
    RETURN(NULL)
  FI

  LET mode=IF append<>0 THEN COMMAND.MODE_READWRITE ELSE COMMAND.MODE_NEWFILE FI
  LET output=COMMAND.Open(BYTE POINTER(name),mode)
  IF output=NULL THEN
    RETURN(NULL)
  FI

  IF append<>0 THEN
    IF COMMAND.Seek(output,0,COMMAND.OFFSET_END)<0 THEN
      IF COMMAND.IoErr()=0 THEN
        COMMAND.SetIoErr(COMMAND.ERROR_SEEK_ERROR)
      FI

      CommandFinish(output,1,COMMAND.RETURN_ERROR)
      RETURN(NULL)
    FI
  FI

RETURN(output)

; Copy counted binary chunks, optionally mirroring to a borrowed stream. A
; committed read prefix is forwarded before reporting its saved causal error.
LONGINT FUNC CommandTransfer(BYTE POINTER input,output,mirror)

  DO
    BEGIN
      IF CommandReady()=0 THEN
        RETURN(COMMAND.RETURN_ERROR)
      FI

      LET count=COMMAND.Read(input,transferBuffer,TRANSFER_BYTES)
      LET cause=COMMAND.IoErr()
      IF count<0 OR count>TRANSFER_BYTES THEN
        COMMAND.SetIoErr(IF cause<>0 THEN cause
            ELSE LONGINT(COMMAND.ERROR_BAD_STREAM_NAME) FI)
        RETURN(COMMAND.RETURN_ERROR)
      FI

      IF count=0 THEN
        RETURN(IF cause=0 THEN COMMAND.RETURN_OK ELSE COMMAND.RETURN_ERROR FI)
      FI

      IF COMMAND.WriteAll(output,transferBuffer,count)=0 THEN
        IF cause<>0 THEN
          COMMAND.SetIoErr(cause)
        FI

        RETURN(COMMAND.RETURN_ERROR)
      FI

      IF mirror<>NULL THEN
        IF COMMAND.WriteAll(mirror,transferBuffer,count)=0 THEN
          IF cause<>0 THEN
            COMMAND.SetIoErr(cause)
          FI

          RETURN(COMMAND.RETURN_ERROR)
        FI
      FI

      IF cause<>0 THEN
        COMMAND.SetIoErr(cause)
        RETURN(COMMAND.RETURN_ERROR)
      FI
    END
  OD

RETURN(COMMAND.RETURN_OK)
