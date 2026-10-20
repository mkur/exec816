; Damage delivery is distinct from painting and never licenses pixel reuse.
PROC ExternalTransactions()
  LAYERTYPES.Rect bounds,part
  LONGCARD id,token,other,epoch
  BYTE index

  Require(LAYERS.Init(scene,32,24)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,0,0,16,16)
  Require(LAYERS.Create(scene,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.SetExternal(scene,id)=LAYERTYPES.OK)
  Require(LAYERS.SetRetained(scene,id)=LAYERTYPES.OK)
  BEGIN
    LET layer=LAYERS.Find(scene,id)
    Require(layer.externalPaint=0 AND layer.pending.count=0)
  END
  Require(LAYERS.SetExternal(scene,id)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,id,1)=LAYERTYPES.OK)
  Require(LAYERS.SetRetained(scene,id)=LAYERTYPES.BUSY)
  Require(LAYERS.BeginPaint(scene,id,@token)=LAYERTYPES.OK)
  Require(LAYERS.SetRetained(scene,id)=LAYERTYPES.BUSY)
  Require(scene.activeKind=LAYERTYPES.UPDATE_HANDOFF)
  Require(LAYERS.Finish(scene,token,1)=LAYERTYPES.BAD_ARGUMENT)
  CheckVisible(scene)
  Require(LAYERS.FinishHandoff(scene,token)=LAYERTYPES.BUSY)
  CheckVisible(scene)
  Require(LAYERS.Delete(scene,id)=LAYERTYPES.BUSY)
  CheckVisible(scene)
  ExhaustPaint(scene,token)
  Require(LAYERS.FinishHandoff(scene,token)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(scene.busy=0)
  BEGIN
    LET layer=LAYERS.Find(scene,id)
    Require(layer.pending.count=1)
    Require(LAYERS.PixelsReady(layer,@bounds)=0)
    epoch=layer.paintEpoch
    REGIONS.Assign(@part,0,0,8,16)
    Require(LAYERS.Painted(scene,id,epoch,@part)=1)
    CheckVisible(scene)
    Require(layer.pending.count=1)
    Require(LAYERS.PixelsReady(layer,@part)=1)
    Require(LAYERS.PixelsReady(layer,@bounds)=0)
    Require(LAYERS.BeginRead(scene,id,@bounds,@other)=LAYERTYPES.REDRAW)
    Require(LAYERS.BeginRead(scene,id,@part,@other)=LAYERTYPES.OK)
    Require(LAYERS.Finish(scene,other,1)=LAYERTYPES.OK)
    CheckVisible(scene)
    REGIONS.Assign(@part,8,0,16,8)
    LAYERS.RequirePaint(scene,id,@part)
    Require(LAYERS.Painted(scene,id,epoch,@bounds)=0)
    CheckVisible(scene)
    Require(layer.pending.count=1)
    Require(LAYERS.Painted(scene,id,layer.paintEpoch,@part)=1)
    CheckVisible(scene)
    Require(layer.pending.count=1)
    REGIONS.Assign(@part,8,8,16,16)
    Require(LAYERS.Painted(scene,id,layer.paintEpoch,@part)=1)
    CheckVisible(scene)
    Require(layer.pending.count=0)
    Require(LAYERS.PixelsReady(layer,@bounds)=1)
    Require(LAYERS.BeginRead(scene,id,@bounds,@other)=LAYERTYPES.OK)
    Require(LAYERS.Show(scene,id,0)=LAYERTYPES.BUSY)
    Require(LAYERS.Finish(scene,other,1)=LAYERTYPES.OK)
    CheckVisible(scene)
    ; Completed external pixels move without a new client obligation.
    epoch=layer.paintEpoch
    Require(LAYERS.BeginMove(scene,id,8,4,@other)=LAYERTYPES.OK)
    Require(layer.bounds.left=0)
    Require(LAYERS.Delete(scene,id)=LAYERTYPES.BUSY)
    CheckVisible(scene)
    Require(LAYERS.Finish(scene,other,1)=LAYERTYPES.OK)
    CheckVisible(scene)
    Require(layer.bounds.left=8 AND layer.bounds.top=4)
    Require(layer.pending.count=0 AND layer.dirty=0)
    Require(LAYERS.Painted(scene,id,epoch,@bounds)=0)
    CheckVisible(scene)
    Require(LAYERS.BeginMove(scene,id,0,0,@other)=LAYERTYPES.OK)
    Require(LAYERS.Finish(scene,other,1)=LAYERTYPES.OK)
    CheckVisible(scene)
    Require(REGIONS.Equal(@layer.bounds,@bounds)=1)
    ; Client obligations exclude title/frame pixels.
    REGIONS.Assign(@part,2,4,14,14)
    LAYERS.ExternalArea(scene,id,@part)
    Require(REGIONS.Equal(@layer.pending.rects(0),@part)=1)
    Require(LAYERS.Painted(scene,id,layer.paintEpoch,@part)=1)
    CheckVisible(scene)
    ; Disjoint completions leave the hole unknown.
    LAYERS.RequirePaint(scene,id,@bounds)
    REGIONS.Assign(@part,2,2,14,14)
    Require(LAYERS.Painted(scene,id,layer.paintEpoch,@part)=1)
    CheckVisible(scene)
    Require(layer.pending.count=4)
    Require(LAYERS.PixelsReady(layer,@part)=1)
    Require(LAYERS.PixelsReady(layer,@bounds)=0)
    Require(LAYERS.Painted(scene,id,layer.paintEpoch,@bounds)=1)
    CheckVisible(scene)
    ; More than eight subtraction fragments must retain the old obligation.
    FOR index=0 TO 7 DO
      REGIONS.Assign(@part,0,INT(index)*2,16,INT(index)*2+1)
      LAYERS.RequirePaint(scene,id,@part)
    OD
    Require(layer.pending.count=8)
    REGIONS.Assign(@part,4,0,12,16)
    Require(LAYERS.Painted(scene,id,layer.paintEpoch,@part)=0)
    CheckVisible(scene)
    Require(layer.pending.count=8)
    Require(LAYERS.Painted(scene,id,layer.paintEpoch,@bounds)=1)
    CheckVisible(scene)
    epoch=layer.contentRevision
    LAYERS.Touch(scene,id)
    Require(layer.contentRevision=epoch+1)
    ; Exhaustion cannot let a late completion match a recycled generation.
    layer.paintEpoch=$ffffffff
    LAYERS.RequirePaint(scene,id,@bounds)
    Require(layer.paintEpoch=0)
    Require(LAYERS.Painted(scene,id,0,@bounds)=0)
    CheckVisible(scene)
    layer.paintEpoch=1
  END
  Require(LAYERS.FinishHandoff(scene,token)=LAYERTYPES.BAD_TOKEN)
  CheckVisible(scene)
  Require(LAYERS.BeginCopy(scene,id,@bounds,@bounds,@other)=LAYERTYPES.REDRAW)
  Require(LAYERS.BeginRead(scene,id,@bounds,@other)=LAYERTYPES.REDRAW)
  Require(LAYERS.BeginMove(scene,id,1,1,@other)=LAYERTYPES.REDRAW)
  Require(LAYERS.Invalidate(scene,id,@bounds)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(scene,id,@token)=LAYERTYPES.OK)
  Require(LAYERS.Finish(scene,token,0)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.BeginPaint(scene,id,@token)=LAYERTYPES.OK)
  ExhaustPaint(scene,token)
  Require(LAYERS.FinishHandoff(scene,token)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.Delete(scene,id)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.Create(scene,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,id,1)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(scene,id,@token)=LAYERTYPES.OK)
  Require(scene.activeKind=LAYERTYPES.UPDATE_PAINT)
  Require(LAYERS.FinishHandoff(scene,token)=LAYERTYPES.BAD_TOKEN)
  CheckVisible(scene)
  ExhaustPaint(scene,token)
  Require(LAYERS.Finish(scene,token,1)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.BeginCopy(scene,id,@bounds,@bounds,@token)=LAYERTYPES.OK)
  Require(LAYERS.Finish(scene,token,1)=LAYERTYPES.OK)
  CheckVisible(scene)
  Require(LAYERS.Delete(scene,id)=LAYERTYPES.OK)
  CheckVisible(scene)

RETURN

; Exercise the shared subtraction through public completion. The host checks
; the remaining union independently, including overlapping damage rectangles.
PROC DamageRetirement(CARD count)
  CARD index
  BYTE POINTER input,output
  LAYERTYPES.Rect bounds
  LONGCARD id,epoch

  scenePhase=60
  Require(LAYERS.Init(scene,32,24)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,0,0,32,24)
  Require(LAYERS.Create(scene,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.SetExternal(scene,id)=LAYERTYPES.OK)
  LET layer=LAYERS.Find(scene,id)
  epoch=layer.paintEpoch
  Require(epoch<>0)
  input=BYTE POINTER($d8002)
  output=BYTE POINTER($d9010)
  FOR index=0 TO count-1 DO
    A816MEMORY.Move(BYTE POINTER(@layer.pending),input,LAYERTYPES.DAMAGE_SIZE)
    Require(LAYERS.Painted(scene,id,epoch,
        LAYERTYPES.Rect POINTER(input+LAYERTYPES.DAMAGE_SIZE))
        =input(LAYERTYPES.DAMAGE_SIZE+LAYERTYPES.RECT_SIZE))
    Require(layer.paintEpoch=epoch AND scene.busy=0)
    A816MEMORY.Move(output,BYTE POINTER(@layer.pending),LAYERTYPES.DAMAGE_SIZE)
    input==+LAYERTYPES.DAMAGE_SIZE+LAYERTYPES.RECT_SIZE+1
    output==+LAYERTYPES.DAMAGE_SIZE
  OD
  Require(LAYERS.Delete(scene,id)=LAYERTYPES.OK)

RETURN
