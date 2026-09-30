"""Derive fault-only variants of the same simultaneous-client workload."""
from pathlib import Path
from os_boundary import require


def source(original, output, variant):
    text=original.read_text()
    def replace(old,new):
        nonlocal text
        require(text.count(old)==1,'Stale concurrency fault transform: '+old)
        text=text.replace(old,new)
    if variant=='queued':
        replace('EXEC.SendIO(EXEC.IORequest POINTER(state.second))',
                'EXEC.SendIO(EXEC.IORequest POINTER(state.second))\n  EXEC.AbortIO(EXEC.IORequest POINTER(state.second))')
        replace('error=EXEC.WaitIO(EXEC.IORequest POINTER(state.second))\n  Require(error=0)',
                'error=EXEC.WaitIO(EXEC.IORequest POINTER(state.second)) Require(error=EXEC.IOERR_ABORTED)')
        replace('Require(state.first.io_Actual=LONGCARD(sectorSize)\n      AND state.second.io_Actual=LONGCARD(sectorSize))',
                'Require(state.first.io_Actual=LONGCARD(sectorSize) AND state.second.io_Actual=0)')
        replace('    Require(state.buffer(index+sectorSize)=state.buffer(index))','')
    elif variant=='timeout':
        replace('  INT error\n\n  state=Client(slot)', '  INT error\n  LONGCARD device\n  state=Client(slot)')
        replace('  error=EXEC.OpenDevice(sioName,LONGCARD(49+(slot & 1)),\n      EXEC.IORequest POINTER(state.first),0)\n  Require(error=0)',
                '  device=LONGCARD(49+(slot & 1))\n  IF slot=0 THEN device=56 FI\n  error=EXEC.OpenDevice(sioName,device,EXEC.IORequest POINTER(state.first),0) Require(error=0)')
        replace('  error=EXEC.OpenDevice(sioName,LONGCARD(49+(slot & 1)),\n      EXEC.IORequest POINTER(state.second),0)\n  Require(error=0)',
                '  error=EXEC.OpenDevice(sioName,device,EXEC.IORequest POINTER(state.second),0) Require(error=0)')
        replace('  req.sio_TimeoutUS=0','  req.sio_TimeoutUS=20205')
        for lane in ('first','second'):
            replace(f'error=EXEC.WaitIO(EXEC.IORequest POINTER(state.{lane}))\n  Require(error=0)',
                    f'error=EXEC.WaitIO(EXEC.IORequest POINTER(state.{lane})) Require(error=0 OR error=1 OR error=8)')
        replace('  Verify(slot,round)',
                '  IF state.first.io_Error=0 AND state.second.io_Error=0 THEN Verify(slot,round) FI\n'
                '  IF state.first.io_Error=1 THEN timeoutReplies==+1 FI\n'
                '  IF state.second.io_Error=1 THEN timeoutReplies==+1 FI\n'
                '  IF state.first.io_Error=8 THEN offlineReplies==+1 FI\n'
                '  IF state.second.io_Error=8 THEN offlineReplies==+1 FI\n'
                '  Poison(state)')
        replace('CARD checks,submitted,', 'CARD timeoutReplies,offlineReplies\nCARD checks,submitted,')
        replace('PROC ClientClose(BYTE slot)',
                'PROC Poison(ClientState POINTER state)\n'
                '  CARD i,status\n'
                '  FOR i=0 TO 255 DO state.buffer(i)=$a5 OD\n'
                '  status=EXECTASKS.Sleep(1)\n'
                '  FOR i=0 TO 255 DO Require(state.buffer(i)=$a5) OD\n'
                'RETURN\n\nPROC ClientClose(BYTE slot)')
        replace('  Require(submitted=collected AND outstanding=0 AND activeWork<>0\n      AND peakOutstanding>=4)',
                '  Require(submitted=collected AND outstanding=0 AND peakOutstanding>=4 AND timeoutReplies=1 AND offlineReplies<>0)')
    else:raise ValueError(variant)
    output.mkdir(parents=True,exist_ok=True)
    (output/'io-names.inc').write_bytes((original.parent/'io-names.inc').read_bytes())
    path=output/'sio_concurrent.act';path.write_text(text)
    return path
