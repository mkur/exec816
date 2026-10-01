#!/usr/bin/env python3
"""Focused native tiled-screen, captured focus, break and loss isolation checks."""
import adapter_state as adapter
import argparse,hashlib,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_console_display import glyph
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def expected(stage):
    result=bytearray(960)
    def tile(left,top,text):
        start=40*top+left
        result[start:start+len(text)]=bytes(map(glyph,text))
    if stage in (1,4,6):tile(0,0,b'AAA')
    if stage in (1,4,6,9):tile(20,0,b'bbb')
    if stage in (1,4,6,9,10):tile(0,12,b'CCC')
    if stage==12:tile(0,0,b'CCCHIDDEN')
    cursor={1:3,4:23,6:23,9:23,10:483,12:9,13:0}.get(stage)
    if cursor is not None:result[cursor]^=128
    return bytes(result)

def run(out,mode,bank):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/console_focus.act'
    p=build(compiler(ROOT/'build/actionc'),source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,kernel_bank=bank,dos_mounts=[])
    def at(name):return next(x['address'] for x in p['image']['data'] if '_CONSOLEFOCUSTEST_'+name.upper()+'_' in x['name'])
    saved={};observations=[];events=[]
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        capture=p['build']['memory']['console_storage']['CAPTURE']
        def rendezvous(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
            b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):
                    require(b.peek16(adapter.STATE)==0xffff,'Focus fixture stopped before checkpoint')
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],3000,60,condition)
            finally:b.regs=original
        def frames(n):rendezvous(f'@frame>={b.eval_expr("@frame")+n}')
        def press(key):
            old=b.eval_expr(f'dw(${capture+10:x})')
            if key=='CTRL-C':b._cmd_ok('KEY CTRL down');key='C'
            require(b._cmd_ok(f'KEY {key} down')['raw_scan'],'Physical input required')
            rendezvous(f'dw(${capture+10:x})>{old}')
            b._cmd_ok(f'KEY {key} up');b._cmd_ok('KEY CTRL up');frames(2)
            events.append(dict(key=key,frame=b.eval_expr('@frame')))
        def before(b):
            saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752))
            saved['screen']=b.memdump(saved['at'],960);b._cmd_ok('KEY ALL up')
            for stage in range(1,14):
                rendezvous(f'db(${at("phase"):x})={stage}')
                if stage in (1,4,6,9,10,11,12,13):
                    screen=b.memdump(saved['at'],960);oracle=expected(stage)
                    (out/f'stage-{stage}.screen.bin').write_bytes(screen)
                    require(screen==oracle,f'Exact tiled screen/cursor mismatch at stage {stage}: '+str([i for i,(a,c) in enumerate(zip(screen,oracle)) if a!=c][:12]))
                    observations.append(dict(stage=stage,screen_sha256=hashlib.sha256(screen).hexdigest()))
                if stage==2:press('A');press('BREAK')
                if stage==3:press('B');press('CTRL-C')
                if stage in (5,7):press('A')
                if stage==8:press('B')
                print('Focus checkpoint',stage,'checks',b.peek16(at('checks')),flush=True)
                b.poke(at('gate'),1)
            b.bp_clear_all()
        try:runtime,_=execute(b,p,before_run=before,timeout=180,frame_limit=9000)
        except Exception:
            print('Focus checks/phase/status',data(b,p['image'],'checks',True),data(b,p['image'],'phase'),hex(b.peek16(adapter.STATE)),flush=True);raise
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'OS screen/input restoration')
        require(runtime['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt reserve touched')
        ownership(b,p,out)
        return dict(status='pass',tier='development',mode=mode,bank=bank,checks=data(b,p['image'],'checks',True),build=p['build'],pin=PIN,machine=machine,runtime=runtime,observations=observations,events=events,source_inputs={str(source.relative_to(ROOT)):sha256(source),'tools/test_console_focus.py':sha256(ROOT/'tools/test_console_focus.py')})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',choices=('raw','opt'),required=True);parser.add_argument('--bank',type=int,choices=(1,3),default=1);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=run(args.output.resolve(),args.case,args.bank)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Console focus/presentation development checks passed',args.case,args.bank,flush=True)
