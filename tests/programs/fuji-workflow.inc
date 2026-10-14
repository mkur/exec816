PROC Pulse()

  WHILE peerStop=0 DO
    peerTurns==+1
    EXEC.Yield()
  OD

  peerDone=1

RETURN

; A host fixture connects the selected ATR to the emulator's disk peripheral
; only after FUJI's serial attachment has completed and before filesystem I/O.
PROC ChangeMedia(BYTE selection)

  mediaPhase=selection
  WHILE mediaPhase<>0 DO
    EXEC.Yield()
  OD

RETURN

PROC ReadPayload(BYTE expected)
  CARD index

  LET file=DOS.Open(BYTE POINTER(c"DATA:SWAP.BIN"),DOS.MODE_OLDFILE)
  Require(file<>NULL)
  Require(DOS.Read(file,bytes,64)=64)
  FOR index=0 TO 63 DO
    Require(bytes(index)=expected)
  OD

  Require(DOS.Close(file)<>0)

RETURN

PROC Workflow()
  CARD index

  LET pulseTask=EXEC.CreateTask(c"fuji-peer",0,@Pulse,1024)
  Require(pulseTask<>NULL)
  Run(c"ATTACH D2: HOST 1 IMAGE /first.atr",c"RAM:ATTACH",0,0)
  ChangeMedia(1)
  mountSpec.drive=2
  mountSpec.profile=SIO.SIO_PROFILE_GENERIC57600
  mountSpec.format=testFormat
  mountSpec.access=0
  Require(DOS.MountVolume(BYTE POINTER(c"DATA"),@mountSpec)<>0)
  Require(DOS.GetVolume(2,@volume)<>0 AND volume.sectorBytes=wantedBytes)
  ReadPayload($55)
  Require(DOS.Open(BYTE POINTER(c"DATA:NEW.BIN"),DOS.MODE_NEWFILE)=NULL AND
      DOS.IoErr()=DOS.ERROR_DISK_WRITE_PROTECTED)
  Peer(0)
  LET changes=snapshot(2)+snapshot(4)
  Run(c"EJECT D2:",c"RAM:BUSY",10,EXEC.IOERR_UNITBUSY)
  Run(c"ATTACH D2: HOST 1 IMAGE /second.atr",c"RAM:BUSY",10,
      EXEC.IOERR_UNITBUSY)
  Peer(0)
  Require(snapshot(2)+snapshot(4)=changes)
  Require(DOS.UnmountVolume(BYTE POINTER(c"DATA"))<>0)
  Run(c"EJECT D2:",c"RAM:EJECT",0,0)
  Run(c"ATTACH D2: HOST 2 IMAGE /second.atr READWRITE",c"RAM:ATTACH",0,0)
  ChangeMedia(2)
  mountSpec.access=DOS.MOUNT_READWRITE
  Require(DOS.MountVolume(BYTE POINTER(c"DATA"),@mountSpec)<>0)
  ReadPayload($aa)
  LET output=DOS.Open(BYTE POINTER(c"DATA:NEW.BIN"),DOS.MODE_NEWFILE)
  Require(output<>NULL)
  FOR index=0 TO 63 DO
    bytes(index)=BYTE(index+1)
  OD

  Require(DOS.Write(output,bytes,64)=64)
  Require(DOS.Close(output)<>0)
  Require(DOS.UnmountVolume(BYTE POINTER(c"DATA"))<>0)
  mountSpec.access=0
  Require(DOS.MountVolume(BYTE POINTER(c"DATA"),@mountSpec)<>0)
  LET readback=DOS.Open(BYTE POINTER(c"DATA:NEW.BIN"),DOS.MODE_OLDFILE)
  Require(readback<>NULL)
  Require(DOS.Read(readback,bytes,64)=64)
  FOR index=0 TO 63 DO
    Require(bytes(index)=BYTE(index+1))
  OD

  Require(DOS.Close(readback)<>0)
  Require(DOS.UnmountVolume(BYTE POINTER(c"DATA"))<>0)
  Run(c"EJECT D2:",c"RAM:EJECT",0,0)
  LET unrelated=DOS.Open(BYTE POINTER(c"SYS:FUJI"),DOS.MODE_OLDFILE)
  Require(unrelated<>NULL AND DOS.Read(unrelated,bytes,64)=64)
  Require(DOS.Close(unrelated)<>0)
  Run(c"STATUS",c"RAM:STATUS",0,0)
  Require(peerTurns>100)
  peerStop=1
  WHILE peerDone=0 DO
    EXEC.Yield()
  OD

  EXECTASKS.Sleep(1)

RETURN
