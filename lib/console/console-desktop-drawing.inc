; One text fragment per private presenter step. The token freezes geometry and
; model data; callers re-resolve their source under the ordinary view borrow.
; Existing exposure damage stays pending when this repairs only a dirty span.
BYTE FUNC DesktopPart(LAYERTYPES.Rect POINTER bounds BYTE text
    BYTE POINTER source CARD count,foreground,background)
  CARD first,last,stop
  BYTE status,okay
  LAYERTYPES.Rect clip

  LET service=DESKSTATE.Get()
  IF desktopToken=0 THEN
    BEGIN
      LET id=DESKSTATE.Selected()
      IF id=0 THEN
        RETURN(1)
      FI

      LET layer=LAYERS.Find(@service.scene,id)
      IF layer=NULL THEN
        RETURN(0)
      FI

      desktopWasDirty=layer.dirty
      status=LAYERS.Invalidate(@service.scene,id,bounds)
      IF status<>LAYERTYPES.OK THEN
        RETURN(0)
      FI

      status=LAYERS.BeginPaint(@service.scene,id,@desktopToken)
      IF status=LAYERTYPES.EMPTY THEN
        RETURN(1)
      FI

      IF status<>LAYERTYPES.OK THEN
        RETURN(0)
      FI

      desktopIndex=0
      desktopGlyph=0
    END
  FI

  LET region=LAYERS.PaintRegion(@service.scene,desktopToken)
  okay=1
  WHILE desktopIndex<region.count DO
    REGIONS.Intersect(bounds,@region.rects(desktopIndex),@clip)
    IF REGIONS.Empty(@clip)=0 THEN
      IF text<>0 THEN
        ; Skip invisible whole cells; retain pixel clipping at partial edges.
        first=CARD(clip.left-bounds.left) RSH 3
        last=(CARD(clip.right-bounds.left)+7) RSH 3
        IF last>count THEN
          last=count
        FI

        IF desktopGlyph<first THEN
          desktopGlyph=first
        FI

        stop=desktopGlyph+TEXT_GLYPHS
        IF clip.top>bounds.top OR clip.bottom<bounds.bottom THEN
          stop=desktopGlyph+CLIPPED_GLYPHS
        FI

        IF stop>last THEN
          stop=last
        FI

        okay=ClippedText(CARD(bounds.left)+(desktopGlyph LSH 3),CARD(bounds.top),
            source+SIZE(desktopGlyph),stop-desktopGlyph,foreground,background,@clip)
        IF okay=0 THEN
          EXIT
        FI

        desktopGlyph=stop
        IF desktopGlyph<last THEN
          RETURN(2)
        FI
      ELSE
        okay=RawFill(CARD(clip.left),CARD(clip.top),CARD(clip.right-clip.left),
            CARD(clip.bottom-clip.top),background)
        IF okay=0 THEN
          EXIT
        FI
      FI

      desktopIndex==+1
      desktopGlyph=0
      EXIT
    FI

    desktopIndex==+1
  OD

  IF okay<>0 THEN
    IF desktopIndex<region.count THEN
      RETURN(2)
    FI

    status=LAYERS.AdvancePaint(@service.scene,desktopToken)
    IF status=LAYERTYPES.OK THEN
      desktopIndex=0
      RETURN(2)
    FI

    okay=(status=LAYERTYPES.EMPTY)
  FI

  status=LAYERS.Finish(@service.scene,desktopToken,okay<>0 AND desktopWasDirty=0)
  desktopToken=0

RETURN(okay)

; Synchronous public primitives drain the same fragment traversal before
; returning. Only the private console presenter can retain it across turns.
BYTE FUNC DesktopDraw(LAYERTYPES.Rect POINTER bounds BYTE text
    BYTE POINTER source CARD count,foreground,background)
  BYTE status

  DO
    status=DesktopPart(bounds,text,source,count,foreground,background)
    IF status<>2 THEN
      RETURN(status)
    FI
  OD

RETURN(0)
