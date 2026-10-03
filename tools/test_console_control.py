#!/usr/bin/env python3
"""Emitted worker-only presentation, competing controls and retained callers."""
import argparse
import json
from pathlib import Path
import generate_tasks
from native_program import ROOT,build,compiler,read_build,require,verify_machine,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out,mode,replay=False):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/console_control.act'
    (out/source.name).write_bytes(source.read_bytes())
    (out/'controlprobe.act').write_bytes((ROOT/'tests/programs/controlprobe.act').read_bytes())
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs)
        path=directory/'consolecontrol.act';text=path.read_text()
        needle='  result=Apply(control.operation,'
        require(text.count(needle)==1,'Missing control execution boundary')
        text=text.replace('USE EXEC\n','USE EXEC\nUSE CONTROLPROBE\n',1)
        path.write_text(text.replace(needle,'  CONTROLPROBE.Gate(0)\n'+needle))
        path=directory/'consoledisplay.act';text=path.read_text()
        text=text.replace('USE A816MEMORY\n','USE A816MEMORY\nUSE CONTROLPROBE\n',1)
        needle='  IF view.cursorOn<>0 THEN'
        require(text.count(needle)==1,'Missing cursor-store boundary')
        text=text.replace(needle,'  CONTROLPROBE.Store(0)\n'+needle)
        path.write_text(text)
        path=directory/'consoledriver.act';text=path.read_text()
        text=text.replace('USE EXEC\n','USE EXEC\nUSE CONTROLPROBE\n',1)
        needle='        bits=EXEC.Wait($e0000000)'
        require(text.count(needle)==1,'Missing idle boundary')
        path.write_text(text.replace(needle,'        CONTROLPROBE.Idle(0)\n'+needle))
        return directory
    generate_tasks.policy_modules=instrument
    try:p=read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc'),out/source.name,out/'program',optimize=mode=='opt',tasks=True,task_capacity=8,console=True,dos_mounts=[])
    finally:generate_tasks.policy_modules=original
    address=next(d['address'] for d in p['image']['data'] if '_CONSOLECONTROLTEST_MODE_' in d['name'])
    reports=[]
    for scenario in (0,1):
        folder=out/f'case-{scenario}';folder.mkdir(exist_ok=True);saved={}
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',folder,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            def before(b):
                b.poke(address,scenario)
                saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16))
                saved['screen']=b.memdump(saved['at'],960)
            try:runtime,_=execute(b,p,before_run=before,expected_status=4 if scenario else 0,timeout=180,frame_limit=9000)
            except Exception:
                print('Control checks',data(b,p['image'],'checks',True),flush=True);raise
            if not scenario:
                require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'],'OS state not restored')
                ownership(b,p,p['output'])
            reports.append(dict(scenario=scenario,checks=data(b,p['image'],'checks',True),runtime=runtime,machine=machine))
    return dict(status='pass',tier='development',mode=mode,build=p['build'],pin=PIN,cases=reports,
        source_inputs={str(q.relative_to(ROOT)):sha256(q) for q in [source,ROOT/'tests/programs/controlprobe.act',Path(__file__)]},
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),upper_metadata_delta=16)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--replay',action='store_true');a=p.parse_args()
    result=run(a.output.resolve(),a.case,a.replay);(a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Worker presentation checks passed',a.case)
