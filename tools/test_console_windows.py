#!/usr/bin/env python3
"""Focused native window lifetime/isolation checks; no SIO or timing matrix."""
from library_paths import read_source
import argparse,json
import generate_tasks
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/console_windows.act'
    (out/'console_windows.act').write_bytes(source.read_bytes())
    (out/'windowprobe.act').write_bytes((ROOT/'tests/programs/windowprobe.act').read_bytes())
    console=read_source(ROOT/'lib/console/console.act').replace('USE EXEC\n','USE EXEC\nUSE WINDOWPROBE\n',1).replace('EXEC.AllocMem(', 'WINDOWPROBE.AllocMem(')
    (out/'console.act').write_text(console)
    mirror=read_source(ROOT/'lib/console/consolemirror.act').replace('USE EXEC\n','USE EXEC\nUSE WINDOWPROBE\n',1).replace('EXEC.AllocMem(', 'WINDOWPROBE.AllocMem(')
    (out/'consolemirror.act').write_text(mirror)
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs)
        path=directory/'consoledriver.act'
        text=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE WINDOWPROBE\n',1)
        text=text.replace('  CONSOLEDISPLAY.Adopt(view,instance)',
            '  CONSOLEDISPLAY.Adopt(view,instance)\n  WINDOWPROBE.Claimed(view)')
        path.write_text(text)
        return directory
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json'
    memory.write_text(json.dumps(profile,indent=2)+'\n')
    generate_tasks.policy_modules=instrument
    try:
        p=build(compiler(ROOT/'build/actionc',release=True),out/'console_windows.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,dos_mounts=[],memory_profile=memory)
    finally:generate_tasks.policy_modules=original
    address=next(d['address'] for d in p['image']['data'] if '_CONSOLEWINDOWTEST_MODE_' in d['name'])
    results=[]
    for scenario in (0,1,2):
        path=out/f'case-{scenario}';path.mkdir(exist_ok=True);saved={}
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',path,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            def before(b):
                b.poke(address,scenario)
                saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16))
                saved['screen']=b.memdump(saved['at'],960)
            try:runtime,_=execute(b,p,before_run=before,expected_status=4 if scenario else 0,timeout=180,frame_limit=9000)
            except Exception:
                print('Window checks',data(b,p['image'],'checks',True),'scenario',scenario,flush=True);raise
            if scenario==0:
                # Startup writes the version banner before acquiring the display.
                # Compare the exact Claim snapshot, rather than pre-startup text.
                baseline=next(d['address'] for d in p['image']['data'] if '_WINDOWPROBE_BASELINE_' in d['name'])
                require(b.memdump(saved['at'],960)==b.memdump(baseline,960)
                    and b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'],
                    'OS console not restored to its acquisition snapshot')
                ownership(b,p,out)
            else:require(runtime['status']==4,'Expected lifetime guard')
            results.append(dict(scenario=scenario,checks=data(b,p['image'],'checks',True),runtime=runtime,machine=machine))
    return dict(status='pass',tier='development',mode=mode,build=p['build'],pin=PIN,cases=results,
                source_inputs={str(source.relative_to(ROOT)):sha256(source),'tests/programs/windowprobe.act':sha256(ROOT/'tests/programs/windowprobe.act'),'tools/test_console_windows.py':sha256(ROOT/'tools/test_console_windows.py')},
                observer_sha256=sha256(out/'console.act'))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',choices=('raw','opt'),required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=run(args.output.resolve(),args.case)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Window lifetime/isolation development checks passed',args.case,flush=True)
