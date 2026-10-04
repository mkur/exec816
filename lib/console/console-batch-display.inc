; Retained batching is admitted only against synchronized, complete pixels.
PUBLIC BYTE FUNC BeginBatch(CONSOLETYPES.Presentation POINTER view
    CONSOLETYPES.Instance POINTER instance LONGCARD unit)

  IF DESKSTATE.CopyReady()=0 OR CONSOLEBITMAP.Enabled()=0 OR CONSOLEBITMAP.Pending()<>0
      OR CONSOLEBITMAP.Failed()<>0 OR view.claimed=0 OR view.visible=0
      OR view.width<>instance.width OR view.height<>instance.height
      OR view.scrollState<>0 OR instance.height<=1
      OR instance.row<>instance.height-1 OR instance.dirtyRows<>0
      OR view.presentedGeneration<>instance.generation THEN
    RETURN(0)
  FI

  RemoveCursor(view)
  IF CONSOLEBITMAP.Failed()<>0
      OR CONSOLEBATCH.Begin(instance,unit,view.generation)=0 THEN
    RETURN(0)
  FI

  view.scrollUnit=unit
  view.scrollState=CONSOLETYPES.SCROLL_GATHER

RETURN(1)

; A ready continuation owns only the already accepted model and scalar identity.
PUBLIC PROC FlushBatch(CONSOLETYPES.Presentation POINTER view
    CONSOLETYPES.Instance POINTER instance BYTE reason)

  LET batch=CONSOLEBATCH.Get()
  CONSOLEBATCH.Publish(instance,reason)
  view.scrollUnit=batch.unit
  view.scrollGeneration=batch.viewGeneration
  view.scrollModel=batch.modelGeneration
  view.scrollRow=batch.rows
  view.index=$ffff
  view.scrollState=1
  IF batch.rows=0 THEN
    view.scrollState=0
    batch.phase=CONSOLETYPES.BATCH_PAINT
  FI

RETURN

; Control callers retain their targets until acknowledgement, including a
; RETIRING window. Preserve an existing worker borrow while abandoning reuse.
PUBLIC PROC DiscardBatch()
  BYTE borrowed

  LET batch=CONSOLEBATCH.Get()
  IF batch.phase=CONSOLETYPES.BATCH_IDLE OR CONSOLEBITMAP.Pending()<>0 THEN
    RETURN
  FI

  LET windows=CONSOLEWINDOWS.Registry()
  LET entry=@windows.items(BYTE(batch.unit & 3))
  borrowed=entry.busy
  entry.busy=1
  IF entry.unit=batch.unit AND entry.state<>CONSOLETYPES.WIN_FREE
      AND entry.instance<>NULL AND entry.view<>NULL THEN
    BEGIN
      LET view=CONSOLETYPES.Presentation POINTER(entry.view)
      LET instance=CONSOLETYPES.Instance POINTER(entry.instance)
      view.scrollState=0
      view.index=$ffff
      view.presentedGeneration=0
      CONSOLECORE.Dirty(instance,0,instance.count)
    END
  FI

  CONSOLEBATCH.Reset()
  entry.busy=borrowed

RETURN

; Only the associated view may consume final spans. Keep the caret absent
; until all text is painted, with the ordinary row and cell budgets per pass.
PROC PresentBatch(CONSOLETYPES.Presentation POINTER view
    CONSOLETYPES.Instance POINTER instance)
  BYTE caret

  LET batch=CONSOLEBATCH.Get()
  LET windows=CONSOLEWINDOWS.Registry()
  LET entry=@windows.items(BYTE(batch.unit & 3))
  IF batch.phase<>CONSOLETYPES.BATCH_PAINT OR entry.unit<>batch.unit
      OR entry.view<>BYTE POINTER(view) THEN
    RETURN
  FI

  IF view.generation<>batch.viewGeneration
      OR instance.generation<>batch.modelGeneration THEN
    DiscardBatch()
    RETURN
  FI

  caret=Cells(view,instance)
  IF instance.dirtyRows=0 THEN
    view.presentedGeneration=instance.generation
    IF caret=0 THEN
      Cursor(view,instance)
    FI

    CONSOLEBATCH.Reset()
  FI

RETURN
