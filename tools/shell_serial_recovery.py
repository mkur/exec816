"""Real serial faults with a selected MyDOS directory and retained resident shell."""
import json,shutil
from pathlib import Path
import test_sio_recovery as recovery
from native_program import ROOT,build,require,sha256
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(t,out,mode,size):
    out.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'tests/programs/sio_recovery.act').read_text()
    source=source.replace('USE EXEC\n','USE EXEC\nUSE DOS\nUSE FSBOOT\nUSE DOSCORE\nUSE DOSCLIENT\n')
    source=source.replace('EXEC.MsgPort POINTER port','INCLUDE "'+str(ROOT/'examples/shell/shell-session.inc')+'"\nINCLUDE "sio-storage-action.inc"\nEXEC.MsgPort POINTER port')
    # Keep private recovery helpers out of the fixed application-entry table.
    import re
    for name in re.findall(r'(?m)^PROC (\w+)\(\)',source):
        if name in ('Main','BlockerEntry'):continue
        source=source.replace('PROC '+name+'()', 'PROC '+name+'(BYTE unused)').replace(name+'()',name+'(0)')
    source=source.replace('PROC Main()', 'BYTE shellCheckpoint\nCARD postsBaseline\nBYTE directoryChecked,directoryReleased\nBYTE ARRAY recoveryRoot=[68 50 58 0]\nPROC Main()')
    source=source.replace('  Rollback(0) Setup(0)', '  Require(ShellStart(recoveryRoot)<>0 AND shell.directory<>DOS.FileLock POINTER(0))\n  postsBaseline=CARD POINTER(SD_POSTS)^\n  Rollback(0) Setup(0)')
    source=source.replace('  Submit(0) Collect(0) Cleanup(0)', '  Submit(0) Collect(0)\n  Require(DOS.Input()=shell.console AND DOS.Output()=shell.console AND shell.directory<>DOS.FileLock POINTER(0))\n  directoryChecked=1 shellCheckpoint=1 Cleanup(0)')
    source=source.replace('PROC Cleanup(BYTE unused)\n', 'PROC Cleanup(BYTE unused)\n  DOS.FileLock POINTER previous\n')
    source=source.replace('  cleanupReached=1\n  SIODRIVER.Stop()', '  previous=DOS.CurrentDir(DOS.FileLock POINTER(0))\n  Require(previous=shell.directory AND DOS.IoErr()=0)\n  DOS.UnLock(previous) Require(DOS.IoErr()=0) shell.directory=DOS.FileLock POINTER(0)\n  Require(FSBOOT.Stop()<>0) directoryReleased=1 shellCheckpoint=2\n  cleanupReached=1\n  SIODRIVER.Stop()')
    source=source.replace('  okay=SIODRIVER.Start()\n  Require(okay=1)\n  SIODRIVER.Stop()', '  shellCheckpoint=3 okay=SIODRIVER.Start() Require(okay=1) SIODRIVER.Stop()\n  shellCheckpoint=4 Require(ShellFinish()=0)')
    for inc in ('tasks_exec_helpers.inc','io-names.inc'):source=source.replace('"'+inc+'"','"'+str(ROOT/'tests/programs'/inc)+'"')
    shutil.copyfile(ROOT/'tests/programs/sioprobe.act',out/'sioprobe.act')
    path=out/'shell-recovery.act';path.write_text(source)
    original_build,original_execute,original_clean=recovery.build,recovery.execute,recovery.clean_ownership
    media=out/'mydos.atr';shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',media);digest=sha256(media)
    def configured(toolchain,ignored,destination,**kwargs):
        p=build(toolchain,path,destination,**kwargs,console=True,task_capacity=8,dos_mounts=[dict(alias='D2',unit=50,sectors=720 if size==128 else 2000,sector_bytes=size,profile=1)])
        p['recovery_posts_baseline']='postsBaseline';return p
    def checked(b,p,**kwargs):
        before=kwargs.get('before_run');saved={}
        def mount(b):
            if before:before(b)
            b.mount(1,str(media));saved.update(screen=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['bytes']=b.memdump(saved['screen'],960)
        kwargs['before_run']=mount
        try:rt,state=execute(b,p,**kwargs)
        except Exception:
            print('Shell serial checkpoint',data(b,p['image'],'shellCheckpoint'), 'directory',data(b,p['image'],'directoryChecked'),data(b,p['image'],'directoryReleased'),flush=True);raise
        require(data(b,p['image'],'directoryChecked')==[1]and data(b,p['image'],'directoryReleased')==[1],'Fault did not preserve then retire selected directory')
        pointer=int.from_bytes(bytes(data(b,p['image'],'shell')),'little')
        ds=p['build']['memory']['dos_storage'];cs=p['build']['memory']['console_storage']
        far=lambda at,n:bytes(b.eval_expr(f'db(${at+i:x})')for i in range(n))
        registry=far(ds['STREAMS'],16);endpoint=int.from_bytes(registry[1:4],'little');instance=far(cs['INSTANCE'],62)
        if rt['status']==0xff93:
            require(pointer and registry[0]==2 and endpoint and instance[21]==1 and int.from_bytes(instance[:3],'little'),'Unsafe SIO reclaimed shell/RAW/console')
        else:
            require(not pointer and registry[0]==0 and not endpoint and instance[:3]==bytes(3),'Safe recovery retained shell/RAW')
            require(b.memdump(saved['screen'],960)==saved['bytes']and b.peek(752)==saved['cursor']and b.peek(16)==saved['mask'],'Safe recovery did not restore OS console')
        rt['shell_cleanup']=dict(directory_checked=True,directory_released=True,shell_pointer=pointer,registry=registry.hex(),console_instance=instance.hex(),unsafe_retained=rt['status']==0xff93)
        require(sha256(media)==digest,'MyDOS media changed');return rt,state
    recovery.build=configured;recovery.execute=checked;recovery.clean_ownership=ownership
    try:r=recovery.run(t,out,mode=='opt',['checksum','device','short','firstcause','framing','protocol'],sector_size=size)
    finally:recovery.build,recovery.execute,recovery.clean_ownership=original_build,original_execute,original_clean
    r.update(shell_fixture_sha256=sha256(path),media_sha256=digest,source_inputs={s:sha256(ROOT/s)for s in ('examples/shell/shell-session.inc','examples/shell/shell-commands.inc','examples/shell/shell-redirection.inc','tests/programs/sio_recovery.act','tools/shell_serial_recovery.py','tools/test_sio_recovery.py')})
    return r
