; Reject unrepresentable C addresses before converting to native pointers.
LONGINT FUNC CWrite(LONGCARD file,buffer LONGINT length)

  IF file>$ffffff OR buffer>$ffffff THEN
    BEGIN
      LET ignored=DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
      RETURN(-1)
    END
  FI

RETURN(DOS.Write(DOS.FileHandle POINTER(ADDRESS(file)),
    BYTE POINTER(ADDRESS(buffer)),length))

LONGCARD FUNC COpen(LONGCARD name,mode,unused)

RETURN(LONGCARD(ADDRESS(DOS.Open(BYTE POINTER(ADDRESS(name)),LONGINT(mode)))))

LONGINT FUNC CClose(LONGCARD file,unused,unused2)

RETURN(DOS.Close(DOS.FileHandle POINTER(ADDRESS(file))))

LONGINT FUNC CRead(LONGCARD file,buffer LONGINT length)

RETURN(DOS.Read(DOS.FileHandle POINTER(ADDRESS(file)),
    BYTE POINTER(ADDRESS(buffer)),length))

LONGCARD FUNC CLock(LONGCARD name,mode,unused)

RETURN(LONGCARD(ADDRESS(DOS.Lock(BYTE POINTER(ADDRESS(name)),LONGINT(mode)))))

PROC CUnLock(LONGCARD lock,unused,unused2)

  DOS.UnLock(DOS.FileLock POINTER(ADDRESS(lock)))

RETURN

LONGINT FUNC CExamine(LONGCARD lock,info,unused)

RETURN(DOS.Examine(DOS.FileLock POINTER(ADDRESS(lock)),
    DOS.FileInfoBlock POINTER(ADDRESS(info))))

LONGINT FUNC CExamineExact(LONGCARD lock,info,unused)

RETURN(DOS.ExamineExact(DOS.FileLock POINTER(ADDRESS(lock)),
    DOS.FileInfoBlock POINTER(ADDRESS(info))))

LONGINT FUNC CExNext(LONGCARD lock,info,unused)

RETURN(DOS.ExNext(DOS.FileLock POINTER(ADDRESS(lock)),
    DOS.FileInfoBlock POINTER(ADDRESS(info))))

LONGINT FUNC CSeek(LONGCARD file LONGINT position,mode)

RETURN(DOS.Seek(DOS.FileHandle POINTER(ADDRESS(file)),position,mode))

; A launched command owns cloned resources and an independent cancellation scope.
INCLUDE "program-start.inc"

BYTE FUNC CMarshalStart(LONGCARD descriptor NativeProgramStart POINTER native)

  native.arguments=NULL
  native.input=NULL
  native.output=NULL
  native.directory=NULL
  native.console=NULL
  native.length=0
  native.minimumStack=0
  IF descriptor=0 THEN
    RETURN(1)
  FI

  IF descriptor>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

  LET source=CProgramStart POINTER(ADDRESS(descriptor))
  IF source.arguments>$ffffff OR source.input>$ffffff
      OR source.output>$ffffff OR source.directory>$ffffff
      OR source.console>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

  native.arguments=BYTE POINTER(ADDRESS(source.arguments))
  native.input=BYTE POINTER(ADDRESS(source.input))
  native.output=BYTE POINTER(ADDRESS(source.output))
  native.directory=BYTE POINTER(ADDRESS(source.directory))
  native.console=BYTE POINTER(ADDRESS(source.console))
  native.length=source.length
  native.minimumStack=source.minimumStack

RETURN(1)

LONGCARD FUNC CLoadProgram(LONGCARD name,unused,unused2)

  IF name>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

RETURN(LONGCARD(ADDRESS(PROGRAMFILE.Load(BYTE POINTER(ADDRESS(name))))))

LONGCARD FUNC CLoadBegin(LONGCARD path,unused,unused2)

RETURN(LONGCARD(ADDRESS(PROGRAMLOAD.Begin(BYTE POINTER(ADDRESS(path))))))

LONGINT FUNC CLoadStep(LONGCARD job,unused,unused2)

RETURN(LONGINT(PROGRAMLOAD.Advance(PROGRAMLOAD.Job POINTER(ADDRESS(job)))))

LONGCARD FUNC CLoadTake(LONGCARD job,unused,unused2)

RETURN(LONGCARD(ADDRESS(PROGRAMLOAD.Take(PROGRAMLOAD.Job POINTER(ADDRESS(job))))))

LONGINT FUNC CLoadCancel(LONGCARD job,unused,unused2)

  PROGRAMLOAD.Cancel(PROGRAMLOAD.Job POINTER(ADDRESS(job)))

RETURN(1)

LONGINT FUNC CReleaseProgram(LONGCARD image,unused,unused2)

  IF image>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

  PROGRAM.Unload(PROGRAMIMAGE.Image POINTER(ADDRESS(image)))

RETURN(1)

LONGCARD FUNC CStartLoaded(LONGCARD image,descriptor,unused)
  NativeProgramStart specification

  IF image>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

  IF CMarshalStart(descriptor,@specification)=0 THEN
    RETURN(0)
  FI

RETURN(PROCESS.StartConfigured(BYTE POINTER(ADDRESS(image)),
    BYTE POINTER(@specification)))

; Drop exactly the temporary load reference; execution belongs to Collect.
LONGCARD FUNC CStartProgram(LONGCARD name,descriptor,unused)

  LET image=CLoadProgram(name,0,0)
  IF image=0 THEN
    RETURN(0)
  FI

  LET identity=CStartLoaded(image,descriptor,0)
  LET error=DOS.IoErr()
  CReleaseProgram(image,0,0)
  DOS.SetIoErr(error)

RETURN(identity)

LONGINT FUNC CCollectProgram(LONGCARD identity,outcome,unused)

RETURN(PROCESS.Collect(identity,PROCESS.Result POINTER(ADDRESS(outcome))))

LONGINT FUNC CBreakProgram(LONGCARD identity,unused,unused2)

RETURN(LONGINT(PROCESS.RequestStop(identity)))

LONGINT FUNC CWaitProgram(LONGCARD identity,outcome,unused)

RETURN(PROCESS.Wait(identity,PROCESS.Result POINTER(ADDRESS(outcome))))

LONGCARD FUNC CGetArgStr(LONGCARD unused,unused2,unused3)

RETURN(LONGCARD(ADDRESS(PROCESS.GetArgStr())))

LONGCARD FUNC CProgramMask(LONGCARD identity,unused,unused2)

RETURN(PROCESS.CompletionMask(identity))

LONGCARD FUNC CCreateDir(LONGCARD name,unused,unused2)

RETURN(LONGCARD(ADDRESS(DOS.CreateDir(BYTE POINTER(ADDRESS(name))))))

LONGINT FUNC CRename(LONGCARD oldName,newName,unused)

RETURN(DOS.Rename(BYTE POINTER(ADDRESS(oldName)),BYTE POINTER(ADDRESS(newName))))

LONGINT FUNC CDeleteFile(LONGCARD name,unused,unused2)

RETURN(DOS.DeleteFile(BYTE POINTER(ADDRESS(name))))

LONGINT FUNC CMountVolume(LONGCARD name,spec,unused)

  IF name>$ffffff OR spec>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

RETURN(DOS.MountVolume(BYTE POINTER(ADDRESS(name)),
    DOS.SioMountSpec POINTER(ADDRESS(spec))))

LONGINT FUNC CUnmountVolume(LONGCARD name,unused,unused2)

  IF name>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

RETURN(DOS.UnmountVolume(BYTE POINTER(ADDRESS(name))))

; Preserve full-width address checks at the C/native boundary only.
LONGINT FUNC CExNextBatch(LONGCARD lock,info,batch)

  IF lock>$ffffff OR info>$ffffff OR batch>$ffffff THEN
    DOS.SetIoErr(DOS.ERROR_BAD_NUMBER)
    RETURN(0)
  FI

RETURN(DOS.ExNextBatch(DOS.FileLock POINTER(ADDRESS(lock)),
    DOS.FileInfoBlock POINTER(ADDRESS(info)),DOS.DirBatch POINTER(ADDRESS(batch))))

; Bind once; each operation still uses the current Task's DOS context.
PROC BindDos(BYTE unused)

  LET entries=ADDRESS POINTER(C_EXECDOSENTRIES)
  entries(0)=ADDRESS(@DOS.Output)
  entries(1)=ADDRESS(@CWrite)
  entries(2)=ADDRESS(@COpen)
  entries(3)=ADDRESS(@CClose)
  entries(4)=ADDRESS(@CRead)
  entries(5)=ADDRESS(@CLock)
  entries(6)=ADDRESS(@CUnLock)
  entries(7)=ADDRESS(@CExamine)
  entries(8)=ADDRESS(@CExNext)
  entries(9)=ADDRESS(@DOS.IoErr)
  entries(10)=ADDRESS(@CSeek)
  entries(11)=ADDRESS(@DOS.ReleaseContext)
  entries(12)=ADDRESS(@CStartProgram)
  entries(13)=ADDRESS(@CCollectProgram)
  entries(14)=ADDRESS(@CBreakProgram)
  entries(15)=ADDRESS(@CWaitProgram)
  entries(16)=ADDRESS(@CGetArgStr)
  entries(17)=ADDRESS(@CProgramMask)
  entries(18)=ADDRESS(@CCreateDir)
  entries(19)=ADDRESS(@CRename)
  entries(20)=ADDRESS(@CDeleteFile)
  entries(21)=ADDRESS(@CExamineExact)
  entries(22)=ADDRESS(@CMountVolume)
  entries(23)=ADDRESS(@CUnmountVolume)
  entries(24)=ADDRESS(@CExNextBatch)
  entries(25)=ADDRESS(@CLoadProgram)
  entries(26)=ADDRESS(@CReleaseProgram)
  entries(27)=ADDRESS(@CStartLoaded)
  entries(28)=ADDRESS(@DOS.Input)
  entries(29)=ADDRESS(@CLoadBegin)
  entries(30)=ADDRESS(@CLoadStep)
  entries(31)=ADDRESS(@CLoadTake)
  entries(32)=ADDRESS(@CLoadCancel)

RETURN
