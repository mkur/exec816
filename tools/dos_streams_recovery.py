"""Reuse real 128/256-byte serial fault oracles while a DOS RAW endpoint is open."""
import json,shutil
from pathlib import Path
import test_sio_recovery as recovery
from native_program import ROOT,build,require,sha256
from test_dos_stack import execute,ownership


def run(t,out,mode,size):
    out.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'tests/programs/sio_recovery.act').read_text()
    source=source.replace('USE EXEC\n','USE EXEC\nUSE DOS\n')
    source=source.replace('PROC Main()','DOS.FileHandle POINTER stream\nPROC Main()')
    source=source.replace('  Rollback()\n  Setup()', '  stream=DOS.Open(BYTE POINTER($d1000),DOS.MODE_OLDFILE) Require(stream<>DOS.FileHandle POINTER(0))\n  Require(DOS.Write(stream,BYTE POINTER($d1020),4)=4)\n  Rollback() Setup()')
    source=source.replace('  okay=SIODRIVER.Start()\n  Require(okay=1)\n  SIODRIVER.Stop()', '  okay=SIODRIVER.Start() Require(okay=1) SIODRIVER.Stop()\n  Require(DOS.Close(stream)<>0 AND DOS.ReleaseContext()<>0)')
    source=source.replace('"tasks_exec_helpers.inc"','"'+str(ROOT/'tests/programs/tasks_exec_helpers.inc')+'"')
    source=source.replace('"io-names.inc"','"'+str(ROOT/'tests/programs/io-names.inc')+'"')
    shutil.copyfile(ROOT/'tests/programs/sioprobe.act',out/'sioprobe.act')
    path=out/'stream-recovery.act';path.write_text(source)
    original_build,original_execute,original_clean=recovery.build,recovery.execute,recovery.clean_ownership
    names=bytearray(36);names[:5]=b'RAW:\0';names[32:]=b'SIO\n'
    def configured(toolchain,ignored_source,destination,**kwargs):
        return build(toolchain,path,destination,**kwargs,console=True,task_capacity=8,image_data=[(0xd1000,bytes(names))])
    def checked(b,p,**kwargs):
        runtime,state=execute(b,p,**kwargs)
        cs=p['build']['memory']['console_storage'];ds=p['build']['memory']['dos_storage']
        def far(at,n):return bytes(b.eval_expr(f'db(${at+i:x})') for i in range(n))
        registry=far(ds['STREAMS'],16);endpoint=int.from_bytes(registry[1:4],'little')
        instance=far(cs['INSTANCE'],62)
        if runtime['status']==0xff93:
            require(registry[0]==2 and endpoint and instance[21]==1,'Unsafe SIO reclaimed live RAW endpoint')
            require(int.from_bytes(instance[:3],'little')!=0,'Unsafe SIO reclaimed console cells')
        else:require(registry[0]==0 and not endpoint and instance[:3]==bytes(3),'Safe cleanup retained RAW state')
        runtime['streams_cleanup']=dict(registry=registry.hex(),console_instance=instance.hex(),unsafe_retained=runtime['status']==0xff93)
        return runtime,state
    recovery.build=configured;recovery.execute=checked;recovery.clean_ownership=ownership
    try:r=recovery.run(t,out,mode=='opt',['checksum','device','short','firstcause','framing','protocol'],sector_size=size)
    finally:recovery.build,recovery.execute,recovery.clean_ownership=original_build,original_execute,original_clean
    r['stream_fixture_sha256']=sha256(path)
    return r
