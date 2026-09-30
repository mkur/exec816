BYTE FUNC Resolve(CARD offset)
  BYTE status
  CARD steps

  status=SDFSNAME.StartResolve(@work,BYTE POINTER(ADDRESS($a2000)+SIZE(offset)))
  steps=0
  WHILE status=FSSTATUS.NEED_IO OR status=FSSTATUS.MORE
      OR status=FSSTATUS.NEXT_COMPONENT DO
    steps==+1
    Require(steps<30000)
    IF status=FSSTATUS.NEXT_COMPONENT THEN
      status=SDFSNAME.ResolveComponent(@work)
    ELSE
      IF status=FSSTATUS.NEED_IO THEN
        Fetch()
      FI

      status=SDFSNAME.ResolveStep(@work)
    FI
  OD

RETURN(status)

BYTE FUNC EntryAt(CARD directory LONGCARD ordinal)
  BYTE status
  CARD steps

  status=SDFSDIR.BeginEntry(@work,directory,ordinal)
  steps=0
  WHILE status=FSSTATUS.NEED_IO OR status=FSSTATUS.MORE DO
    steps==+1
    Require(steps<100)
    IF status=FSSTATUS.NEED_IO THEN
      Fetch()
    FI

    status=SDFSDIR.BufferedEntry(@work)
  OD

RETURN(status)

BYTE FUNC MeasureEntry()
  BYTE status

  status=SDFSDIR.Measure(@work,@file,0)
  WHILE status=FSSTATUS.NEED_IO OR status=FSSTATUS.MORE DO
    IF status=FSSTATUS.NEED_IO THEN
      Fetch()
    FI

    status=SDFSDIR.Measure(@work,@file,1)
  OD

RETURN(status)

; The first header supplies the extent. A cache hit must retain that same entry
; without treating the 23-byte bootstrap read as the directory's length.
PROC HeaderExtent()
  BYTE status
  LONGCARD requests

  Require(Resolve(0)=FSSTATUS.DONE)
  SDFS.Invalidate(@work)
  LET state=SDFS.GetState(@work)
  status=SDFSDIR.BeginHeader(@work,volume.root)
  Require(state.directory.entry.known=0)
  WHILE status=FSSTATUS.NEED_IO OR status=FSSTATUS.MORE DO
    IF status=FSSTATUS.NEED_IO THEN
      Fetch()
    FI

    status=SDFSDIR.BufferedEntry(@work)
  OD

  Require(status=FSSTATUS.DONE AND state.directory.entry.known<>0
      AND state.directory.entry.length>23)
  LET extent=state.directory.entry.length
  requests=work.operations
  Require(SDFSDIR.BeginHeader(@work,volume.root)=FSSTATUS.MORE)
  Require(SDFSDIR.BufferedEntry(@work)=FSSTATUS.DONE)
  Require(work.operations=requests AND state.directory.entry.length=extent)

RETURN

; Resolve nested and ambiguous names through the production SpartaDOS parser.
PROC Paths()

  phase=30
  HeaderExtent()
  Require(Resolve(0)=1 AND work.entry.start=volume.root AND work.entry.parent=0)
  Require(MeasureEntry()=1 AND file.entry.count>0 AND file.entry.length>23)
  Require(Resolve(32)=1 AND work.entry.length=777 AND work.entry.known=1)
  Require(MeasureEntry()=1 AND file.entry.length=777 AND file.entry.count>0)
  Require(work.entry.days=17799 AND work.entry.minutes=0 AND work.entry.ticks=0)
  Require(Resolve(320)=1 AND work.entry.name(0)=66)
  Require(Resolve(64)=1 AND MeasureEntry()=1 AND file.entry.length=70003)
  Require(Resolve(96)=1 AND work.depth=2 AND work.entry.length=259)
  Require(Resolve(128)=1 AND work.entry.key=LONGCARD(1409) AND work.entry.length=4)
  Require(Resolve(160)=1 AND work.entry.key=255 AND work.entry.length=4)
  Require(Resolve(224)=0 AND work.error=205)
  Require(Resolve(352)=0 AND work.error=210)
  Require(Resolve(256)=1 AND work.depth=2 AND (work.entry.flags & FSBTYPES.DIR)<>0)
  Require(MeasureEntry()=1 AND file.entry.count>0)

RETURN

; Compare directory order and metadata with the fixture's on-disk records.
PROC Enumeration()
  CARD directory,live,skipped
  LONGCARD ordinal
  BYTE status

  Require(Resolve(192)=1)
  directory=work.entry.start
  live=0
  skipped=0
  ordinal=0
  DO
    status=EntryAt(directory,ordinal)
    IF status=FSSTATUS.END_DIR THEN
      EXIT
    FI

    IF status=FSSTATUS.DONE THEN
      live==+1
    ELSE
      Require(status=FSSTATUS.SKIP_ENTRY)
      skipped==+1
    FI

    ordinal==+1
    Require(ordinal<=1410)
  OD

  Require(live=300 AND skipped=1110 AND ordinal=1410)
  Require(EntryAt(directory,255)=1 AND work.entry.key=255)
  Require(EntryAt(directory,1409)=1 AND work.entry.key=LONGCARD(1409))
  Require(EntryAt(directory,729442)=FSSTATUS.END_DIR)

RETURN

; Reject invalid directory maps and parent relationships without unbounded
; scanning.
PROC BadDirectories()
  SDFSTYPES.BackendState POINTER state

  phase=31
  SDFS.Invalidate(@work)
  Require(Resolve(0)=1 AND MeasureEntry()=0 AND work.error=213)
  phase=32
  SDFS.Invalidate(@work)
  Require(Resolve(32)=0 AND work.error=213)
  phase=33
  SDFS.Invalidate(@work)
  Require(Resolve(32)=0 AND work.error=213)
  phase=34
  SDFS.Invalidate(@work)
  Require(Resolve(256)=0 AND work.error=213)
  phase=35
  SDFS.Invalidate(@work)
  Require(Resolve(32)=1 AND (work.entry.flags & FSBTYPES.PROTECTED)<>0)
  phase=36
  SDFS.Invalidate(@work)
  Require(Resolve(32)=0 AND work.error=210)
  phase=37
  SDFS.Invalidate(@work)
  Require(Resolve(32)=1 AND work.entry.length=777)
  Require(Resolve(448)=0 AND work.error=210)
  phase=38
  SDFS.Invalidate(@work)
  Require(Resolve(288)=0 AND work.error=213)
  phase=30
  SDFS.Invalidate(@work)
  Require(Resolve(32)=1)
  state=SDFS.GetState(@work)
  state.row(17)=29
  state.row(18)=2
  state.row(19)=0
  state.row(20)=23
  state.row(21)=59
  state.row(22)=59
  SDFSDATE.Decode(@work.entry,state.row)
  Require(work.entry.days=8094 AND work.entry.minutes=1439
      AND work.entry.ticks=2950)
  state.row(19)=1
  SDFSDATE.Decode(@work.entry,state.row)
  Require(work.entry.days=0 AND work.entry.minutes=0 AND work.entry.ticks=0)
  state.row(19)=77
  SDFSDATE.Decode(@work.entry,state.row)
  Require(work.entry.days=0)

RETURN
