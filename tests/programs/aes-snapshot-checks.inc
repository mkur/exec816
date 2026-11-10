CONST OBSERVATION_BYTES=320, MAX_OBSERVATIONS=32
BYTE ARRAY observations(OBSERVATION_BYTES*MAX_OBSERVATIONS)
CARD observationCount

PROC Observe()
  CARD i

  Require(observationCount<MAX_OBSERVATIONS)
  LET view=service.windows(0).view
  Require(view.visibleCount<=16)
  LET target=CARD POINTER(@observations(observationCount*OBSERVATION_BYTES))
  A816MEMORY.Clear(BYTE POINTER(target),OBSERVATION_BYTES)
  target(0)=view.visibleCount
  target(1)=desktop.windows(0).iconified
  target(2)=desktop.windows(0).frameKind
  target(3)=view.shown
  A816MEMORY.Move(BYTE POINTER(@target(4)),BYTE POINTER(@view.bounds),16)
  A816MEMORY.Move(BYTE POINTER(@target(12)),BYTE POINTER(@view.visible(0)),
      SIZE(view.visibleCount*8))
  FOR i=0 TO 6 DO
    BEGIN
      LET layer=LAYERS.Find(@desktop.scene,handles(i))
      A816MEMORY.Move(BYTE POINTER(@target(76+i*4)),BYTE POINTER(@layer.bounds),8)
      target(104+i)=layer.shown
      target(111+i)=desktop.scene.order(i)
    END
  OD
  A816MEMORY.Move(BYTE POINTER(@target(118)),
      BYTE POINTER(@desktop.windows(0).normalBounds),8)
  A816MEMORY.Move(BYTE POINTER(@target(122)),BYTE POINTER(@view.revision),4)
  A816MEMORY.Move(BYTE POINTER(@target(124)),BYTE POINTER(@view.paintEpoch),4)
  target(126)=view.pixelsReady
  target(127)=view.updates
  target(128)=desktop.scene.count
  target(129)=view.changed
  observationCount==+1

RETURN

PROC Snapshot()

  AESWINDOWSTATE.SnapshotAll(@service.clients(0))
  Observe()

RETURN

PROC FreshnessChecks()

  LET client=@service.clients(0)
  LET item=@service.windows(0)
  LET view=item.view
  LET window=item.window
  Snapshot()
  FOR iteration=0 TO 1 DO
    AESWINDOWSTATE.BeginUpdate(client)
    AESWINDOWSTATE.Updates(client,1)
    Observe()
    AESWINDOWSTATE.EndUpdate(client)
    AESWINDOWSTATE.Updates(client,0)
  OD
  Require(LAYERS.Bounds(@desktop.scene,handles(4),80,64,16,64)=LAYERTYPES.OK)
  Snapshot()
  Require(LAYERS.Show(@desktop.scene,handles(4),0)=LAYERTYPES.OK)
  Snapshot()
  Require(LAYERS.Show(@desktop.scene,handles(4),1)=LAYERTYPES.OK)
  Require(LAYERS.Order(@desktop.scene,handles(0),1)=LAYERTYPES.OK)
  Snapshot()
  Require(LAYERS.Bounds(@desktop.scene,handles(0),48,40,220,150)=LAYERTYPES.OK)
  Snapshot()
  Require(LAYERS.Bounds(@desktop.scene,handles(4),48,40,220,150)=LAYERTYPES.OK)
  Require(LAYERS.Order(@desktop.scene,handles(4),1)=LAYERTYPES.OK)
  Snapshot()
  Require(LAYERS.Show(@desktop.scene,handles(4),0)=LAYERTYPES.OK)
  Snapshot()
  Require(LAYERS.Show(@desktop.scene,handles(0),0)=LAYERTYPES.OK)
  Snapshot()
  Require(LAYERS.Bounds(@desktop.scene,handles(0),64,48,200,120)=LAYERTYPES.OK)
  Snapshot()
  LET layer=LAYERS.Find(@desktop.scene,handles(0))
  LET content=layer.contentRevision
  AESWINDOWSTATE.BeginUpdate(client)
  Require(layer.contentRevision=content+1)
  Observe()
  AESWINDOWSTATE.EndUpdate(client)
  Require(layer.pending.count<>0 AND view.pixelsReady=0)
  window.iconified=1
  REGIONS.Assign(@window.normalBounds,40,32,240,180)
  Snapshot()
  REGIONS.Assign(@window.normalBounds,48,36,260,190)
  Snapshot()
  window.iconified=0
  Require(LAYERS.Bounds(@desktop.scene,handles(0),48,36,212,154)=LAYERTYPES.OK)
  Require(LAYERS.Show(@desktop.scene,handles(0),1)=LAYERTYPES.OK)
  Snapshot()
  window.frameKind=AESTYPES.WINDOW_KIND OR DESKTYPES.FRAME_INFO
  Snapshot()
  window.frameKind=DESKTYPES.FRAME_BORDERLESS
  Snapshot()

  ; Geometry stays fixed while paint identity/completeness changes.
  layer.dirty=0
  layer.damage.count=0
  FOR index=0 TO 2 DO
    AESWINDOWSTATE.BeginUpdate(client)
    view.changed=AESTYPES.CHANGE_DECLARED
    request.paintCount=1
    request.paints(0).handle=view.handle
    request.paints(0).epoch=view.paintEpoch
    REGIONS.Copy(LAYERTYPES.Rect POINTER(@view.work),
        LAYERTYPES.Rect POINTER(@request.paints(0).rect))
    IF index=0 THEN
      request.paints(0).epoch==+1
    ELSEIF index=1 THEN
      request.paintFailed=1
    ELSE
      request.paints(0).rect.right=request.paints(0).rect.left+8
    FI
    AESWINDOWSTATE.EndUpdate(client)
    Require(layer.pending.count<>0 AND view.pixelsReady=0)
    Observe()
  OD
  AESWINDOWSTATE.BeginUpdate(client)
  view.changed=AESTYPES.CHANGE_DECLARED
  request.paintCount=1
  request.paints(0).handle=view.handle
  request.paints(0).epoch=view.paintEpoch
  REGIONS.Copy(LAYERTYPES.Rect POINTER(@view.work),
      LAYERTYPES.Rect POINTER(@request.paints(0).rect))
  AESWINDOWSTATE.EndUpdate(client)
  ; Old obligations outside the current work area may remain outstanding.
  Require(view.pixelsReady<>0)
  Observe()
  AESSTATE.Bind(service)
  Snapshot()

RETURN
