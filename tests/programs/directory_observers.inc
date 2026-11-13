; Two real directory consumers. Neither arms a timer nor queries the controller.
EXEC.Task POINTER directoryParent
LONGCARD directoryMask,directoryOldUnit,directoryNewUnit
LONGCARD ARRAY directoryCounts(2)
BYTE directoryReady,directoryDone,directoryStopping
CARD directoryChecks

PROC DirectoryCheck(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($ed00+directoryChecks)
  FI

  EXEC.Forbid()
  directoryChecks==+1
  EXEC.Permit()

RETURN

PROC DirectoryObserver(BYTE index)
  LONGCARD bits

  DirectoryCheck(EXEC.AllocSignal(31)=31)
  LET watch=CONSOLEVIEW.WatchDirectory($80000000)
  DirectoryCheck(watch<>0)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(watch)=1)
  bits=EXEC.Wait($80000000)
  EXEC.Forbid()
  directoryReady==+1
  EXEC.Signal(directoryParent,directoryMask)
  EXEC.Permit()
  DO
    bits=EXEC.Wait($80000000)
    IF CONSOLEVIEWCORE.TakeDirectoryChange(watch)<>0 THEN
      directoryCounts(index)==+1
      EXEC.Signal(directoryParent,directoryMask)
    FI

    IF directoryStopping<>0 AND shellPublished=0 THEN
      EXIT
    FI
  OD

  DirectoryCheck(CONSOLEVIEWCORE.UnwatchDirectory(watch)=VIEW.OK)
  EXEC.FreeSignal(31)
  EXEC.Forbid()
  directoryDone==+1
  EXEC.Signal(directoryParent,directoryMask)
  EXEC.RemTask(NULL)

RETURN

PROC DirectoryFirst()

  DirectoryObserver(0)

RETURN

PROC DirectorySecond()

  DirectoryObserver(1)

RETURN

PROC DirectoryStart()

  directoryParent=EXEC.FindTask(NULL)
  LET bit=EXEC.AllocSignal(-1)
  DirectoryCheck(bit<>$ff)
  directoryMask=LONGCARD(1) LSH bit
  DirectoryCheck(EXEC.CreateTask(c"directory first",0,@DirectoryFirst,1536)<>NULL)
  DirectoryCheck(EXEC.CreateTask(c"directory second",0,@DirectorySecond,1536)<>NULL)
  WHILE directoryReady<>2 DO
    EXEC.Wait(directoryMask)
  OD

RETURN

PROC DirectoryBarrier(LONGCARD previous)

  WHILE directoryCounts(0)=previous OR directoryCounts(1)=previous DO
    EXEC.Wait(directoryMask)
  OD
  DirectoryCheck(directoryCounts(0)=directoryCounts(1))

RETURN

; Root also consumes its own watch while it owns UPDATE. Peer consumers
; remain blocked from drawing and still receive each metadata commit.
PROC DirectoryPublishers()
  LONGCARD previous
  VIEW.Directory snapshot

  LET own=CONSOLEVIEW.WatchDirectory(directoryMask)
  DirectoryCheck(own<>0)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=1)
  LET service=AESSTATE.Get()
  DirectoryCheck(CALYPSICALL.Invoke(ADDRESS($DIRECTORYUPDATE),
      LONGCARD(ADDRESS(@service.port)))<>0)
  previous=directoryCounts(0)
  directoryOldUnit=CONSOLE.Create(CONSOLE.ScreenWidth(),CONSOLE.ScreenHeight())
  DirectoryCheck(directoryOldUnit<>0)
  DirectoryBarrier(previous)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=1)
  DirectoryCheck(CONSOLEVIEW.Directory(@snapshot)=VIEW.OK)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=0)
  previous=directoryCounts(0)
  DirectoryCheck(CONSOLE.Destroy(directoryOldUnit)<>0)
  DirectoryBarrier(previous)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=1)
  DirectoryCheck(CONSOLEVIEW.Directory(@snapshot)=VIEW.OK)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=0)
  previous=directoryCounts(0)
  directoryNewUnit=CONSOLE.Create(CONSOLE.ScreenWidth(),CONSOLE.ScreenHeight())
  DirectoryCheck(directoryNewUnit<>0 AND directoryNewUnit<>directoryOldUnit)
  DirectoryBarrier(previous)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=1)
  DirectoryCheck(CONSOLEVIEW.Directory(@snapshot)=VIEW.OK)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=0)
  previous=directoryCounts(0)
  DirectoryCheck(CONSOLE.Destroy(directoryNewUnit)<>0)
  DirectoryBarrier(previous)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=1)
  DirectoryCheck(CONSOLEVIEW.Directory(@snapshot)=VIEW.OK)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=0)
  previous=directoryCounts(0)
  DirectoryCheck(CONSOLEVIEW.Activate(0)=VIEW.OK)
  DirectoryBarrier(previous)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=1)
  DirectoryCheck(CONSOLEVIEW.Directory(@snapshot)=VIEW.OK)
  DirectoryCheck(CONSOLEVIEWCORE.TakeDirectoryChange(own)=0)
  DirectoryCheck(CALYPSICALL.Invoke(ADDRESS($DIRECTORYUPDATE),0)<>0)
  DirectoryCheck(CONSOLEVIEWCORE.UnwatchDirectory(own)=VIEW.OK)

RETURN

PROC DirectoryFinish()
  BYTE bit

  WHILE directoryDone<>2 DO
    EXEC.Wait(directoryMask)
  OD

  EXEC.SetSignal(0,directoryMask)
  bit=0
  WHILE (LONGCARD(1) LSH bit)<>directoryMask DO
    bit==+1
  OD
  EXEC.FreeSignal(bit)

RETURN
