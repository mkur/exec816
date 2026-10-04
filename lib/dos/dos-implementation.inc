; Native source adapters preserve the public DOS record identities and ABI.
PUBLIC FileHandle POINTER FUNC Open(BYTE POINTER name LONGINT mode)

RETURN(FileHandle POINTER(DOSCALLS.Open(name,mode)))

PUBLIC LONGINT FUNC Read(FileHandle POINTER file BYTE POINTER buffer LONGINT length)

RETURN(DOSCALLS.Read(BYTE POINTER(file),buffer,length))

PUBLIC LONGINT FUNC Write(FileHandle POINTER file BYTE POINTER buffer
    LONGINT length)

RETURN(DOSCALLS.Write(BYTE POINTER(file),buffer,length))

PUBLIC LONGINT FUNC Seek(FileHandle POINTER file LONGINT offset,mode)

RETURN(DOSCALLS.Seek(BYTE POINTER(file),offset,mode))

PUBLIC LONGINT FUNC Close(FileHandle POINTER file)

RETURN(DOSCALLS.Close(BYTE POINTER(file)))

PUBLIC LONGINT FUNC SetIoErr(LONGINT error)

RETURN(DOSCLIENT.SetIoErr(error))

PUBLIC LONGINT FUNC IoErr()

RETURN(DOSCLIENT.IoErr())

PUBLIC LONGINT FUNC ReleaseContext()

RETURN(DOSCLIENT.ReleaseContext())

PUBLIC FileLock POINTER FUNC Lock(BYTE POINTER name LONGINT mode)

RETURN(FileLock POINTER(DOSCALLS.Lock(name,mode)))

PUBLIC PROC UnLock(FileLock POINTER lock)

  DOSCALLS.UnLock(BYTE POINTER(lock))

RETURN

PUBLIC LONGINT FUNC Examine(FileLock POINTER lock FileInfoBlock POINTER info)

RETURN(DOSCALLS.Information(BYTE POINTER(lock),BYTE POINTER(info),23))

PUBLIC LONGINT FUNC ExNext(FileLock POINTER lock FileInfoBlock POINTER info)

RETURN(DOSCALLS.Information(BYTE POINTER(lock),BYTE POINTER(info),24))

PUBLIC FileHandle POINTER FUNC Input()

RETURN(FileHandle POINTER(DOSCALLS.Selected(0)))

PUBLIC FileHandle POINTER FUNC Output()

RETURN(FileHandle POINTER(DOSCALLS.Selected(1)))

PUBLIC FileHandle POINTER FUNC SelectInput(FileHandle POINTER file)

RETURN(FileHandle POINTER(DOSCALLS.Select(BYTE POINTER(file),0)))

PUBLIC FileHandle POINTER FUNC SelectOutput(FileHandle POINTER file)

RETURN(FileHandle POINTER(DOSCALLS.Select(BYTE POINTER(file),1)))

PUBLIC LONGINT FUNC IsInteractive(FileHandle POINTER file)

RETURN(DOSCALLS.IsInteractive(BYTE POINTER(file)))

PUBLIC FileLock POINTER FUNC CurrentDir(FileLock POINTER lock)

RETURN(FileLock POINTER(DOSCALLS.CurrentDir(BYTE POINTER(lock))))

PUBLIC LONGINT FUNC NameFromLock(FileLock POINTER lock BYTE POINTER buffer
    LONGINT length)

RETURN(DOSCALLS.NameFromLock(BYTE POINTER(lock),buffer,length))

PUBLIC LONGINT FUNC BeginForeground(FileHandle POINTER console)

RETURN(DOSCALLS.BeginForeground(BYTE POINTER(console)))

PUBLIC LONGINT FUNC EndForeground()

RETURN(DOSCALLS.EndForeground())

PUBLIC LONGINT FUNC BreakPending()

RETURN(DOSCALLS.BreakPending())

PUBLIC PROC ClearBreak()

  DOSCALLS.ClearBreak()

RETURN

PUBLIC LONGINT FUNC Pipe(PipePair POINTER pair)

RETURN(DOSCALLS.Pipe(BYTE POINTER(pair)))

; Console control remains attached to the foreground scope across redirection.
PUBLIC FileHandle POINTER FUNC OpenConsole()

RETURN(FileHandle POINTER(DOSCALLS.OpenConsole()))

PUBLIC LONGINT FUNC ConsoleInfo(FileHandle POINTER file BYTE POINTER size)

RETURN(DOSCALLS.ConsoleInfo(BYTE POINTER(file),size))
