; External work survives handoff. Only explicit completion retires it.
PUBLIC PROC RequirePaint(LAYERTYPES.Scene POINTER scene LONGCARD id
    LAYERTYPES.Rect POINTER area)
  LAYERTYPES.Rect clipped

  LET layer=Find(scene,id)
  REGIONS.Intersect(@layer.bounds,area,@clipped)
  IF REGIONS.Empty(@clipped)<>0 THEN
    RETURN
  FI
  AddDamage(@layer.pending,@clipped)
  IF layer.paintEpoch<>0 THEN
    layer.paintEpoch==+1
  FI

RETURN

; Establish the client extent while creating or resizing an external window.
PUBLIC PROC ExternalArea(LAYERTYPES.Scene POINTER scene LONGCARD id
    LAYERTYPES.Rect POINTER area)

  LET layer=Find(scene,id)
  layer.pending.count=0
  RequirePaint(scene,id,area)

RETURN

; A model/update boundary invalidates snapshots without inventing screen paint.
PUBLIC PROC Touch(LAYERTYPES.Scene POINTER scene LONGCARD id)

  LET layer=Find(scene,id)
  LAYERCACHE.Changed(@scene.under,id,@layer.bounds)
  IF layer.contentRevision<>0 THEN
    layer.contentRevision==+1
  FI

RETURN

PROC PaintPiece(LAYERTYPES.Scene POINTER scene INT left,top,right,bottom)

  IF left<right AND top<bottom THEN
    REGIONS.Assign(@scene.work.rects(scene.work.count),left,top,right,bottom)
    scene.work.count==+1
  FI

RETURN

; At most eight pending rectangles produce 32 pieces in the existing workspace.
; Overflow retains the old obligation rather than widening completed coverage.
BYTE FUNC SubtractDamage(LAYERTYPES.Scene POINTER scene
    LAYERTYPES.Damage POINTER damage LAYERTYPES.Rect POINTER area)
  LAYERTYPES.Rect overlap
  BYTE index

  IF damage.count=0 THEN
    RETURN(1)
  FI
  IF damage.count=1 AND REGIONS.Contains(area,@damage.rects(0))<>0 THEN
    damage.count=0
    RETURN(1)
  FI
  scene.work.count=0
  index=0
  WHILE index<damage.count DO
    BEGIN
      LET dirty=@damage.rects(index)
      REGIONS.Intersect(dirty,area,@overlap)
      IF REGIONS.Empty(@overlap)<>0 THEN
        PaintPiece(scene,dirty.left,dirty.top,dirty.right,dirty.bottom)
      ELSE
        PaintPiece(scene,dirty.left,dirty.top,dirty.right,overlap.top)
        PaintPiece(scene,dirty.left,overlap.bottom,dirty.right,dirty.bottom)
        PaintPiece(scene,dirty.left,overlap.top,overlap.left,overlap.bottom)
        PaintPiece(scene,overlap.right,overlap.top,dirty.right,overlap.bottom)
      FI
    END
    index==+1
  OD
  IF scene.work.count>LAYERTYPES.MAX_DAMAGE THEN
    RETURN(0)
  FI
  damage.count=BYTE(scene.work.count)
  IF scene.work.count<>0 THEN
    A816MEMORY.Move(BYTE POINTER(@damage.rects(0)),
        BYTE POINTER(@scene.work.rects(0)),SIZE(scene.work.count*8))
  FI

RETURN(1)

PUBLIC BYTE FUNC Painted(LAYERTYPES.Scene POINTER scene LONGCARD id,
    epoch LAYERTYPES.Rect POINTER area)

  LET layer=Find(scene,id)
  IF scene.busy<>0 OR epoch=0 OR epoch<>layer.paintEpoch THEN
    RETURN(0)
  FI

RETURN(SubtractDamage(scene,@layer.pending,area))

; Capturing pixels requires no outstanding work intersecting the source.
PUBLIC BYTE FUNC PixelsReady(LAYERTYPES.Layer POINTER layer
    LAYERTYPES.Rect POINTER area)
  LAYERTYPES.Rect overlap
  BYTE index

  IF layer.dirty<>0 THEN
    index=0
    WHILE index<layer.damage.count DO
      REGIONS.Intersect(@layer.damage.rects(index),area,@overlap)
      IF REGIONS.Empty(@overlap)=0 THEN
        RETURN(0)
      FI
      index==+1
    OD
  FI
  IF layer.externalPaint<>0 THEN
    index=0
    WHILE index<layer.pending.count DO
      REGIONS.Intersect(@layer.pending.rects(index),area,@overlap)
      IF REGIONS.Empty(@overlap)=0 THEN
        RETURN(0)
      FI
      index==+1
    OD
  FI

RETURN(1)
