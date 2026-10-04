#!/usr/bin/env python3
"""Observe shell heap use while old/new CD locks are simultaneously owned."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,compiler,build,read_build,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def run(t,out,mode,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    s=(ROOT/'examples/shell/shell-session.inc').read_text().replace('PROC ShellWrite(','PROC NativeShellWrite(')
    old='  LET candidate=DOS.Lock(path,DOS.SHARED_LOCK)\n  LET lockError=DOS.IoErr()';require(s.count(old)==1,'Missing CD allocation sample')
    s=s.replace('INCLUDE \"shell-commands.inc\"','INCLUDE \"'+str(ROOT/'examples/shell/shell-commands.inc')+'\"')
    s=s.replace('INCLUDE \"shell-redirection.inc\"','INCLUDE \"'+str(ROOT/'examples/shell/shell-redirection.inc')+'\"')
    s=s.replace('INCLUDE \"shell-path.inc\"','INCLUDE \"'+str(ROOT/'examples/shell/shell-path.inc')+'\"')
    (out/'shell-heap-observed.inc').write_text(s.replace(old,old+'\n  ShellSample()'))
    (out/'shell_heap.act').write_bytes((ROOT/'tests/programs/shell_heap.act').read_bytes())
    p=read_build(out) if reuse else build(t,out/'shell_heap.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,
            system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)])
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media)
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned console bridge')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN)as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower()if isinstance(v,bool)else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        try:rt,_=execute(b,p,timeout=180,frame_limit=9000)
        except Exception:print('Shell heap checks',data(b,p['image'],'checks',True),flush=True);raise
        require(data(b,p['image'],'finished')==[1] and data(b,p['image'],'checks',True)==[8],'Incomplete heap sampling')
        values={k:int.from_bytes(bytes(data(b,p['image'],k)),'little')for k in ('baseline','minimum','peakUsed','peakObjects')}
        require(values['peakObjects']==3 and values['peakUsed']==values['baseline']-values['minimum'],'Bad heap sample')
        ownership(b,p,out)
    return dict(status='pass',mode=mode,build=p['build'],runtime=rt,machine=machine,pin=PIN,checks=8,heap=values,
                sample_scope='After candidate Lock (before CurrentDir/old UnLock) and completed RAW writes; observed allocated-byte maximum, not a universal transient-allocation bound.',
                hook_sha256=sha256(out/'shell-heap-observed.inc'),media_sha256=sha256(media),
                source_inputs={s:sha256(ROOT/s)for s in ('examples/shell/shell-session.inc','examples/shell/shell-commands.inc','tests/programs/shell_heap.act','tools/test_shell_heap.py')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reuse',action='store_true');p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    r=run(compiler(a.compiler_dir),out,a.case,a.reuse);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell heap passed',a.case,flush=True)
