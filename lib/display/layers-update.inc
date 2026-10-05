; Ordinary calls from the scene owner. Tokens retain metadata, not hardware.

PUBLIC BYTE FUNC Invalidate(LAYERTYPES.Scene POINTER scene LONGCARD id
    LAYERTYPES.Rect POINTER rect)
  BYTE status
  LAYERTYPES.Layer POINTER layer

  status=Admit(scene)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI

  IF REGIONS.Valid(rect)=0 THEN
    RETURN(LAYERTYPES.BAD_ARGUMENT)
  FI

  layer=Find(scene,id)
  IF layer=NULL THEN
    RETURN(LAYERTYPES.BAD_ID)
  FI

  Mark(layer,rect)

RETURN(LAYERTYPES.OK)

; All publication fields are scalar copies; no caller rectangle is borrowed.
BYTE FUNC Claim(LAYERTYPES.Scene POINTER scene LONGCARD id BYTE kind
    LONGCARD POINTER token)

  IF scene.nextToken=0 THEN
    RETURN(LAYERTYPES.EXHAUSTED)
  FI

  scene.activeId=id
  scene.activeKind=kind
  scene.busy=scene.nextToken
  scene.nextToken==+1
  token^=scene.busy

RETURN(LAYERTYPES.OK)

; Stream one damage/visibility intersection at a time into the existing
; bounded work region. The mutation gate makes the retained damage a snapshot.
BYTE FUNC NextPaint(LAYERTYPES.Scene POINTER scene
    LAYERTYPES.Layer POINTER layer)
  BYTE status

  scene.work.count=0
  WHILE scene.nextDamage<layer.damage.count DO
    status=REGIONS.Clip(@layer.visible,
        @layer.damage.rects(scene.nextDamage),@scene.work)
    scene.nextDamage==+1
    IF status<>LAYERTYPES.OK THEN
      RETURN(status)
    FI

    IF scene.work.count<>0 THEN
      RETURN(LAYERTYPES.OK)
    FI
  OD

RETURN(LAYERTYPES.EMPTY)

; Capture only dirty visible pixels. An empty result acquires no transaction.
PUBLIC BYTE FUNC BeginPaint(LAYERTYPES.Scene POINTER scene LONGCARD id
    LONGCARD POINTER token)
  BYTE status
  LAYERTYPES.Layer POINTER layer

  status=Admit(scene)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI

  IF token=NULL THEN
    RETURN(LAYERTYPES.BAD_ARGUMENT)
  FI

  layer=Find(scene,id)
  IF layer=NULL THEN
    RETURN(LAYERTYPES.BAD_ID)
  FI

  IF layer.dirty=0 THEN
    RETURN(LAYERTYPES.EMPTY)
  FI

  scene.nextDamage=0
  status=NextPaint(scene,layer)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI

RETURN(Claim(scene,id,LAYERTYPES.UPDATE_PAINT,token))

; The read-only region is stable until AdvancePaint or Finish, including across
; yields. The owner may submit one bounded portion per worker turn.
PUBLIC LAYERTYPES.Region POINTER FUNC PaintRegion(LAYERTYPES.Scene POINTER scene
    LONGCARD token)

  IF token=0 OR token<>scene.busy OR scene.activeKind<>LAYERTYPES.UPDATE_PAINT THEN
    RETURN(NULL)
  FI

RETURN(@scene.work)

; Acknowledge the current batch and expose the next. EMPTY is required before
; successful Finish, so a caller cannot silently discard a later damage batch.
PUBLIC BYTE FUNC AdvancePaint(LAYERTYPES.Scene POINTER scene LONGCARD token)

  IF scene=NULL THEN
    RETURN(LAYERTYPES.BAD_ARGUMENT)
  FI

  IF token=0 OR token<>scene.busy OR scene.activeKind<>LAYERTYPES.UPDATE_PAINT THEN
    RETURN(LAYERTYPES.BAD_TOKEN)
  FI

RETURN(NextPaint(scene,Find(scene,scene.activeId)))

; Conservative screen-copy fast path. Hidden source pixels are never valid
; screen-copy sources. The renderer additionally checks pixel alignment,
; overlay removal and hardware overlap direction before launch.
PUBLIC BYTE FUNC BeginCopy(LAYERTYPES.Scene POINTER scene LONGCARD id
    LAYERTYPES.Rect POINTER source,target LONGCARD POINTER token)
  BYTE status
  LAYERTYPES.Layer POINTER layer
  LAYERTYPES.Rect savedSource,savedTarget

  status=Admit(scene)
  IF status<>LAYERTYPES.OK THEN
    RETURN(status)
  FI

  IF token=NULL OR REGIONS.Valid(source)=0 OR REGIONS.Valid(target)=0 THEN
    RETURN(LAYERTYPES.BAD_ARGUMENT)
  FI

  layer=Find(scene,id)
  IF layer=NULL THEN
    RETURN(LAYERTYPES.BAD_ID)
  FI

  IF REGIONS.Contains(@layer.bounds,source)=0
      OR REGIONS.Contains(@layer.bounds,target)=0 THEN
    RETURN(LAYERTYPES.BAD_ARGUMENT)
  FI

  IF source.right-source.left<>target.right-target.left
      OR source.bottom-source.top<>target.bottom-target.top THEN
    RETURN(LAYERTYPES.BAD_ARGUMENT)
  FI

  IF REGIONS.Empty(source)<>0 THEN
    RETURN(LAYERTYPES.EMPTY)
  FI

  IF layer.dirty<>0 OR layer.shown=0 OR layer.visible.count<>1 THEN
    RETURN(LAYERTYPES.REDRAW)
  FI

  IF REGIONS.Equal(@layer.visible.rects(0),@layer.bounds)=0 THEN
    RETURN(LAYERTYPES.REDRAW)
  FI

  ; Inputs may refer to the preceding copy's saved descriptors, including a
  ; swapped pair. Snapshot both before publishing either replacement.
  REGIONS.Copy(source,@savedSource)
  REGIONS.Copy(target,@savedTarget)
  status=Claim(scene,id,LAYERTYPES.UPDATE_COPY,token)
  IF status=LAYERTYPES.OK THEN
    REGIONS.Copy(@savedSource,@scene.copySource)
    REGIONS.Copy(@savedTarget,@scene.copyTarget)
  FI

RETURN(status)

; Call only after completed drawing or proven DMA quiescence on failure.
; Covered model pixels are redrawn on later exposure, which marks damage anew.
PUBLIC BYTE FUNC Finish(LAYERTYPES.Scene POINTER scene LONGCARD token
    BYTE completed)
  LAYERTYPES.Layer POINTER layer

  IF scene=NULL THEN
    RETURN(LAYERTYPES.BAD_ARGUMENT)
  FI

  IF token=0 OR token<>scene.busy THEN
    RETURN(LAYERTYPES.BAD_TOKEN)
  FI

  IF completed>1 THEN
    RETURN(LAYERTYPES.BAD_ARGUMENT)
  FI

  layer=Find(scene,scene.activeId)
  IF scene.activeKind=LAYERTYPES.UPDATE_PAINT THEN
    IF completed<>0 THEN
      IF scene.work.count<>0 OR scene.nextDamage<layer.damage.count THEN
        RETURN(LAYERTYPES.BUSY)
      FI

      layer.dirty=0
      layer.damage.count=0
    FI
  ELSEIF completed=0 THEN
    Mark(layer,@layer.bounds)
  FI

  scene.busy=0
  scene.activeKind=0
  scene.activeId=0

RETURN(LAYERTYPES.OK)
