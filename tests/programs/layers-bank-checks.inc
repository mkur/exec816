; The complete caller-owned scene crosses a CPU bank. Region arrays and scalar
; update state must use native far addressing, including a real 640x240 scene.
PROC BankCrossing()
  LAYERTYPES.Scene POINTER state
  LAYERTYPES.Rect bounds
  LONGCARD id,token
  BYTE slot

  state=LAYERTYPES.Scene POINTER($11fff0)
  Require(LAYERS.Init(state,640,240)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,64,40,192,80)
  Require(LAYERS.Create(state,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.Show(state,id,1)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,256,96,384,136)
  Require(LAYERS.Create(state,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.Show(state,id,1)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,448,152,576,192)
  Require(LAYERS.Create(state,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.Show(state,id,1)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,160,168,288,216)
  Require(LAYERS.Create(state,@bounds,@id)=LAYERTYPES.OK)
  Require(LAYERS.Show(state,id,1)=LAYERTYPES.OK)

  FOR slot=0 TO LAYERTYPES.SLOT_COUNT-1 DO
    Require(LAYERS.BeginPaint(state,state.items(slot).id,@token)=LAYERTYPES.OK)
    Require(LAYERS.PaintRegion(state,token)=@state.work)
    ExhaustPaint(state,token)
    Require(LAYERS.Finish(state,token,1)=LAYERTYPES.OK)
  OD

  Require(state.rebuilds=5 AND state.busy=0)

RETURN
