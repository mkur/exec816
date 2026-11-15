; Independent geometric oracle: derive bits from rectangle intersections,
; without consulting the production summary or its mutation helpers.
PROC CheckVisible(LAYERTYPES.Scene POINTER state)
  BYTE slot,damage
  CARD visible,expected
  LAYERTYPES.Rect overlap

  expected=0
  FOR slot=0 TO LAYERTYPES.SLOT_COUNT-1 DO
    BEGIN
      LET layer=@state.items(slot)
      damage=0
      WHILE layer.dirty<>0 AND damage<layer.damage.count DO
        visible=0
        WHILE visible<layer.visible.count DO
          REGIONS.Intersect(@layer.damage.rects(damage),
              @layer.visible.rects(visible),@overlap)
          IF REGIONS.Empty(@overlap)=0 THEN
            expected=expected OR (CARD(1) LSH slot)
          FI
          visible==+1
        OD
        damage==+1
      OD
    END
  OD
  Require(state.visibleDamage=expected)
  FOR slot=0 TO LAYERTYPES.SLOT_COUNT-1 DO
    BEGIN
      LET layer=@state.items(slot)
      IF layer.id<>0 OR slot=LAYERTYPES.BACKGROUND_SLOT THEN
        BEGIN
          LET found=LAYERS.FindDamaged(state,layer.id)
          IF (expected & (CARD(1) LSH slot))<>0 THEN
            Require(found=layer)
          ELSE
            Require(found=NULL)
          FI
        END
      FI
    END
  OD
  Require(LAYERS.FindDamaged(state,$ffffffff)=NULL)

RETURN

; Cover the whole screen, then expose dirty background and reuse a hidden slot.
PROC ReadinessTransactions()
  LAYERTYPES.Rect bounds
  LONGCARD id,token
  BYTE index

  Require(LAYERS.Init(scene,32,24)=LAYERTYPES.OK)
  Require(scene.visibleDamage=$100)
  REGIONS.Assign(@bounds,0,0,32,24)
  Require(LAYERS.Create(scene,@bounds,@id)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.Show(scene,id,1)=LAYERTYPES.OK)
  Require(scene.visibleDamage=1)
  Require(LAYERS.BeginPaint(scene,id,@token)=LAYERTYPES.OK)
  ExhaustPaint(scene,token)
  Require(LAYERS.Finish(scene,token,1)=LAYERTYPES.OK)
  Require(scene.visibleDamage=0)
  Require(scene.items(LAYERTYPES.BACKGROUND_SLOT).dirty<>0)
  Require(LAYERS.Invalidate(scene,0,@bounds)=LAYERTYPES.OK)
  Require(scene.visibleDamage=0)
  CheckVisible(scene)
  Require(LAYERS.Show(scene,id,0)=LAYERTYPES.OK)
  Require(scene.visibleDamage=$100)
  Require(LAYERS.Delete(scene,id)=LAYERTYPES.OK)
  Require(LAYERS.FindDamaged(scene,id)=NULL)
  CheckVisible(scene)

  ; Direct frame completion retires only its manager pixels. Client work
  ; remains pending, and an active paint token prevents concurrent completion.
  Require(LAYERS.Create(scene,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.SetExternal(scene,id)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,id,1)=LAYERTYPES.OK)
  BEGIN
    LET layer=LAYERS.Find(scene,id)
    LET epoch=layer.paintEpoch
    REGIONS.Assign(@bounds,0,0,16,24)
    Require(LAYERS.Repaired(scene,id,@bounds)<>0)
    Require(layer.dirty<>0 AND layer.damage.count=1)
    Require(layer.damage.rects(0).left=16)
    Require(layer.pending.count=1 AND layer.paintEpoch=epoch)
    CheckVisible(scene)
    Require(LAYERS.BeginPaint(scene,id,@token)=LAYERTYPES.OK)
    Require(LAYERS.Repaired(scene,id,@bounds)=0)
    Require(LAYERS.Finish(scene,token,0)=LAYERTYPES.OK)
    REGIONS.Assign(@bounds,16,0,32,24)
    Require(LAYERS.Repaired(scene,id,@bounds)<>0)
    ; Aborting an external handoff restores full manager damage. The earlier
    ; half must be completed again before the layer can become clean.
    Require(layer.dirty<>0 AND layer.damage.rects(0).right=16)
    REGIONS.Assign(@bounds,0,0,16,24)
    Require(LAYERS.Repaired(scene,id,@bounds)<>0)
    Require(layer.dirty=0 AND layer.damage.count=0)
    Require(layer.pending.count=1 AND layer.paintEpoch=epoch)
    CheckVisible(scene)
  END
  Require(LAYERS.Delete(scene,id)=LAYERTYPES.OK)

  ; Every normal slot has an independent bit; the background is the ninth.
  FOR index=0 TO LAYERTYPES.MAX_LAYERS-1 DO
    REGIONS.Assign(@bounds,INT(index*4),0,INT(index*4+4),24)
    Require(LAYERS.Create(scene,@bounds,@id)=LAYERTYPES.OK)
    Require(LAYERS.Show(scene,id,1)=LAYERTYPES.OK)
    CheckVisible(scene)
  OD
  Require(scene.visibleDamage=$ff)
  Require(LAYERS.BeginPaint(scene,id,@token)=LAYERTYPES.OK)
  Require(LAYERS.Finish(scene,token,0)=LAYERTYPES.OK)
  Require(scene.visibleDamage=$ff)
  CheckVisible(scene)

RETURN
