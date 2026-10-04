; A software drawing backend consumes the same clipped updates that a later
; VBXE presenter will consume. Retained pixels never come from the screen.

BYTE FUNC ModelSlot(LONGCARD id)
  BYTE slot

  slot=0
  WHILE slot<LAYERTYPES.MAX_LAYERS DO
    IF scene.items(slot).id=id THEN
      RETURN(slot)
    FI

    slot==+1
  OD

  Require(0)

RETURN(0)

PROC CreateModel(LONGCARD id)
  CARD index

  LET slot=ModelSlot(id)
  LET pixels=model+SIZE(CARD(slot)*768)
  FOR index=0 TO 767 DO
    pixels(index)=BYTE((index+CARD(id)*17) & 127)
  OD

RETURN

PROC ChangeModel(LONGCARD id LAYERTYPES.Rect POINTER area BYTE value)
  CARD x,y
  LAYERTYPES.Rect clipped

  LET slot=ModelSlot(id)
  LET layer=@scene.items(slot)
  LET pixels=model+SIZE(CARD(slot)*768)
  REGIONS.Intersect(@layer.bounds,area,@clipped)
  IF REGIONS.Empty(@clipped)=0 THEN
    FOR y=CARD(clipped.top) TO CARD(clipped.bottom)-1 DO
      FOR x=CARD(clipped.left) TO CARD(clipped.right)-1 DO
        pixels((y-CARD(layer.bounds.top))*32+x-CARD(layer.bounds.left))=value
      OD
    OD
  FI

  Require(LAYERS.Invalidate(scene,id,area)=LAYERTYPES.OK)

RETURN

PROC PaintScene()
  BYTE slot,status
  CARD index,y,width
  LONGCARD token
  LAYERTYPES.Region POINTER region
  LAYERTYPES.Rect POINTER rect
  LAYERTYPES.Layer POINTER layer
  BYTE POINTER target,source,pixels

  FOR slot=0 TO LAYERTYPES.SLOT_COUNT-1 DO
    layer=@scene.items(slot)
    IF layer.id<>0 OR slot=LAYERTYPES.BACKGROUND_SLOT THEN
      status=LAYERS.BeginPaint(scene,layer.id,@token)
      Require(status=LAYERTYPES.OK OR status=LAYERTYPES.EMPTY)
      IF status=LAYERTYPES.OK THEN
        region=LAYERS.PaintRegion(scene,token)
        Require(region<>NULL AND region.count<>0)
        IF region.count>maxPaintRects THEN
          maxPaintRects=region.count
        FI
        pixels=model+SIZE(CARD(slot)*768)
        index=0
        WHILE index<region.count DO
          rect=@region.rects(index)
          width=CARD(rect.right-rect.left)
          FOR y=CARD(rect.top) TO CARD(rect.bottom)-1 DO
            target=canvas+SIZE(y*32+CARD(rect.left))
            IF slot=LAYERTYPES.BACKGROUND_SLOT THEN
              A816MEMORY.Fill(target,0,SIZE(width))
            ELSE
              source=pixels+SIZE((y-CARD(layer.bounds.top))*32
                  +CARD(rect.left-layer.bounds.left))
              A816MEMORY.Move(target,source,SIZE(width))
            FI
          OD

          index==+1
        OD

        Require(LAYERS.Finish(scene,token,1)=LAYERTYPES.OK)
        paints==+1
      FI
    FI
  OD

RETURN

; Exercise a full-rectangle upward copy/fill or redraw fallback, using
; independent retained pixels and a screen that may contain other layers.
PROC ScrollModel(LONGCARD id)
  LAYERTYPES.Rect source,target
  CARD y,width,height
  BYTE status
  LONGCARD token
  BYTE POINTER pixels,row

  LET slot=ModelSlot(id)
  LET layer=@scene.items(slot)
  pixels=model+SIZE(CARD(slot)*768)
  width=CARD(layer.bounds.right-layer.bounds.left)
  height=CARD(layer.bounds.bottom-layer.bounds.top)
  REGIONS.Assign(@source,layer.bounds.left,layer.bounds.top+1,
      layer.bounds.right,layer.bounds.bottom)
  REGIONS.Assign(@target,layer.bounds.left,layer.bounds.top,
      layer.bounds.right,layer.bounds.bottom-1)
  status=LAYERS.BeginCopy(scene,id,@source,@target,@token)
  Require(status=LAYERTYPES.OK OR status=LAYERTYPES.REDRAW)
  FOR y=0 TO height-2 DO
    A816MEMORY.Move(pixels+SIZE(y*32),pixels+SIZE((y+1)*32),SIZE(width))
  OD

  A816MEMORY.Fill(pixels+SIZE((height-1)*32),77,SIZE(width))
  IF status=LAYERTYPES.OK THEN
    FOR y=CARD(target.top) TO CARD(target.bottom)-1 DO
      row=canvas+SIZE(y*32+CARD(target.left))
      A816MEMORY.Move(row,row+32,SIZE(width))
    OD

    A816MEMORY.Fill(canvas+SIZE(CARD(target.bottom)*32+CARD(target.left)),
        77,SIZE(width))
    Require(LAYERS.Finish(scene,token,1)=LAYERTYPES.OK)
    copies==+1
  ELSE
    Require(LAYERS.Invalidate(scene,id,@layer.bounds)=LAYERTYPES.OK)
    redraws==+1
  FI

RETURN
