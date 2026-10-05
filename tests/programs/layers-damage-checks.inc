; Sparse damage remains distinct; all batches belong to one stable transaction.
PROC DamageTransactions()
  LAYERTYPES.Scene POINTER state
  LAYERTYPES.Layer POINTER layer
  LAYERTYPES.Rect bounds
  LONGCARD token,id
  BYTE index,status
  CARD fragments

  scenePhase=50
  state=LAYERTYPES.Scene POINTER(Guarded(LAYERTYPES.SCENE_SIZE))
  Require(LAYERS.Init(state,640,240)=LAYERTYPES.OK)
  layer=LAYERS.Find(state,0)
  Require(LAYERS.BeginPaint(state,0,@token)=LAYERTYPES.OK)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.BUSY)
  Require(state.busy=token AND layer.dirty<>0)
  ExhaustPaint(state,token)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)
  FOR index=0 TO 7 DO
    REGIONS.Assign(@bounds,INT(index*16),0,INT(index*16+4),4)
    Require(LAYERS.Invalidate(state,0,@bounds)=LAYERTYPES.OK)
  OD

  Require(layer.damage.count=8)
  REGIONS.Assign(@bounds,1,1,3,3)
  Require(LAYERS.Invalidate(state,0,@bounds)=LAYERTYPES.OK)
  Require(layer.damage.count=8)
  Require(LAYERS.BeginPaint(state,0,@token)=LAYERTYPES.OK)
  fragments=0
  DO
    fragments==+state.work.count
    status=LAYERS.AdvancePaint(state,token)
    IF status<>LAYERTYPES.OK THEN
      EXIT
    FI
  OD

  Require(status=LAYERTYPES.EMPTY AND fragments=8)
  Require(LAYERS.Finish(state,token,0)=LAYERTYPES.OK)
  Require(layer.damage.count=8)
  REGIONS.Assign(@bounds,128,0,132,4)
  Require(LAYERS.Invalidate(state,0,@bounds)=LAYERTYPES.OK)
  Require(layer.damage.count=1 AND layer.damage.rects(0).right=132)
  Require(LAYERS.BeginPaint(state,0,@token)=LAYERTYPES.OK)
  ExhaustPaint(state,token)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)

  ; Four disjoint occluders leave thirteen background pieces. Eight overlapping
  ; but nonmergeable damage rectangles exercise more than one work buffer's worth.
  FOR index=0 TO 3 DO
    REGIONS.Assign(@bounds,INT(40+index*128),INT(20+index*40),
        INT(80+index*128),INT(40+index*40))
    Require(LAYERS.Create(state,@bounds,@id)=LAYERTYPES.OK)
    Require(LAYERS.Show(state,id,1)=LAYERTYPES.OK)
  OD

  REGIONS.Copy(@state.screen,@bounds)
  Require(LAYERS.Invalidate(state,0,@bounds)=LAYERTYPES.OK)
  Require(LAYERS.BeginPaint(state,0,@token)=LAYERTYPES.OK)
  ExhaustPaint(state,token)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)
  FOR index=0 TO 7 DO
    REGIONS.Assign(@bounds,INT(index),0,640,INT(232+index))
    Require(LAYERS.Invalidate(state,0,@bounds)=LAYERTYPES.OK)
  OD

  Require(layer.damage.count=8)
  Require(LAYERS.BeginPaint(state,0,@token)=LAYERTYPES.OK)
  fragments=0
  index=0
  DO
    A816MEMORY.Move(BYTE POINTER($e4010)+SIZE(CARD(index)*LAYERTYPES.REGION_SIZE),
        BYTE POINTER(@state.work),LAYERTYPES.REGION_SIZE)
    index==+1
    Require(state.work.count<=LAYERTYPES.MAX_RECTS)
    fragments==+state.work.count
    status=LAYERS.AdvancePaint(state,token)
    IF status<>LAYERTYPES.OK THEN
      EXIT
    FI
  OD

  Require(status=LAYERTYPES.EMPTY AND fragments>LAYERTYPES.MAX_RECTS)
  Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)
  Require(layer.dirty=0 AND layer.damage.count=0)
  FreeGuarded(BYTE POINTER(state),LAYERTYPES.SCENE_SIZE)

RETURN
