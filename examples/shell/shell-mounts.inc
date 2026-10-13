; Small resident parser; geometry is always discovered by the filesystem worker.
LONGINT FUNC ShellMountParse(BYTE POINTER name DOS.SioMountSpec POINTER spec)
  CARD index,length
  BYTE seen,option,inferred

  length=ShellLength(shell.words(1).text)
  IF length<>0 THEN
    IF shell.words(1).text(length-1)=CHAR_COLON THEN
      length==-1
    FI
  FI

  IF length=0 OR length>31 THEN
    RETURN(DOS.ERROR_INVALID_COMPONENT_NAME)
  FI

  FOR index=0 TO length-1 DO
    name(index)=FS83.Fold(shell.words(1).text(index))
  OD

  name(length)=0
  IF FSNAMES.System(name,length)=0 AND FSNAMES.ValidAlias(name)=0 THEN
    RETURN(DOS.ERROR_INVALID_COMPONENT_NAME)
  FI

  A816MEMORY.Clear(BYTE POINTER(spec),DOS.SIOMOUNTSPEC_SIZE)
  spec.profile=EXEC.SIO_PROFILE_GENERIC57600
  inferred=0
  IF length=2 AND name(0)='D AND name(1)>='1 AND name(1)<='8 THEN
    inferred=name(1)-'0
    spec.drive=CARD(inferred)
  FI

  seen=0
  index=2
  WHILE index<shell.argc DO
    BEGIN
      LET word=shell.words(index).text
      option=0
      IF ShellEqual(word,c"READWRITE")<>0 THEN
        option=1
        spec.access=DOS.MOUNT_READWRITE
      ELSE
        BEGIN
          IF ShellEqual(word,c"DRIVE")=0 AND ShellEqual(word,c"FORMAT")=0 AND
              ShellEqual(word,c"PROFILE")=0 THEN
            RETURN(DOS.ERROR_BAD_ARGUMENTS)
          FI

          IF index+1>=shell.argc THEN
            RETURN(DOS.ERROR_REQUIRED_ARG_MISSING)
          FI

          LET value=shell.words(index+1).text
          IF ShellEqual(word,c"DRIVE")<>0 THEN
            option=2
            IF value(0)<'1 OR value(0)>'8 OR value(1)<>0 THEN
              RETURN(DOS.ERROR_BAD_NUMBER)
            FI

            spec.drive=CARD(value(0)-'0)
          ELSEIF ShellEqual(word,c"FORMAT")<>0 THEN
            option=4
            IF ShellEqual(value,c"MYDOS")<>0 THEN
              spec.format=DOS.MOUNT_MYDOS
            ELSEIF ShellEqual(value,c"SPARTA")<>0 THEN
              spec.format=DOS.MOUNT_SPARTA
            ELSE
              RETURN(DOS.ERROR_BAD_ARGUMENTS)
            FI
          ELSEIF ShellEqual(word,c"PROFILE")<>0 THEN
            option=8
            IF ShellEqual(value,c"GENERIC57600")<>0 THEN
              spec.profile=EXEC.SIO_PROFILE_GENERIC57600
            ELSEIF ShellEqual(value,c"FASTEST125")<>0 THEN
              spec.profile=EXEC.SIO_PROFILE_FASTEST125
            ELSEIF ShellEqual(value,c"STOCK810")<>0 THEN
              spec.profile=EXEC.SIO_PROFILE_STOCK810
            ELSE
              RETURN(DOS.ERROR_BAD_ARGUMENTS)
            FI
          ELSE
            RETURN(DOS.ERROR_BAD_ARGUMENTS)
          FI

          index==+1
        END
      FI

      IF (seen & option)<>0 THEN
        RETURN(DOS.ERROR_BAD_ARGUMENTS)
      FI

      seen=seen OR option
    END
    index==+1
  OD

  IF seen<>0 THEN
    IF (seen & 4)=0 OR spec.drive=0 THEN
      RETURN(DOS.ERROR_REQUIRED_ARG_MISSING)
    FI

    IF inferred<>0 AND spec.drive<>CARD(inferred) THEN
      RETURN(DOS.ERROR_BAD_NUMBER)
    FI
  FI

RETURN(0)

CSTRING FUNC ShellMountProfile(CARD profile)

  CASE profile OF
  WHEN EXEC.SIO_PROFILE_GENERIC57600 THEN
    RETURN(c"GENERIC57600")
  WHEN EXEC.SIO_PROFILE_FASTEST125 THEN
    RETURN(c"FASTEST125")
  WHEN EXEC.SIO_PROFILE_STOCK810 THEN
    RETURN(c"STOCK810")
  ESAC

RETURN(c"configured")

CSTRING FUNC ShellGeometrySource(BYTE source)

  CASE source OF
  WHEN FSDISCOVER.PERCOM THEN
    RETURN(c"PERCOM")
  WHEN FSDISCOVER.STATUS THEN
    RETURN(c"STATUS fallback")
  ESAC

RETURN(c"boot configuration")

; Rows fit the standard console; no probe or filesystem query occurs here.
PROC ShellMountDetails(DOS.FileHandle POINTER output FSINSPECT.Info POINTER info)
  CARD used

  used=ShellRowText(output,0,CSTRING(@info.name(0)))
  ShellRowEnd(output,ShellRowByte(output,used,CHAR_COLON))
  used=ShellRowText(output,0,c"  ")
  IF info.format=FSFORMATS.RAM THEN
    used=ShellRowText(output,used,c"RAM writable")
    ShellRowEnd(output,used)
    RETURN
  FI

  IF info.backend=BLOCKTYPES.BACKEND_SIO THEN
    used=ShellRowText(output,used,c"D")
    used=ShellRowNumber(output,used,LONGINT(info.unit)-48)
  ELSE
    used=ShellRowText(output,used,c"IDE unit ")
    used=ShellRowNumber(output,used,LONGINT(info.unit))
  FI

  IF info.format=FSFORMATS.MYDOS THEN
    used=ShellRowText(output,used,c" MyDOS ")
  ELSE
    used=ShellRowText(output,used,c" SpartaDOS ")
  FI

  IF info.readOnly<>0 THEN
    used=ShellRowText(output,used,c"read-only")
  ELSE
    used=ShellRowText(output,used,c"read-write")
  FI
  ShellRowEnd(output,used)
  used=ShellRowText(output,0,c"  ")
  used=ShellRowUnsigned(output,used,info.sectors)
  used=ShellRowText(output,used,c" x ")
  used=ShellRowNumber(output,used,LONGINT(info.bytes))
  used=ShellRowText(output,used,c"B ")
  IF info.backend=BLOCKTYPES.BACKEND_SIO THEN
    used=ShellRowText(output,used,ShellMountProfile(info.profile))
  FI

  ShellRowEnd(output,used)
  used=ShellRowText(output,0,c"  geometry: ")
  ShellRowEnd(output,ShellRowText(output,used,ShellGeometrySource(info.source)))

RETURN

PROC ShellMountCommand()
  BYTE ARRAY name(32)
  DOS.SioMountSpec spec
  CARD index,length
  LONGINT result

  LET output=DOS.Output()
  IF shell.argc=1 THEN
    ShellMounts(output)
    RETURN
  FI

  IF shell.argc=2 AND ShellEqual(shell.words(1).text,c"DIAGNOSTICS")<>0 THEN
    BEGIN
      ShellMounts(output)
      ShellIdeDiagnostics(output,1)
      LET rows=FSINSPECT.Info POINTER(ShellTransfer())
      LET count=FSINSPECT.Snapshot(rows,FSINSPECT.CAPACITY)
      IF count<>0 THEN
        FOR index=0 TO count-1 DO
          ShellMountDetails(output,@rows(index))
        OD
      FI

      RETURN
    END
  FI

  LET error=ShellMountParse(name,@spec)
  IF error<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  IF spec.format=0 THEN
    result=DOS.MountVolume(name,NULL)
  ELSE
    result=DOS.MountVolume(name,@spec)
  FI

  LET cause=DOS.IoErr()
  IF result=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,cause)
    RETURN
  FI

  length=ShellLength(name)
  LET rows=FSINSPECT.Info POINTER(ShellTransfer())
  LET count=FSINSPECT.Snapshot(rows,FSINSPECT.CAPACITY)
  IF count<>0 THEN
    FOR index=0 TO count-1 DO
      IF FSNAMES.AliasMatches(rows(index).name,name,length)<>0 OR
          (FSNAMES.System(name,length)<>0 AND
          rows(index).slot=BOOTCONFIG.B_SYSTEM_SLOT) THEN
        ShellMountDetails(output,@rows(index))
        EXIT
      FI
    OD
  FI

RETURN

PROC ShellUnmountCommand()
  BYTE ARRAY name(32)
  DOS.SioMountSpec spec

  LET error=ShellMountParse(name,@spec)
  IF error<>0 THEN
    ShellFail(PROCESS.RETURN_ERROR,error)
    RETURN
  FI

  LET result=DOS.UnmountVolume(name)
  LET cause=DOS.IoErr()
  IF result=0 THEN
    ShellFail(PROCESS.RETURN_ERROR,cause)
  ELSE
    BEGIN
      LET output=DOS.Output()
      ShellLineText(output,c"Unmounted")
      LET used=ShellRowText(output,0,CSTRING(@name(0)))
      ShellRowEnd(output,ShellRowByte(output,used,CHAR_COLON))
    END
  FI

RETURN
