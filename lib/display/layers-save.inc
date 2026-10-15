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
      OR REGIONS.Contains(@save.bounds,@layer.bounds)=0 THEN
    RETURN(LAYERTYPES.REDRAW)
  FI
  status=Show(scene,overlay,0)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI
  status=Claim(scene,overlay,LAYERTYPES.UPDATE_RESTORE,token)
  IF status=LAYERTYPES.OK THEN
    REGIONS.Copy(@layer.bounds,@scene.copyTarget)
    save.slot.pinned=1
  FI

RETURN(status)

; The presenter has removed overlays and established DMA completion/quiescence.
; Exposure notification to external owners remains its responsibility.
PUBLIC BYTE FUNC FinishSave(LAYERTYPES.Scene POINTER scene LONGCARD token BYTE okay,keep)
  BYTE index,accepted

  IF token=0 OR token<>scene.busy OR (scene.activeKind<>LAYERTYPES.UPDATE_SCENE_READ
      AND scene.activeKind<>LAYERTYPES.UPDATE_RESTORE) THEN
    RETURN(LAYERTYPES.BAD_TOKEN)
  FI
  okay=(okay<>0 AND scene.under.slot.revision<>0)
  IF scene.activeKind=LAYERTYPES.UPDATE_SCENE_READ THEN
    LAYERCACHE.Captured(@scene.under.slot,okay)
  ELSE
    IF okay<>0 THEN
      FOR index=0 TO LAYERTYPES.SLOT_COUNT-1 DO
        BEGIN
          LET layer=@scene.items(index)
          IF layer.dirty<>0 THEN
            accepted=SubtractDamage(scene,@layer.damage,@scene.copyTarget)
            layer.dirty=(layer.damage.count<>0)
            UpdateDamage(scene,index)
          FI
        END
      OD
    FI
    IF keep=0 THEN
      LAYERCACHE.Discard(@scene.under.slot)
    FI
    LAYERCACHE.Released(@scene.under.slot,okay)
  FI

RETURN(Finish(scene,token,okay))

; Keep the old opaque overlay committed while its saved pixels are replaced.
PUBLIC BYTE FUNC BeginSavedReplace(LAYERTYPES.Scene POINTER scene
    LONGCARD overlay LAYERTYPES.Rect POINTER nextBounds LONGCARD POINTER token)
  BYTE status

  status=Admit(scene)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI

  LET save=@scene.under
  LET layer=Find(scene,overlay)
  IF save.slot.valid=0 OR save.slot.pinned<>0 OR save.slot.identity<>overlay
      OR REGIONS.Contains(@save.bounds,@layer.bounds)=0
      OR REGIONS.Contains(@save.bounds,nextBounds)=0 THEN
    RETURN(LAYERTYPES.REDRAW)
  FI

  status=Claim(scene,overlay,LAYERTYPES.UPDATE_SAVED_REPLACE,token)
  IF status=LAYERTYPES.OK THEN
    REGIONS.Copy(nextBounds,@scene.copyTarget)
    REGIONS.Copy(@layer.bounds,@scene.copySource)
    save.slot.pinned=1
  FI

RETURN(status)

; The caller has quiesced both copies and frozen the image/menu revision.
; REDRAW retires the transaction but certifies no restored exposure.
PUBLIC BYTE FUNC FinishSavedReplace(LAYERTYPES.Scene POINTER scene
    LONGCARD token BYTE outcome)
  BYTE index,accepted,status

  IF token=0 OR token<>scene.busy
      OR scene.activeKind<>LAYERTYPES.UPDATE_SAVED_REPLACE THEN
    RETURN(LAYERTYPES.BAD_TOKEN)
  FI

  LET layer=Find(scene,scene.activeId)
  IF scene.under.slot.revision=0 THEN
    outcome=LAYERTYPES.REPLACE_REPAIR
  FI

  IF outcome=LAYERTYPES.REPLACE_REPAIR THEN
    DamageAll(scene,@scene.copySource)
    DamageAll(scene,@scene.copyTarget)
    LAYERCACHE.Released(@scene.under.slot,0)
    status=LAYERTYPES.REDRAW
  ELSE
    ; Initial Show may already have damaged the layers behind this overlay.
    ; Rebuild will compute their summary once, against the final geometry.
    FOR index=0 TO LAYERTYPES.SLOT_COUNT-1 DO
      BEGIN
        LET item=@scene.items(index)
        IF item.dirty<>0 THEN
          accepted=SubtractDamage(scene,@item.damage,@scene.copySource)
          item.dirty=(item.damage.count<>0)
        FI
      END
    OD

    REGIONS.Copy(@scene.copyTarget,@layer.bounds)
    layer.dirty=(outcome=LAYERTYPES.REPLACE_DIRTY)
    layer.damage.count=layer.dirty
    IF layer.dirty<>0 THEN
      REGIONS.Copy(@layer.bounds,@layer.damage.rects(0))
    FI
    status=Rebuild(scene)
    LAYERCACHE.Released(@scene.under.slot,status=LAYERTYPES.OK)
  FI

  scene.busy=0
  scene.activeKind=0
  scene.activeId=0

RETURN(status)
