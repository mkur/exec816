; Ordinary application windows borrow a console until window deletion. The
; existing presenter owns every pixel; no application receives a cell pointer.
PROC CommitAttachment(DESKTYPES.Window POINTER window
    CONSOLETYPES.Window POINTER entry LAYERTYPES.Rect POINTER work)

  LET view=CONSOLETYPES.Presentation POINTER(entry.view)
  LET instance=CONSOLETYPES.Instance POINTER(entry.instance)
  view.claimed=1
  view.visible=0
  view.focused=0
  view.left=CARD(work.left) RSH 3
  view.top=CARD(work.top) RSH 3
  view.index=$ffff
  view.presentedGeneration=0
  view.generation==+1
  CONSOLECORE.Dirty(instance,0,instance.count)
  window.console=entry.unit

RETURN

PUBLIC CARD FUNC Attach(DESKTYPES.Window POINTER window LONGCARD unit
    EXEC.Task POINTER owner)
  LAYERTYPES.Rect work
  BYTE status

  LET service=DESKSTATE.Get()
  LET layer=LAYERS.Find(@service.scene,window.layer)
  LET entry=CONSOLEWINDOWS.Find(unit)
  IF unit=0 OR entry=NULL OR entry.owner<>BYTE POINTER(owner) THEN
    RETURN(DESKTYPES.BAD_ID)
  FI

  IF layer.shown<>0 OR window.console<>0
      OR DESKSTATE.FindConsoleWindow(unit)<>NULL THEN
    RETURN(DESKTYPES.BAD_ARGUMENT)
  FI

  DESKGEOMETRY.Work(window.frameKind,@layer.bounds,@work)
  LET instance=CONSOLETYPES.Instance POINTER(entry.instance)
  IF work.right-work.left<>512 OR work.bottom-work.top<>160
      OR ((work.left OR work.top) & 7)<>0
      OR instance.width<>64 OR instance.height<>20 THEN
    RETURN(DESKTYPES.BAD_ARGUMENT)
  FI

  LET registry=CONSOLEWINDOWS.Registry()
  IF registry.presenting<>0 OR entry.busy<>0 OR service.scene.busy<>0
      OR CONSOLEBITMAP.Pending()<>0 OR DISPLAY.Blocked()<>0 THEN
    RETURN(DESKTYPES.BUSY)
  FI

  status=LAYERS.SetRetained(@service.scene,window.layer)
  IF status<>LAYERTYPES.OK THEN
    RETURN(DESKTYPES.BUSY)
  FI

  CommitAttachment(window,entry,@work)

RETURN(DESKTYPES.OK)

; Restore any outstanding caret before withdrawing its presentation.
PUBLIC CONSOLETYPES.Presentation POINTER FUNC PrepareRelease(LONGCARD unit)

  LET entry=CONSOLEWINDOWS.Find(unit)
  IF entry=NULL THEN
    RETURN(NULL)
  FI

  LET view=CONSOLETYPES.Presentation POINTER(entry.view)
  DESKSTATE.SelectConsoleUnit(unit)
  CONSOLEDISPLAY.RemoveCursor(view)

RETURN(view)

; Streams outlive the attachment. The creating Task still owns the unit.
PUBLIC PROC Release(DESKTYPES.Window POINTER window
    CONSOLETYPES.Presentation POINTER view)

  IF view<>NULL THEN
    view.visible=0
    view.focused=0
    view.claimed=0
    view.index=$ffff
    view.generation==+1
    view.presentedGeneration=0
  FI

  IF DESKSTATE.ConsoleUnit()=window.console THEN
    DESKSTATE.SelectConsole(0,0)
  FI
  window.console=0

RETURN
