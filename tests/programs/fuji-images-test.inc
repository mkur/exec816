; All state changes go through the actual loaded command and serial worker.
PROC Images()

  Peer(0)
  LET writes=snapshot(2)
  Require(SIOCLIENT.Open($32,0,BYTE POINTER(@session))=0)
  Run(c"ATTACH D2: HOST 1 IMAGE /tools.atr",c"RAM:RAWBUSY",10,
      EXEC.IOERR_UNITBUSY)
  Run(c"EJECT D2:",c"RAM:RAWBUSY",10,EXEC.IOERR_UNITBUSY)
  SIOCLIENT.Close(BYTE POINTER(@session))
  Run(c"EJECT D1:",c"RAM:SYSBUSY",10,EXEC.IOERR_UNITBUSY)
  Peer(0)
  Require(snapshot(2)=writes AND snapshot(3)=0 AND snapshot(4)=0)
  Run(c"ATTACH D2: HOST 8 IMAGE /tools.atr",c"RAM:NOHOST",10,
      DOS.ERROR_OBJECT_NOT_FOUND)
  Peer(9)
  Run(c"ATTACH D2: HOST 1 IMAGE /tools.atr",c"RAM:HOSTERR",10,
      SIO.SIOERR_DEVICE)
  Peer(4)
  Run(c"ATTACH D2: HOST 1 IMAGE /tools.atr",c"RAM:PATHERR",10,
      SIO.SIOERR_DEVICE)
  Peer(0)
  Require(snapshot(2)=writes AND snapshot(3)=0)
  Run(c"ATTACH D2: HOST 1 IMAGE \"/disks/My tools.atr\"",c"RAM:ATTACH",0,0)
  Peer(0)
  Require(snapshot(2)=writes+1 AND snapshot(3)=1 AND snapshot(5)=$41)
  Run(c"DISKS D2:",c"RAM:PATH",0,0)
  TextResult(c"RAM:PATH",c"D2: host 1 RO attached\n  /disks/My tools.atr\nPath /disks/My tools.atr\n")
  Run(c"ATTACH D2: HOST 1 IMAGE /other.atr",c"RAM:REPEAT",10,
      DOS.ERROR_OBJECT_IN_USE)
  Peer(0)
  Require(snapshot(2)=writes+1 AND snapshot(3)=1)
  Run(c"EJECT D2:",c"RAM:EJECT",0,0)
  Peer(5)
  Run(c"ATTACH D2: HOST 1 IMAGE /broken.atr",c"RAM:BADIMAGE",10,
      SIO.SIOERR_DEVICE)
  Peer(0)
  Require(snapshot(2)=writes+2 AND snapshot(3)=1 AND snapshot(5)=1)
  Run(c"DISKS D2:",c"RAM:PATH",0,0)
  TextResult(c"RAM:PATH",c"D2: host 1 RO configured\n  /broken.atr\nPath /broken.atr\n")
  Run(c"ATTACH D2: HOST 2 IMAGE /other.atr",c"RAM:REPEAT",10,
      DOS.ERROR_OBJECT_IN_USE)
  Run(c"EJECT D2:",c"RAM:EJECT",0,0)
  Peer(10)
  interrupted=1
  Run(c"ATTACH D2: HOST 1 IMAGE /early.atr",c"RAM:EARLY",10,DOS.ERROR_BREAK)
  Peer(0)
  Require(snapshot(2)=writes+2 AND snapshot(3)=1)
  Peer(6)
  interrupted=1
  contested=1
  Run(c"ATTACH D2: HOST 2 IMAGE /late.atr READWRITE",c"RAM:LATE",0,0)
  Peer(0)
  Require(snapshot(2)=writes+3 AND snapshot(3)=2 AND
      snapshot(5)=$42 AND snapshot(7)=1)
  Run(c"EJECT D2:",c"RAM:EJECT",0,0)
  Peer(7)
  interrupted=1
  Run(c"ATTACH D2: HOST 1 IMAGE /late.atr",c"RAM:LATE",0,0)
  Peer(8)
  interrupted=1
  Run(c"EJECT D2:",c"RAM:LATE",0,0)
  Peer(0)
  Require(snapshot(3)=3 AND snapshot(4)=4 AND snapshot(5)=0)
  Run(c"ATTACH D9: HOST 1 IMAGE /bad.atr",c"RAM:BADDRIVE",10,
      DOS.ERROR_BAD_ARGUMENTS)
  Run(c"ATTACH D2: HOST 1",c"RAM:NOIMAGE",10,DOS.ERROR_BAD_ARGUMENTS)
  Run(c"EJECT D2: READWRITE",c"RAM:BADOPT",10,DOS.ERROR_BAD_ARGUMENTS)

RETURN
