PROC ZeroEpochSamples()

  AESWINDOWSTATE.SnapshotAll(@service.clients(0))
  AESWINDOWSTATE.SnapshotAll(@service.clients(0))

RETURN

PROC EpochChecks()
  BYTE i

  LET epoch=desktop.scene.layoutEpoch
  LET rebuilds=desktop.scene.rebuilds
  SNAPSHOTFAULTS.fail=1
  Require(LAYERS.Show(@desktop.scene,handles(4),1)=LAYERTYPES.FULL)
  Require(desktop.scene.layoutEpoch<>epoch)
  Require(desktop.scene.rebuilds=rebuilds)
  FOR i=0 TO LAYERTYPES.SLOT_COUNT-1 DO
    Require(desktop.scene.items(i).visible.count=0)
  OD
  SNAPSHOTFAULTS.fail=0
  Require(LAYERS.Show(@desktop.scene,handles(4),0)=LAYERTYPES.OK)
  AESWINDOWSTATE.SnapshotAll(@service.clients(0))
  Require(service.windows(0).geometryEpoch=desktop.scene.layoutEpoch)

  desktop.scene.layoutEpoch=$fffffffe
  Require(LAYERS.Show(@desktop.scene,handles(4),1)=LAYERTYPES.OK)
  Require(desktop.scene.layoutEpoch=$ffffffff)
  AESWINDOWSTATE.SnapshotAll(@service.clients(0))
  Require(service.windows(0).geometryEpoch=$ffffffff)
  Require(LAYERS.Show(@desktop.scene,handles(4),0)=LAYERTYPES.OK)
  Require(desktop.scene.layoutEpoch=0)
  ZeroEpochSamples()
  Require(service.windows(0).geometryEpoch=0)
  Require(LAYERS.Order(@desktop.scene,handles(0),0)=LAYERTYPES.OK)
  Require(desktop.scene.layoutEpoch=0)

  service.windows(0).geometryEpoch=$ffffffff
  AESSTATE.Bind(service)
  Require(service.windows(0).geometryEpoch=0)
  AESSTATE.Bind(NULL)
  Require(LAYERS.Init(@desktop.scene,640,240)=LAYERTYPES.OK)
  Require(desktop.scene.layoutEpoch<>0)
  FOR i=0 TO 6 DO
    BEGIN
      LAYERTYPES.Rect bounds
      REGIONS.Assign(@bounds,40+INT(i)*24,32,240+INT(i)*24,180)
      Require(LAYERS.Create(@desktop.scene,@bounds,@handles(i))=LAYERTYPES.OK)
      IF i<4 THEN
        Require(LAYERS.SetExternal(@desktop.scene,handles(i))=LAYERTYPES.OK)
        desktop.windows(i).layer=handles(i)
      FI
    END
  OD
  AESSTATE.Bind(service)
  AESWINDOWSTATE.SnapshotAll(@service.clients(0))
  Require(service.windows(0).geometryEpoch=desktop.scene.layoutEpoch)

RETURN
