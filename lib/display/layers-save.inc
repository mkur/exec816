; A single saved scene rectangle, excluding its own temporary overlay.
PUBLIC BYTE FUNC BeginSave(LAYERTYPES.Scene POINTER scene LONGCARD overlay
    LAYERTYPES.Rect POINTER area LONGCARD POINTER token)
  BYTE status,index
  CARD rect
  LAYERTYPES.Rect part

  status=Admit(scene)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI
  LET overlayLayer=Find(scene,overlay)
  IF overlayLayer.shown<>0 THEN
    RETURN(LAYERTYPES.REDRAW)
  FI
  FOR index=0 TO LAYERTYPES.SLOT_COUNT-1 DO
    BEGIN
      LET layer=@scene.items(index)
      IF layer.shown<>0 AND (layer.dirty<>0
          OR (layer.externalPaint<>0 AND layer.pending.count<>0)) THEN
        rect=0
        WHILE rect<layer.visible.count DO
          REGIONS.Intersect(area,@layer.visible.rects(rect),@part)
          IF REGIONS.Empty(@part)=0 AND PixelsReady(layer,@part)=0 THEN
            RETURN(LAYERTYPES.REDRAW)
          FI
          rect==+1
        OD
      FI
    END
  OD
  status=Claim(scene,overlay,LAYERTYPES.UPDATE_SCENE_READ,token)
  IF status=LAYERTYPES.OK THEN
    REGIONS.Copy(area,@scene.under.bounds)
    LAYERCACHE.Prepare(@scene.under.slot,overlay,1,
        CARD(area.right-area.left),CARD(area.bottom-area.top))
  FI

RETURN(status)

PUBLIC BYTE FUNC BeginRestore(LAYERTYPES.Scene POINTER scene LONGCARD overlay
    LONGCARD POINTER token)
  BYTE status

  status=Admit(scene)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI
  LET save=@scene.under
  LET layer=Find(scene,overlay)
  IF save.slot.valid=0 OR save.slot.pinned<>0 OR save.slot.identity<>overlay
      OR REGIONS.Equal(@save.bounds,@layer.bounds)=0 THEN
    RETURN(LAYERTYPES.REDRAW)
  FI
  status=Show(scene,overlay,0)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI
  status=Claim(scene,overlay,LAYERTYPES.UPDATE_RESTORE,token)
  IF status=LAYERTYPES.OK THEN
    save.slot.pinned=1
  FI

RETURN(status)

; The presenter has removed overlays and established DMA completion/quiescence.
; Exposure notification to external owners remains its responsibility.
PUBLIC BYTE FUNC FinishSave(LAYERTYPES.Scene POINTER scene LONGCARD token BYTE okay)
  BYTE index,accepted

  IF token=0 OR token<>scene.busy OR (scene.activeKind<>LAYERTYPES.UPDATE_SCENE_READ
      AND scene.activeKind<>LAYERTYPES.UPDATE_RESTORE) THEN
    RETURN(LAYERTYPES.BAD_TOKEN)
  FI
  IF scene.activeKind=LAYERTYPES.UPDATE_SCENE_READ THEN
    LAYERCACHE.Captured(@scene.under.slot,okay)
  ELSE
    IF okay<>0 THEN
      FOR index=0 TO LAYERTYPES.SLOT_COUNT-1 DO
        BEGIN
          LET layer=@scene.items(index)
          IF layer.dirty<>0 THEN
            accepted=SubtractDamage(scene,@layer.damage,@scene.under.bounds)
            layer.dirty=(layer.damage.count<>0)
          FI
        END
      OD
    FI
    LAYERCACHE.Discard(@scene.under.slot)
    LAYERCACHE.Released(@scene.under.slot,okay)
  FI

RETURN(Finish(scene,token,okay))
