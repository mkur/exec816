; A continuation contains identities and scalars, never borrowed pointers.
; The logical edit commits once before the physical copy/fill launch.
PROC BitmapEdit(CONSOLETYPES.Presentation POINTER view CONSOLETYPES.Instance
    POINTER instance)
  BYTE synchronized

  IF CONSOLEBITMAP.Pending()<>0 THEN
    RETURN
  FI

  LET operation=instance.operation
  synchronized=0
  IF view.claimed<>0 AND view.visible<>0 AND view.width=instance.width
      AND view.height=instance.height AND CONSOLEBITMAP.Failed()=0 THEN
    RemoveCursor(view)
    IF operation=CONSOLETYPES.OP_CLEAR THEN
      synchronized=1
    ELSE
      IF instance.dirtyRows<>0 AND instance.dirtyRows<=ROW_BUDGET THEN
        Cells(view,instance)
      FI

      synchronized=instance.dirtyRows=0
          AND view.presentedGeneration=instance.generation
    FI
  FI

  CONSOLECORE.EditQuantum(instance)
  IF synchronized=0 OR CONSOLEBITMAP.Failed()<>0 THEN
    RETURN
  FI

  LET entry=CONSOLEWINDOWS.Bound(BYTE POINTER(instance))
  IF entry=NULL OR entry.view<>BYTE POINTER(view) THEN
    RETURN
  FI

  view.scrollUnit=entry.unit
  view.scrollGeneration=view.generation
  view.scrollModel=instance.generation
  view.scrollRow=0
  view.scrollState=1
  IF operation=CONSOLETYPES.OP_CLEAR THEN
    view.scrollState=2
  FI

RETURN

; Resolve the permanent registry only after the DMA no longer owns its pixels.
; Presenting entries defer adoption until publication; retired entries cannot
; adopt it. No instance pointer crosses a worker turn.
BYTE FUNC BitmapComplete()

  LET windows=CONSOLEWINDOWS.Registry()
  LET entry=@windows.items(BYTE(bitmapUnit & 3))
  entry.busy=1
  IF entry.state=CONSOLETYPES.WIN_PRESENTING AND entry.unit=bitmapUnit THEN
    entry.busy=0
    RETURN(0)
  FI

  IF entry.state=CONSOLETYPES.WIN_LIVE AND entry.unit=bitmapUnit THEN
    BEGIN
      LET view=CONSOLETYPES.Presentation POINTER(entry.view)
      LET instance=CONSOLETYPES.Instance POINTER(entry.instance)
      IF view.scrollState=3 THEN
        view.scrollState=0
        view.index=$ffff
        IF view.generation=bitmapGeneration AND instance.generation=bitmapModel
            AND view.scrollUnit=bitmapUnit
            AND view.scrollGeneration=bitmapGeneration
            AND view.scrollModel=bitmapModel AND view.visible<>0
            AND view.claimed<>0 AND CONSOLEBITMAP.Failed()=0 THEN
          view.scrollRow=view.height LSH 3
          CONSOLECORE.Clean(instance)
          view.presentedGeneration=instance.generation
        ELSE
          view.presentedGeneration=0
          CONSOLECORE.Dirty(instance,0,instance.count)
        FI
      FI
    END
  FI

  entry.busy=0

RETURN(1)

; This runs even when a presentation transaction prevents normal borrows.
; Poll once per turn; retire its identity before another instance can launch.
PUBLIC PROC Poll()

  IF CONSOLEBITMAP.Pending()<>0 THEN
    CONSOLEBITMAP.Poll()
    IF CONSOLEBITMAP.Pending()=0 THEN
      bitmapReady=1
    FI
  FI

  IF bitmapReady<>0 THEN
    IF BitmapComplete()<>0 THEN
      bitmapReady=0
    FI
  FI

RETURN

; One scroll submission owns copy and bottom fill. Clear retains bounded fills.
PUBLIC PROC Advance(CONSOLETYPES.Presentation POINTER view CONSOLETYPES.Instance
    POINTER instance LONGCARD unit)
  CARD rows
  BYTE okay

  IF view.scrollState=0 OR CONSOLEBITMAP.Pending()<>0 THEN
    RETURN
  FI

  IF view.scrollUnit<>unit OR view.scrollGeneration<>view.generation
      OR view.scrollModel<>instance.generation OR view.visible=0
      OR view.claimed=0 OR CONSOLEBITMAP.Failed()<>0 THEN
    view.scrollState=0
    view.presentedGeneration=0
    CONSOLECORE.Dirty(instance,0,instance.count)
    RETURN
  FI

  IF view.scrollState=1 THEN
    okay=CONSOLEBITMAP.Scroll(view.left,view.top,view.width,view.height)
    IF okay<>0 THEN
      bitmapUnit=unit
      bitmapGeneration=view.generation
      bitmapModel=instance.generation
      view.scrollState=3
    ELSE
      view.scrollState=0
      view.presentedGeneration=0
    FI

    RETURN
  FI

  ; A retired/republished entry cannot adopt another operation's completion.
  IF view.scrollState=3 THEN
    view.scrollState=0
    view.presentedGeneration=0
    CONSOLECORE.Dirty(instance,0,instance.count)
    RETURN
  FI

  rows=(view.height LSH 3)-view.scrollRow
  IF rows>16 THEN
    rows=16
  FI

  okay=CONSOLEBITMAP.Fill(view.left LSH 3,(view.top LSH 3)+view.scrollRow,
      view.width LSH 3,rows,0)
  IF okay=0 THEN
    view.scrollState=0
    view.presentedGeneration=0
    RETURN
  FI

  view.scrollRow==+rows
  IF view.scrollState=2 AND view.scrollRow=(view.height LSH 3) THEN
    view.scrollState=0
    CONSOLECORE.Clean(instance)
    view.presentedGeneration=instance.generation
  FI

RETURN
