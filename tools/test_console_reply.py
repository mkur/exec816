#!/usr/bin/env python3
"""Bounded presentation before short-write reply, cancellation and ownership."""
import argparse,json
from pathlib import Path
import generate_tasks
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from stack_budget import stack_usage


def run(out,mode,bitmap=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/console_reply.act'
    (out/'consolereplyprobe.act').write_bytes((ROOT/'tests/programs/consolereplyprobe.act').read_bytes())
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs);path=directory/'consoledriver.act'
        text=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE CONSOLEREPLYPROBE\n',1)
        needle='          CONSOLEDISPLAY.Present(view,instance)'
        require(text.count(needle)==1,'Presentation boundary changed')
        text=text.replace(needle,
            '          IF completeWrite<>0 THEN\n            CONSOLEREPLYPROBE.Before(instance)\n          FI\n'+needle+
            '\n          IF completeWrite<>0 THEN\n            CONSOLEREPLYPROBE.After(instance)\n          FI')
        path.write_text(text);return directory
    generate_tasks.policy_modules=instrument
    try:
        if bitmap:
            from build_bitmap_console import build_bitmap
            p=build_bitmap(source,out,mode=='opt')
        else:
            p=build(compiler(ROOT/'build/actionc'),source,out/'program',optimize=mode=='opt',
                    tasks=True,task_capacity=8,console=True,dos_mounts=[])
    finally:generate_tasks.policy_modules=original
    if bitmap:
        from test_mouse_observe import PIN,BRIDGE,ROM
    else:
        PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
        BRIDGE=ROOT/'build/shell-paced-bridge';ROM=ROOT/'build/firmware/altirraos-816.rom'
    report=dict(status='running',tier='development',mode=mode,bitmap=bitmap,build=p['build'],pin=PIN,
                scope='Fixture-only worker gates exercise cancellation, hidden output, one presentation budget and 64/65-byte boundaries. No timing claim.',
                source_inputs={str(q.relative_to(ROOT)):sha256(q) for q in (source,ROOT/'tests/programs/consolereplyprobe.act',ROOT/'lib/console/consoledriver.act')},
                bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN);saved={}
            def before(b):
                saved.update(at=b.peek16(88),dma=b.memdump(0x22f,3))
                saved['screen']=b.memdump(saved['at'],960)
            runtime,_=execute(b,p,before_run=before,frame_limit=6000,timeout=90)
            ownership(b,p,p['output'])
            require(b.memdump(saved['at'],960)==saved['screen'] and
                    b.memdump(0x22f,3)==saved['dma'],'OS screen not restored')
            usage=stack_usage(b,p['build']['memory'])
            require(all(v['remaining_above_floor']>0 for v in usage.values()),'Stack budget exhausted')
            report.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),stack_usage=usage)
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Console reply ordering passed',mode,'bitmap' if bitmap else 'text',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--bitmap',action='store_true')
    a=p.parse_args();run(a.output,a.mode,a.bitmap)
