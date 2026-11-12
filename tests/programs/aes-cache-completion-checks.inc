; Run after freshness checks, with the same live owner and layer records.
CONST COMPLETION_CASES=15, COMPLETION_BYTES=50
BYTE ARRAY completionStates(COMPLETION_CASES*COMPLETION_BYTES)
BYTE completionCase,completionIteration,completionComplete
LAYERTYPES.Rect completionChanged
BYTE POINTER completionBefore

PROC SameDesktop(BYTE POINTER original)
  CARD offset
  BYTE equal

  LET current=BYTE POINTER(desktop)
  equal=1
  FOR offset=0 TO CARD(SIZEOF(DESKTYPES.Service))-1 DO
    IF current(offset)<>original(offset) THEN
      equal=0
    FI
  OD
  Require(equal<>0)

RETURN

PROC CompletionSample(BYTE complete)

  DESKCACHE.EndChange(desktop,@desktop.windows(0),
      @completionChanged,complete)

RETURN

PROC CompletionSetup(BYTE kind)
  BYTE slot

  LET window=@desktop.windows(0)
  LET layer=LAYERS.Find(@desktop.scene,window.layer)
  ; Retire any simulated DMA before replacing storage, including pinned cases.
  FOR slot=0 TO 1 DO
    LAYERCACHE.Released(@desktop.cache.slots(slot),1)
  OD
  A816MEMORY.Clear(BYTE POINTER(@desktop.cache),LAYERTYPES.CACHEPAIR_SIZE)
  A816MEMORY.Clear(BYTE POINTER(@desktop.repairs(0)),
      2*LAYERTYPES.CACHEREPAIR_SIZE)
  window.visualRevision=10
  completionComplete=1
  REGIONS.Assign(@completionChanged,layer.bounds.left+3,layer.bounds.top+5,
      layer.bounds.left+11,layer.bounds.top+13)
  Require(LAYERS.Painted(@desktop.scene,layer.id,layer.paintEpoch,
      @layer.bounds)<>0)
  FOR slot=0 TO 1 DO
    IF kind<>0 AND (kind<=3 OR kind=6
        OR (kind=5 AND slot=1)
        OR (kind>=4 AND kind<>5 AND slot=0)) THEN
      BEGIN
        LET identity=IF kind<=3 THEN LONGCARD(99)+LONGCARD(slot)
            ELSE window.id FI
        LAYERCACHE.Prepare(@desktop.cache.slots(slot),identity,10,212,154)
        IF kind<>3 AND kind<>10 THEN
          LAYERCACHE.Captured(@desktop.cache.slots(slot),kind<>2)
        FI
      END
    FI
  OD
  IF (kind>=4 AND kind<=8) OR kind>=11 THEN
    DESKCACHE.BeginChange(desktop,window)
  FI
  IF kind=7 THEN
    REGIONS.Assign(@completionChanged,0,0,0,0)
  ELSEIF kind=8 THEN
    ; A ready repair is left alone by a second END without a new BEGIN.
    CompletionSample(completionComplete)
  ELSEIF kind=11 THEN
    ; A discarded base cannot be revived by completing its outstanding hold.
    LAYERCACHE.Discard(@desktop.cache.slots(0))
  ELSEIF kind=12 THEN
    ; Completion flag alone is insufficient while client pixels are missing.
    LAYERS.RequirePaint(@desktop.scene,layer.id,@completionChanged)
  ELSEIF kind=13 THEN
    completionComplete=0
  ELSEIF kind=14 THEN
    ; A queued repair absorbs a second update and expands its local bounds.
    CompletionSample(completionComplete)
    DESKCACHE.BeginChange(desktop,window)
    REGIONS.Assign(@completionChanged,layer.bounds.left+21,layer.bounds.top+7,
        layer.bounds.left+29,layer.bounds.top+17)
  FI

RETURN

PROC CompletionChecks()
  BYTE slot

  completionBefore=EXEC.AllocMem(LONGCARD(SIZEOF(DESKTYPES.Service)),
      EXEC.MEMF_UPPER)
  Require(completionBefore<>NULL)
  FOR completionCase=0 TO COMPLETION_CASES-1 DO
    FOR completionIteration=0 TO 9 DO
      BEGIN
        CompletionSetup(completionCase)
        LET discarded=LAYERCACHE.discards
        A816MEMORY.Move(completionBefore,BYTE POINTER(desktop),
            SIZEOF(DESKTYPES.Service))
        CompletionSample(completionComplete)
        IF completionCase<=3 OR (completionCase>=8 AND completionCase<=10) THEN
          SameDesktop(completionBefore)
          Require(LAYERCACHE.discards=discarded)
        FI
        FOR slot=0 TO 1 DO
          IF desktop.cache.slots(slot).identity=desktop.windows(0).id THEN
            BEGIN
              LET base=@desktop.cache.slots(slot)
              LET repair=@desktop.repairs(slot)
              IF completionCase=7 THEN
                Require(base.valid<>0 AND repair.state=0)
              ELSEIF completionCase>=11 AND completionCase<=13 THEN
                Require(base.valid=0 AND base.revision=0 AND repair.state=0)
              ELSEIF completionCase=9 THEN
                Require(base.valid<>0 AND repair.state=0)
              ELSEIF completionCase=10 THEN
                Require(base.pinned<>0 AND repair.state=0)
              ELSE
                Require(base.valid=0 AND repair.state=LAYERTYPES.CACHE_CHANGE_READY)
                Require(repair.bounds.left=2 AND repair.bounds.top=5)
                Require(repair.bounds.right=IF completionCase=14 THEN INT(30)
                    ELSE INT(12) FI)
                Require(repair.bounds.bottom=IF completionCase=14 THEN INT(17)
                    ELSE INT(13) FI)
              FI
            END
          FI
        OD
        LET target=@completionStates(CARD(completionCase)*COMPLETION_BYTES)
        A816MEMORY.Move(target,BYTE POINTER(@desktop.cache),
            LAYERTYPES.CACHEPAIR_SIZE)
        A816MEMORY.Move(@target(30),
            BYTE POINTER(@desktop.repairs(0)),2*LAYERTYPES.CACHEREPAIR_SIZE)
      END
    OD
  OD
  FOR slot=0 TO 1 DO
    LAYERCACHE.Released(@desktop.cache.slots(slot),1)
  OD
  A816MEMORY.Clear(BYTE POINTER(@desktop.cache),LAYERTYPES.CACHEPAIR_SIZE)
  A816MEMORY.Clear(BYTE POINTER(@desktop.repairs(0)),
      2*LAYERTYPES.CACHEREPAIR_SIZE)

  ; A hidden/iconified owner still completes the ordinary no-slot END policy.
  LET item=service.windows(0)
  LET layer=LAYERS.Find(@desktop.scene,item.layer)
  Require(LAYERS.Show(@desktop.scene,layer.id,0)=LAYERTYPES.OK)
  item.iconified=1
  REGIONS.Copy(@layer.bounds,@item.normalBounds)
  service.updateWindow=item.gui.window
  AESWINDOWSTATE.BeginUpdate(@service.clients(0))
  AESWINDOWSTATE.Updates(@service.clients(0),2)
  Require(item.view.updates=2)
  item.view.changed=AESTYPES.CHANGE_UNDECLARED OR AESTYPES.CHANGE_RECT
  REGIONS.Copy(@completionChanged,LAYERTYPES.Rect POINTER(@item.view.change))
  AESWINDOWSTATE.EndUpdate(@service.clients(0))
  AESWINDOWSTATE.Updates(@service.clients(0),0)
  Require(item.view.changed=0 AND item.view.updates=0)
  Require(layer.pending.count<>0 AND item.view.pixelsReady=0)
  Require(item.view.paintEpoch=layer.paintEpoch)
  Require(request.paintCount=0 AND request.invalidationCount=0)
  item.iconified=0

  ; Successful reports still publish readiness and schedule capture on a miss.
  ; This metadata-only fixture has no renderer to retire hide's frame damage.
  layer.dirty=0
  layer.damage.count=0
  DESKCACHE.ResetCandidates(desktop)
  AESWINDOWSTATE.BeginUpdate(@service.clients(0))
  item.view.changed=AESTYPES.CHANGE_DECLARED
  request.paintCount=1
  request.paints(0).handle=item.view.handle
  request.paints(0).epoch=item.view.paintEpoch
  REGIONS.Copy(LAYERTYPES.Rect POINTER(@item.view.work),
      LAYERTYPES.Rect POINTER(@request.paints(0).rect))
  AESWINDOWSTATE.EndUpdate(@service.clients(0))
  Require(item.view.pixelsReady<>0 AND item.view.paintEpoch=layer.paintEpoch)
  Require(DESKCACHE.TakeCandidate(0)<>0)
  Require(request.paintCount=0 AND item.view.changed=0)
  service.updateWindow=0

  ; Normal retirement invalidates both identities before the layer is deleted.
  LAYERCACHE.Prepare(@desktop.cache.slots(0),item.id,10,212,154)
  LAYERCACHE.Captured(@desktop.cache.slots(0),1)
  DESKCACHE.Invalidate(desktop,item.id)
  Require(desktop.cache.slots(0).revision=0 AND desktop.repairs(0).state=0)
  EXEC.FreeMem(completionBefore,LONGCARD(SIZEOF(DESKTYPES.Service)))

RETURN
