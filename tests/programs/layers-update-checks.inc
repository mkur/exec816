; Admission and completion must not borrow caller arguments or confuse a
; stale completion with a later operation on the same layer.
PROC UpdateTransactions()
  LAYERTYPES.Scene POINTER state
  LAYERTYPES.Layer POINTER layer
  LAYERTYPES.Region POINTER region
  LAYERTYPES.Rect bounds,source,target,part
  LONGCARD id,other,token,old,untouched,rebuilds

  scenePhase=40
  state=LAYERTYPES.Scene POINTER(Guarded(LAYERTYPES.SCENE_SIZE))
  Require(LAYERS.Init(state,32,24)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,0,0,16,16)
  REGIONS.Assign(@source,0,1,16,16)
  REGIONS.Assign(@target,0,0,16,15)
  Require(LAYERS.Create(state,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.Show(state,id,1)=LAYERTYPES.OK)
  layer=LAYERS.Find(state,id)
  Require(LAYERS.BeginCopy(state,id,@source,@target,@token)=LAYERTYPES.REDRAW)
  Require(LAYERS.BeginPaint(state,id,@token)=LAYERTYPES.OK)
  old=token
  untouched=12345
  Require(LAYERS.BeginPaint(state,id,@untouched)=LAYERTYPES.BUSY)
  Require(LAYERS.BeginCopy(state,id,@source,@target,@untouched)=LAYERTYPES.BUSY)
  Require(LAYERS.Move(state,id,1,1)=LAYERTYPES.BUSY)
  Require(LAYERS.Show(state,id,0)=LAYERTYPES.BUSY)
  Require(LAYERS.Order(state,id,0)=LAYERTYPES.BUSY)
  Require(LAYERS.Delete(state,id)=LAYERTYPES.BUSY)
  Require(LAYERS.Create(state,@bounds,@untouched)=LAYERTYPES.BUSY)
  Require(LAYERS.Invalidate(state,id,@bounds)=LAYERTYPES.BUSY)
  Require(untouched=12345)
  Require(LAYERS.Finish(state,0,1)=LAYERTYPES.BAD_TOKEN)
  Require(LAYERS.Finish(state,token,2)=LAYERTYPES.BAD_ARGUMENT)
  EXEC.Yield()
  Require(state.busy=token AND layer.shown<>0)
  Require(LAYERS.PaintRegion(state,token)<>NULL)
  Require(LAYERS.Finish(state,token,0)=LAYERTYPES.OK)
  Require(layer.dirty<>0)
  Require(LAYERS.BeginPaint(state,id,@token)=LAYERTYPES.OK)
  Require(token<>old)
  Require(LAYERS.Finish(state,old,1)=LAYERTYPES.BAD_TOKEN)
  Require(LAYERS.PaintRegion(state,old)=NULL)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)
  Require(layer.dirty=0)
  Require(LAYERS.BeginPaint(state,id,@untouched)=LAYERTYPES.EMPTY)
  Require(untouched=12345)

  ; Copy preparation captures descriptors before the caller reuses them.
  scenePhase=41
  Require(LAYERS.BeginCopy(state,id,@source,@target,@token)=LAYERTYPES.OK)
  REGIONS.Assign(@source,0,0,0,0)
  Require(state.copySource.top=1 AND state.copySource.bottom=16)
  Require(state.copyTarget.bottom=15)
  Require(LAYERS.PaintRegion(state,token)=NULL)
  Require(LAYERS.Finish(state,token,0)=LAYERTYPES.OK)
  Require(layer.dirty<>0 AND REGIONS.Equal(@layer.damage,@bounds)<>0)
  Require(LAYERS.BeginPaint(state,id,@token)=LAYERTYPES.OK)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)

  ; Invalid geometry and empty copies must not consume a token or change it.
  REGIONS.Assign(@source,0,1,16,16)
  REGIONS.Assign(@target,0,0,15,15)
  Require(LAYERS.BeginCopy(state,id,@source,@target,@untouched)=LAYERTYPES.BAD_ARGUMENT)
  REGIONS.Assign(@source,-1,0,15,15)
  REGIONS.Assign(@target,0,0,16,15)
  Require(LAYERS.BeginCopy(state,id,@source,@target,@untouched)=LAYERTYPES.BAD_ARGUMENT)
  Require(LAYERS.BeginCopy(state,id,NULL,@target,@untouched)=LAYERTYPES.BAD_ARGUMENT)
  REGIONS.Assign(@source,0,0,0,0)
  REGIONS.Assign(@target,1,1,1,1)
  Require(LAYERS.BeginCopy(state,id,@source,@target,@untouched)=LAYERTYPES.EMPTY)
  Require(untouched=12345 AND state.busy=0)

  scenePhase=42
  rebuilds=state.rebuilds
  REGIONS.Assign(@part,3,3,6,5)
  Require(LAYERS.Invalidate(state,id,@part)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(state,id,@token)=LAYERTYPES.OK)
  region=LAYERS.PaintRegion(state,token)
  Require(region.count=1 AND REGIONS.Equal(@region.rects(0),@part)<>0)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)
  Require(state.rebuilds=rebuilds)
  Require(LAYERS.Show(state,id,0)=LAYERTYPES.OK)
  Require(LAYERS.Invalidate(state,id,@part)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(state,id,@untouched)=LAYERTYPES.EMPTY)
  Require(untouched=12345 AND layer.dirty<>0)
  Require(LAYERS.Show(state,id,1)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(state,id,@token)=LAYERTYPES.OK)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)

  ; Even an individually visible copy pair takes the conservative fallback
  ; when another part of the layer is covered.
  scenePhase=43
  Require(LAYERS.Create(state,@part,@other)=LAYERTYPES.OK)
  Require(LAYERS.Show(state,other,1)=LAYERTYPES.OK)
  ; Showing the upper layer damaged only pixels it now covers. No visible
  ; paint is required until we deliberately invalidate the whole lower layer.
  Require(LAYERS.BeginPaint(state,id,@untouched)=LAYERTYPES.EMPTY)
  Require(untouched=12345 AND state.busy=0)
  Require(LAYERS.Invalidate(state,id,@bounds)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(state,id,@token)=LAYERTYPES.OK)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)
  REGIONS.Assign(@source,8,8,10,10)
  REGIONS.Assign(@target,10,10,12,12)
  Require(LAYERS.BeginCopy(state,id,@source,@target,@untouched)=LAYERTYPES.REDRAW)
  Require(untouched=12345 AND state.busy=0)
  Require(LAYERS.Delete(state,other)=LAYERTYPES.OK)

  scenePhase=44
  state.nextToken=$ffffffff
  Require(LAYERS.BeginPaint(state,id,@token)=LAYERTYPES.OK)
  Require(token=$ffffffff AND state.nextToken=0)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)
  Require(LAYERS.BeginCopy(state,id,@source,@target,@untouched)=LAYERTYPES.EXHAUSTED)
  Require(LAYERS.Invalidate(state,id,@part)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(state,id,@untouched)=LAYERTYPES.EXHAUSTED)
  Require(untouched=12345 AND state.busy=0 AND layer.dirty<>0)
  Require(LAYERS.Delete(state,id)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(state,id,@token)=LAYERTYPES.BAD_ID)
  Require(LAYERS.BeginPaint(state,0,NULL)=LAYERTYPES.BAD_ARGUMENT)
  Require(LAYERS.Invalidate(state,0,NULL)=LAYERTYPES.BAD_ARGUMENT)
  scenePhase=45
  FreeGuarded(BYTE POINTER(state),LAYERTYPES.SCENE_SIZE)

RETURN
