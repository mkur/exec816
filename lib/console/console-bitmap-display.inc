; A continuation contains identities and scalars, never borrowed pointers.
; The logical edit commits once before the first physical copy/fill chunk.
PROC BitmapEdit(CONSOLETYPES.Presentation POINTER view CONSOLETYPES.Instance
    POINTER instance)
  BYTE synchronized

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

; Re-resolve on each worker borrow. Copy order is top-to-bottom, with opaque
; zero pixels; no more than sixteen pixel rows cross this ordinary-call fence.
PUBLIC PROC Advance(CONSOLETYPES.Presentation POINTER view CONSOLETYPES.Instance
    POINTER instance LONGCARD unit)
  CARD limit,rows
  BYTE okay

  IF view.scrollState=0 THEN
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

  limit=view.height LSH 3
  IF view.scrollState=1 THEN
    limit==-8
    IF view.scrollRow=limit THEN
      view.scrollState=2
    FI
  FI

  IF view.scrollState=1 THEN
    rows=limit-view.scrollRow
    IF rows>16 THEN
      rows=16
    FI

    okay=CONSOLEBITMAP.Scroll(view.left,view.top,view.width,
        view.scrollRow,rows)
  ELSE
    rows=(view.height LSH 3)-view.scrollRow
    IF rows>16 THEN
      rows=16
    FI

    okay=CONSOLEBITMAP.Fill(view.left LSH 3,(view.top LSH 3)+view.scrollRow,
        view.width LSH 3,rows,0)
  FI

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
