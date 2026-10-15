PROC SavePaint()
  BYTE index,status
  LONGCARD token

  FOR index=0 TO LAYERTYPES.SLOT_COUNT-1 DO
    BEGIN
      LET layer=@scene.items(index)
      IF layer.shown<>0 AND layer.dirty<>0 THEN
        status=LAYERS.BeginPaint(scene,layer.id,@token)
        IF status=LAYERTYPES.OK THEN
          ExhaustPaint(scene,token)
          IF layer.externalPaint<>0 THEN
            Require(LAYERS.FinishHandoff(scene,token)=LAYERTYPES.OK)
            CheckVisible(scene)
          ELSE
            Require(LAYERS.Finish(scene,token,1)=LAYERTYPES.OK)
            CheckVisible(scene)
          FI
        FI
      FI
    END
  OD

RETURN

PROC SavedScene()
  LAYERTYPES.Rect bounds,area,part
  LAYERTYPES.CachePair cache
  LONGCARD left,right,popup,token

  Require(LAYERS.Init(scene,32,24)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,0,0,16,24)
  Require(LAYERS.Create(scene,@bounds,@left)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,left,1)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,16,0,32,24)
  Require(LAYERS.Create(scene,@bounds,@right)=LAYERTYPES.OK)
  Require(LAYERS.SetExternal(scene,right)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,right,1)=LAYERTYPES.OK)
  REGIONS.Assign(@area,8,4,24,16)
  Require(LAYERS.Create(scene,@area,@popup)=LAYERTYPES.OK)
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.REDRAW)
  SavePaint()
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.REDRAW)
  BEGIN
    LET layer=LAYERS.Find(scene,right)
    Require(LAYERS.Painted(scene,right,layer.paintEpoch,@bounds)=1)
    CheckVisible(scene)
  END
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.OK)
  Require(scene.under.slot.pinned=1 AND scene.under.slot.valid=0)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.BUSY)
  ; Source invalidation holds the pin until explicit transfer retirement.
  LAYERCACHE.Changed(@scene.under,left,@area)
  Require(scene.under.slot.pinned=1 AND scene.under.slot.revision=0)
  Require(LAYERS.FinishSave(scene,token,1,0)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(scene.under.slot.pinned=0 AND scene.under.slot.valid=0)
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,0)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(scene.under.slot.valid=1)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  Require(scene.under.slot.valid=1)
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.REDRAW)
  Require(LAYERS.Invalidate(scene,popup,@area)=LAYERTYPES.OK)
  Require(scene.under.slot.valid=1)
  REGIONS.Assign(@part,0,0,4,4)
  Require(LAYERS.Invalidate(scene,left,@part)=LAYERTYPES.OK)
  Require(scene.under.slot.valid=1)
  Require(LAYERS.BeginRestore(scene,popup,@token)=LAYERTYPES.OK)
  BEGIN
    LET layer=LAYERS.Find(scene,popup)
    Require(scene.under.slot.pinned=1 AND layer.shown=0)
  END
  Require(LAYERS.Delete(scene,right)=LAYERTYPES.BUSY)
  CheckVisible(scene)
  Require(LAYERS.FinishSave(scene,token,1,1)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(scene.busy=0 AND scene.under.slot.pinned=0 AND scene.under.slot.valid=1)
  ; Resize/move the hidden overlay without losing identity or the saved union.
  Require(LAYERS.Bounds(scene,popup,12,6,8,6)=LAYERTYPES.OK)
  Require(scene.under.slot.valid=1)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  Require(LAYERS.BeginRestore(scene,popup,@token)=LAYERTYPES.OK)
  Require(scene.copyTarget.left=12 AND scene.copyTarget.top=6)
  Require(scene.copyTarget.right=20 AND scene.copyTarget.bottom=12)
  Require(LAYERS.FinishSave(scene,token,1,1)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(scene.under.slot.valid=1 AND scene.under.slot.pinned=0)
  Require(LAYERS.Bounds(scene,popup,8,4,18,12)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  Require(LAYERS.BeginRestore(scene,popup,@token)=LAYERTYPES.REDRAW)
  Require(LAYERS.Show(scene,popup,0)=LAYERTYPES.OK)
  Require(LAYERS.Bounds(scene,popup,8,4,16,12)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  Require(LAYERS.BeginRestore(scene,popup,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,0)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(scene.under.slot.valid=0)
  Require(LAYERS.PixelsReady(LAYERS.Find(scene,left),@area)=1)
  Require(LAYERS.PixelsReady(LAYERS.Find(scene,left),@part)=0)
  ; Exposure delivery remains pending even though screen restoration finished.
  LAYERS.RequirePaint(scene,right,@area)
  Require(LAYERS.PixelsReady(LAYERS.Find(scene,right),@area)=0)
  Require(LAYERS.FinishSave(scene,token,1,0)=LAYERTYPES.BAD_TOKEN)
  CheckVisible(scene)
  SavePaint()
  BEGIN
    LET layer=LAYERS.Find(scene,right)
    Require(LAYERS.Painted(scene,right,layer.paintEpoch,@area)=1)
    CheckVisible(scene)
  END
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,0)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  Require(LAYERS.BeginRestore(scene,popup,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,0,1)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(scene.under.slot.valid=0 AND scene.under.slot.pinned=0)
  Require(LAYERS.PixelsReady(LAYERS.Find(scene,left),@area)=0)
  SavePaint()
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,0)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  Require(LAYERS.BeginRestore(scene,popup,@token)=LAYERTYPES.OK)
  ; An in-flight invalidation cannot release the pin or certify old pixels.
  LAYERCACHE.Changed(@scene.under,right,@area)
  Require(scene.under.slot.pinned=1 AND scene.under.slot.revision=0)
  Require(LAYERS.FinishSave(scene,token,1,1)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(scene.under.slot.valid=0 AND scene.under.slot.pinned=0)
  Require(LAYERS.PixelsReady(LAYERS.Find(scene,left),@area)=0)
  SavePaint()
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,0)=LAYERTYPES.OK)
  CheckVisible(scene)
  LAYERS.Touch(scene,right)
  Require(scene.under.slot.valid=0)
  Require(LAYERS.BeginSave(scene,popup,@area,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,0)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.Move(scene,left,1,0)=LAYERTYPES.OK)
  Require(scene.under.slot.valid=0)
  ; The same small cache policy serves native clients and menus.
  A816MEMORY.Clear(BYTE POINTER(@cache),SIZEOF(cache))
  Require(LAYERCACHE.Choose(@cache)=0)
  LAYERCACHE.Prepare(@cache.slots(0),left,3,16,12)
  Require(LAYERCACHE.Choose(@cache)=1)
  LAYERCACHE.Prepare(@cache.slots(1),right,4,16,12)
  Require(LAYERCACHE.Choose(@cache)=255)
  LAYERCACHE.Captured(@cache.slots(0),1)
  LAYERCACHE.Captured(@cache.slots(1),1)
  Require(LAYERCACHE.Lookup(@cache,left,3,16,12)=0)
  Require(LAYERCACHE.Lookup(@cache,right,3,16,12)=255)
  cache.recent=0
  Require(LAYERCACHE.Choose(@cache)=1)
  LAYERCACHE.Invalidate(@cache,left)
  Require(LAYERCACHE.Choose(@cache)=0)

RETURN
