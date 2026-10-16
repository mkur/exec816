; Capture independent pixel partitions and incremental software painting for
; a covering layer beneath a crossing overlay and an edge-touching neighbour.
PROC RebuildOccluders(INT half)
  LAYERTYPES.Rect bounds
  LONGCARD base,cover,neighbour,overlay
  BYTE POINTER output

  Require(LAYERS.Init(scene,32,24)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,0,0,half,24)
  Require(LAYERS.Create(scene,@bounds,@base)=LAYERTYPES.OK)
  CreateModel(base)
  Require(LAYERS.Show(scene,base,1)=LAYERTYPES.OK)
  Require(LAYERS.Create(scene,@bounds,@cover)=LAYERTYPES.OK)
  CreateModel(cover)
  Require(LAYERS.Show(scene,cover,1)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,half,0,32,24)
  Require(LAYERS.Create(scene,@bounds,@neighbour)=LAYERTYPES.OK)
  CreateModel(neighbour)
  Require(LAYERS.Show(scene,neighbour,1)=LAYERTYPES.OK)
  REGIONS.Assign(@bounds,4,4,12,8)
  Require(LAYERS.Create(scene,@bounds,@overlay)=LAYERTYPES.OK)
  CreateModel(overlay)
  Require(LAYERS.Show(scene,overlay,1)=LAYERTYPES.OK)
  output=BYTE POINTER($e6010)
  Snapshot(output)

  Require(LAYERS.Show(scene,cover,0)=LAYERTYPES.OK)
  Snapshot(output+1540)

  Require(LAYERS.Move(scene,cover,half/2,0)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,cover,1)=LAYERTYPES.OK)
  Require(LAYERS.Order(scene,cover,1)=LAYERTYPES.OK)
  Snapshot(output+3080)

  Require(LAYERS.Show(scene,cover,0)=LAYERTYPES.OK)
  Require(LAYERS.Show(scene,base,0)=LAYERTYPES.OK)
  Snapshot(output+4620)

RETURN
