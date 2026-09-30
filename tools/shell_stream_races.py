"""Existing RAW race hooks extended with live, independent current directories."""
import shutil
from pathlib import Path
import test_dos_streams_lifetime as life
from native_program import ROOT,build,require,sha256
from test_shell_lifetime import PIN
from os_boundary import emulator

def run(t,out,mode,bank=1,scenario=0):
    out.mkdir(parents=True,exist_ok=True)
    s=(ROOT/'tests/programs/dos_streams_lifetime.act').read_text()
    s=s.replace('CARD checks,childChecks','DOS.FileLock POINTER rootDirectory,peerDirectory\nBYTE directories\nBYTE ARRAY rootPath=[68 49 58 0]\nCARD checks,childChecks')
    s=s.replace('spare=EXEC.AllocMem(80,EXEC.MEMF_UPPER)','spare=EXEC.AllocMem(88,EXEC.MEMF_UPPER)').replace('EXEC.FreeMem(spare,80)','EXEC.FreeMem(spare,88)')
    s=s.replace('  DOSCORE.DosSlot POINTER owner\n  BYTE action', '  DOSCORE.DosSlot POINTER owner\n  DOS.FileLock POINTER previous\n  BYTE action')
    s=s.replace('      peerResult=LONGINT(ADDRESS(other))', '''      IF directories<>0 AND other<>DOS.FileHandle POINTER(0) THEN
        peerDirectory=DOS.Lock(rootPath,DOS.SHARED_LOCK) PeerCheck(peerDirectory<>DOS.FileLock POINTER(0))
        previous=DOS.CurrentDir(peerDirectory) PeerCheck(previous=DOS.FileLock POINTER(0) AND DOS.IoErr()=0)
      FI
      peerResult=LONGINT(ADDRESS(other))''')
    s=s.replace('    ELSEIF action=2 THEN\n      peerResult=DOS.Close(other)', '''    ELSEIF action=2 THEN
      peerResult=DOS.Close(other)
      IF peerDirectory<>DOS.FileLock POINTER(0) THEN
        previous=DOS.CurrentDir(DOS.FileLock POINTER(0)) PeerCheck(previous=peerDirectory)
        DOS.UnLock(previous) PeerCheck(DOS.IoErr()=0) peerDirectory=DOS.FileLock POINTER(0)
      FI''')
    a=s.index('PROC DeliveryRaces(');b=s.index('\nPROC OpenerExit(',a);body=s[a:b]
    body=body.replace('  CARD tag', '  CARD tag\n  DOS.FileLock POINTER previous')
    body=body.replace('  Spawn(0)\n  handle=', '''  directories=BYTE(mode<>3)
  Spawn(0)
  IF directories<>0 THEN
    rootDirectory=DOS.Lock(rootPath,DOS.SHARED_LOCK) Check(rootDirectory<>DOS.FileLock POINTER(0))
    previous=DOS.CurrentDir(rootDirectory) Check(previous=DOS.FileLock POINTER(0) AND DOS.IoErr()=0)
  FI
  handle=''')
    body=body.replace('  Arm(5)\n  Send(3)', '''  IF directories<>0 THEN
    Check(peer.directory=BYTE POINTER(peerDirectory) AND client.directory=BYTE POINTER(rootDirectory))
    Check(DOS.CurrentDir(peerDirectory)=DOS.FileLock POINTER(0) AND DOS.IoErr()=DOS.ERROR_INVALID_LOCK)
    Check(client.directory=BYTE POINTER(rootDirectory))
  FI
  Arm(5) Send(3)''')
    body=body.replace('  Check(DOS.Close(handle)<>0 AND DOS.ReleaseContext()<>0\n        AND EXEC.AvailMem(0)=baseline)', '''  IF directories<>0 THEN
    previous=DOS.CurrentDir(DOS.FileLock POINTER(0)) Check(previous=rootDirectory)
    DOS.UnLock(previous) Check(DOS.IoErr()=0 AND FSBOOT.Stop()<>0) rootDirectory=DOS.FileLock POINTER(0)
  FI
  directories=0
  Check(DOS.Close(handle)<>0 AND DOS.ReleaseContext()<>0 AND EXEC.AvailMem(0)=baseline)''')
    s=s[:a]+body+s[b:]
    a=s.index('PROC Mixed(');b=s.index('\nPROC Main(',a);body=s[a:b]
    body=body.replace('  BYTE index', '  BYTE index\n  DOS.FileLock POINTER previous')
    body=body.replace('  client=DOSCLIENT.Ensure()', '''  rootDirectory=DOS.Lock(rootPath,DOS.SHARED_LOCK) Check(rootDirectory<>DOS.FileLock POINTER(0))
  previous=DOS.CurrentDir(rootDirectory) Check(previous=DOS.FileLock POINTER(0) AND DOS.IoErr()=0)
  client=DOSCLIENT.Ensure()''')
    body=body.replace('  Check(DOS.Close(file)<>0', '''  previous=DOS.CurrentDir(DOS.FileLock POINTER(0)) Check(previous=rootDirectory)
  DOS.UnLock(previous) Check(DOS.IoErr()=0) rootDirectory=DOS.FileLock POINTER(0)
  Check(DOS.Close(file)<>0''')
    s=s[:a]+body+s[b:]
    path=out/'shell-stream-races.act';path.write_text(s);shutil.copyfile(ROOT/'tests/programs/dstreamprobe.act',out/'dstreamprobe.act')
    old_build,old_emulator,old_pin=life.build,life.emulator,life.PIN
    def configured(toolchain,ignored,destination,**kwargs):return build(toolchain,path,destination,**kwargs)
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned paced bridge')
    life.build=configured;life.emulator=lambda ignored,*args,**kwargs:emulator(ROOT/'build/shell-paced-bridge',*args,**kwargs);life.PIN=PIN
    try:r=life.run(t,out,mode,bank,scenario)
    finally:life.build,life.emulator,life.PIN=old_build,old_emulator,old_pin
    r.update(pin=PIN,fixture_sha256=sha256(path),scope='Two current directories through queued/collected RAW replies; root/peer foreign-selection refusal, stale-signal filesystem reads, real port-allocation exhaustion and existing stream lifecycle hooks.',
        source_inputs={s:sha256(ROOT/s)for s in ('tests/programs/dos_streams_lifetime.act','tests/programs/dstreamprobe.act','tools/test_dos_streams_lifetime.py','tools/shell_stream_races.py')})
    return r
