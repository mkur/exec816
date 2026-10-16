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

; An unrelated dirty window and external paint survive both replacement
; outcomes and dismissal. Only the saved footprint certifies restored pixels.
PROC DisjointSavedDamage(INT width)
  LAYERTYPES.Rect whole,saved,old,next,outside
  LONGCARD base,side,popup,token,rebuilds
  BYTE pass,outcome

  Require(LAYERS.Init(scene,width,24)=LAYERTYPES.OK)
  REGIONS.Assign(@whole,0,0,width,24)
  Require(LAYERS.Create(scene,@whole,@base)=LAYERTYPES.OK)
  Require(LAYERS.SetExternal(scene,base)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,base,1)=LAYERTYPES.OK)
  REGIONS.Assign(@outside,24,16,width,24)
  Require(LAYERS.Create(scene,@outside,@side)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,side,1)=LAYERTYPES.OK)
  SavePaint()
  LET under=LAYERS.Find(scene,base)
  LET other=LAYERS.Find(scene,side)
  Require(LAYERS.Painted(scene,base,under.paintEpoch,@whole)=1)
  REGIONS.Assign(@old,4,4,12,12)
  REGIONS.Assign(@saved,0,0,24,16)
  Require(LAYERS.Create(scene,@old,@popup)=LAYERTYPES.OK)
  Require(LAYERS.BeginSave(scene,popup,@saved,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,1)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  REGIONS.Assign(@outside,26,18,30,22)
  Require(LAYERS.Invalidate(scene,side,@outside)=LAYERTYPES.OK)
  LAYERS.RequirePaint(scene,base,@old)

  FOR pass=0 TO 1 DO
    REGIONS.Assign(@next,12,4,20,12)
    IF pass=1 THEN
      REGIONS.Copy(@old,@next)
    FI
    outcome=IF pass=0 THEN LAYERTYPES.REPLACE_CLEAN
        ELSE LAYERTYPES.REPLACE_DIRTY FI
    rebuilds=scene.rebuilds
    Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.OK)
    Require(LAYERS.FinishSavedReplace(scene,token,outcome)=LAYERTYPES.OK)
    Require(scene.rebuilds=rebuilds+1)
    Require(scene.busy=0 AND scene.under.slot.pinned=0 AND scene.under.slot.valid=1)
    Require(other.dirty=1 AND other.damage.count=1)
    Require(REGIONS.Equal(@other.damage.rects(0),@outside)=1)
    Require(LAYERS.FindDamaged(scene,side)=other)
    Require(under.pending.count=1)
    Require(REGIONS.Equal(@under.pending.rects(0),@old)=1)
    CheckVisible(scene)
  OD

  Require(LAYERS.BeginRestore(scene,popup,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,1)=LAYERTYPES.OK)
  Require(scene.busy=0 AND scene.under.slot.pinned=0 AND scene.under.slot.valid=1)
  Require(other.dirty=1 AND other.damage.count=1)
  Require(REGIONS.Equal(@other.damage.rects(0),@outside)=1)
  Require(LAYERS.FindDamaged(scene,side)=other)
  Require(under.pending.count=1)
  Require(REGIONS.Equal(@under.pending.rects(0),@old)=1)
  CheckVisible(scene)

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

; Replacement publishes one final scene and retires only proven old coverage.
PROC ReplaceSavedScene(BYTE stripes)
  LAYERTYPES.Rect old,next,whole
  LONGCARD base,popup,token,stale,serial,rebuilds
  BYTE index

  Require(LAYERS.Init(scene,32,24)=LAYERTYPES.OK)
  REGIONS.Assign(@whole,0,0,32,24)
  Require(LAYERS.Create(scene,@whole,@base)=LAYERTYPES.OK)
  Require(LAYERS.SetExternal(scene,base)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,base,1)=LAYERTYPES.OK)
  SavePaint()
  LET under=LAYERS.Find(scene,base)
  Require(LAYERS.Painted(scene,base,under.paintEpoch,@whole)=1)
  REGIONS.Assign(@old,4,4,12,12)
  Require(LAYERS.Create(scene,@old,@popup)=LAYERTYPES.OK)
  Require(LAYERS.BeginSave(scene,popup,@whole,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,1)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  LET overlay=LAYERS.Find(scene,popup)
  rebuilds=scene.rebuilds
  REGIONS.Assign(@next,8,2,20,10)
  LAYERS.RequirePaint(scene,base,@old)
  Require(under.pending.count=1 AND under.dirty=1)

  serial=scene.nextToken
  scene.nextToken=0
  token=$12345678
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.EXHAUSTED)
  Require(token=$12345678 AND scene.busy=0 AND scene.under.slot.pinned=0)
  Require(REGIONS.Equal(@overlay.bounds,@old)=1 AND scene.rebuilds=rebuilds)
  scene.nextToken=serial
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.OK)
  Require(scene.busy=token AND scene.under.slot.pinned=1)
  Require(overlay.shown=1 AND REGIONS.Equal(@overlay.bounds,@old)=1)
  Require(REGIONS.Equal(@scene.copySource,@old)=1)
  Require(REGIONS.Equal(@scene.copyTarget,@next)=1)
  Require(LAYERS.Hit(scene,5,5)=popup AND LAYERS.Hit(scene,18,3)=base)
  Require(scene.rebuilds=rebuilds)
  stale=$12345678
  Require(LAYERS.BeginSavedReplace(scene,popup,@whole,@stale)=LAYERTYPES.BUSY)
  Require(stale=$12345678)
  Require(LAYERS.Finish(scene,token,1)=LAYERTYPES.BAD_TOKEN)
  Require(LAYERS.FinishSavedReplace(scene,token+1,LAYERTYPES.REPLACE_CLEAN)=LAYERTYPES.BAD_TOKEN)
  Require(scene.busy=token AND scene.under.slot.pinned=1)
  Require(LAYERS.FinishSavedReplace(scene,token,LAYERTYPES.REPLACE_CLEAN)=LAYERTYPES.OK)
  Require(scene.rebuilds=rebuilds+1 AND REGIONS.Equal(@overlay.bounds,@next)=1)
  Require(overlay.dirty=0 AND under.dirty=0 AND under.pending.count=1)
  Require(REGIONS.Equal(@under.pending.rects(0),@old)=1)
  Require(scene.busy=0 AND scene.under.slot.valid=1 AND scene.under.slot.pinned=0)
  Require(LAYERS.Hit(scene,5,5)=base AND LAYERS.Hit(scene,18,3)=popup)
  CheckVisible(scene)

  stale=token
  REGIONS.Copy(@next,@old)
  REGIONS.Assign(@next,24,16,32,24)
  rebuilds=scene.rebuilds
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSavedReplace(scene,stale,LAYERTYPES.REPLACE_REPAIR)=LAYERTYPES.BAD_TOKEN)
  Require(scene.busy=token AND scene.under.slot.pinned=1)
  Require(LAYERS.FinishSavedReplace(scene,token,LAYERTYPES.REPLACE_DIRTY)=LAYERTYPES.OK)
  Require(scene.rebuilds=rebuilds+1 AND overlay.dirty=1)
  Require(overlay.damage.count=1 AND REGIONS.Equal(@overlay.damage.rects(0),@next)=1)
  Require(under.pending.count=1 AND under.dirty=0)
  CheckVisible(scene)

  ; A stale retained save cannot certify either copied image.
  REGIONS.Copy(@next,@old)
  REGIONS.Assign(@next,0,0,4,4)
  rebuilds=scene.rebuilds
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.OK)
  LAYERS.Touch(scene,base)
  Require(scene.under.slot.pinned=1 AND scene.under.slot.revision=0)
  Require(LAYERS.FinishSavedReplace(scene,token,LAYERTYPES.REPLACE_CLEAN)=LAYERTYPES.REDRAW)
  Require(REGIONS.Equal(@overlay.bounds,@old)=1 AND scene.rebuilds=rebuilds)
  Require(scene.busy=0 AND scene.under.slot.pinned=0 AND scene.under.slot.valid=0)
  Require(LAYERS.PixelsReady(under,@old)=0 AND LAYERS.PixelsReady(under,@next)=0)
  CheckVisible(scene)
  token=$12345678
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.REDRAW)
  Require(token=$12345678)

  Require(LAYERS.Show(scene,popup,0)=LAYERTYPES.OK)
  SavePaint()
  Require(LAYERS.Painted(scene,base,under.paintEpoch,@whole)=1)
  Require(LAYERS.BeginSave(scene,popup,@whole,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSave(scene,token,1,1)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,popup,1)=LAYERTYPES.OK)
  REGIONS.Assign(@next,0,8,32,16)
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSavedReplace(scene,token,LAYERTYPES.REPLACE_CLEAN)=LAYERTYPES.OK)
  ; Eight independent strips would split into sixteen. Keep all old damage.
  under.dirty=1
  under.damage.count=stripes
  FOR index=0 TO stripes-1 DO
    REGIONS.Assign(@under.damage.rects(index),INT(index*4),0,INT(index*4+2),24)
  OD
  REGIONS.Copy(@next,@old)
  REGIONS.Assign(@next,0,0,4,4)
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSavedReplace(scene,token,LAYERTYPES.REPLACE_CLEAN)=LAYERTYPES.OK)
  Require(under.dirty=1 AND under.damage.count=stripes)
  FOR index=0 TO stripes-1 DO
    BEGIN
      LET part=@under.damage.rects(index)
      Require(part.left=INT(index*4) AND part.right=INT(index*4+2))
      Require(part.top=0 AND part.bottom=24)
    END
  OD
  CheckVisible(scene)

  REGIONS.Assign(@next,30,20,34,24)
  token=$12345678
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.REDRAW)
  Require(token=$12345678 AND scene.busy=0 AND scene.under.slot.pinned=0)
  REGIONS.Copy(@overlay.bounds,@old)
  REGIONS.Assign(@next,20,20,24,24)
  Require(LAYERS.BeginSavedReplace(scene,popup,@next,@token)=LAYERTYPES.OK)
  Require(LAYERS.FinishSavedReplace(scene,token,LAYERTYPES.REPLACE_REPAIR)=LAYERTYPES.REDRAW)
  Require(REGIONS.Equal(@overlay.bounds,@old)=1 AND scene.busy=0)
  Require(scene.under.slot.valid=0 AND scene.under.slot.pinned=0)
  Require(LAYERS.PixelsReady(under,@next)=0)
  CheckVisible(scene)

RETURN
