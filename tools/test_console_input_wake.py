#!/usr/bin/env python3
"""Controlled input publication races through the real text/bitmap worker."""
import argparse,json
from pathlib import Path
import generate_tasks
from build_bitmap_console import build_bitmap
from native_program import ROOT,build,compiler,read_build,require,verify_machine,sha256
from test_mouse_observe import PIN,BRIDGE,ROM
from test_dos_stack import execute,ownership
from test_cooperative import data
from os_boundary import emulator


def run(out,mode,bitmap=False,replay=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    (out/'program').mkdir(exist_ok=True)
    (out/'program/inputwakeprobe.act').write_bytes((ROOT/'tests/programs/inputwakeprobe.act').read_bytes())
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs)
        for name,replacements in {
            'consoledriver.act':[
                ('    bits=Collect(bits,displayMask)','    INPUTWAKEPROBE.Point(1)\n    bits=Collect(bits,displayMask)\n    INPUTWAKEPROBE.Point(2)'),
                ('        bits=EXEC.Wait($e0000000 OR displayMask)','        INPUTWAKEPROBE.Point(4)\n        bits=EXEC.Wait($e0000000 OR displayMask)'),
                ('          CONSOLEDISPLAY.Advance(view,instance,entry.unit)','          INPUTWAKEPROBE.Point(6)\n          CONSOLEDISPLAY.Advance(view,instance,entry.unit)')],
            'consoleinput.act': [('    IF status=INPUT.EMPTY THEN\n      EXIT','    IF status=INPUT.EMPTY THEN\n      INPUTWAKEPROBE.Point(3)\n      EXIT')],
            'input.act': [('      index==+1\n    UNTIL raw=', '      index==+1\n      IF index=RAW_SLOTS THEN\n        INPUTWAKEPROBE.Point(5)\n      FI\n    UNTIL raw=')]
        }.items():
            path=directory/name;s=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE INPUTWAKEPROBE\n',1)
            for old,new in replacements:
                require(s.count(old)==(2 if 'bits=EXEC.Wait' in old else 1),'Publication boundary changed: '+name+': '+old);s=s.replace(old,new)
            path.write_text(s)
        return directory
    generate_tasks.policy_modules=instrument
    try:
        source=ROOT/'tests/programs/console_input_wake.act'
        p=read_build(out/'program') if replay else (build_bitmap(source,out,mode=='opt') if bitmap else
            build(compiler(ROOT/'build/actionc'),source,out/'program',optimize=mode=='opt',tasks=True,task_capacity=8,console=True))
    finally:generate_tasks.policy_modules=original
    at=lambda n:next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_INPUTWAKE_'+n.upper()+'_'))
    require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
    result=dict(status='running',tier='development',mode=mode,bitmap=bitmap,build=p['build'],pin=PIN)
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            result['machine']=verify_machine(b,ROM,PIN)
            try:runtime,_=execute(b,p,before_run=lambda b:b.poke(at('bitmap'),int(bitmap)),timer_irq=not bitmap,frame_limit=12000,timeout=180)
            except Exception:
                print('Wake phase/checks/regs',data(b,p['image'],'phase'),data(b,p['image'],'checks',True),b.regs(),flush=True);raise
            require(data(b,p['image'],'finished')==[1],'Wake fixture did not finish')
            ownership(b,p,p['output'])
            result.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True))
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Console input wake passed',mode,'bitmap' if bitmap else 'text',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),required=True);p.add_argument('--bitmap',action='store_true');p.add_argument('--replay',action='store_true')
    a=p.parse_args();run(a.output,a.mode,a.bitmap,a.replay)
