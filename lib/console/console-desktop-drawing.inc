; One synchronous primitive holds a scene token across every clipped fragment.
; Existing exposure damage is left pending when this paints only a dirty span.
BYTE FUNC DesktopDraw(LAYERTYPES.Rect POINTER bounds BYTE text
    BYTE POINTER source CARD count,foreground,background)
  CARD index
  LONGCARD token
  BYTE status,wasDirty,okay
  LAYERTYPES.Rect clip

  LET service=DESKSTATE.Get()
  LET id=DESKSTATE.Selected()
  IF id=0 THEN
    RETURN(1)
  FI

  LET layer=LAYERS.Find(@service.scene,id)
  IF layer=NULL THEN
    RETURN(0)
  FI

  wasDirty=layer.dirty
  status=LAYERS.Invalidate(@service.scene,id,bounds)
  IF status<>LAYERTYPES.OK THEN
    RETURN(0)
  FI

  status=LAYERS.BeginPaint(@service.scene,id,@token)
  IF status=LAYERTYPES.EMPTY THEN
    RETURN(1)
  FI

  IF status<>LAYERTYPES.OK THEN
    RETURN(0)
  FI

  LET region=LAYERS.PaintRegion(@service.scene,token)
  okay=1
  index=0
  WHILE index<region.count AND okay<>0 DO
    REGIONS.Intersect(bounds,@region.rects(index),@clip)
    IF REGIONS.Empty(@clip)=0 THEN
      IF text<>0 THEN
        okay=ClippedText(CARD(bounds.left),CARD(bounds.top),source,count,
            foreground,background,@clip)
      ELSE
        okay=RawFill(CARD(clip.left),CARD(clip.top),CARD(clip.right-clip.left),
            CARD(clip.bottom-clip.top),background)
      FI
    FI

    index==+1
  OD

  status=LAYERS.Finish(@service.scene,token,okay<>0 AND wasDirty=0)

RETURN(okay)
