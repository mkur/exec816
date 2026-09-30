#!/usr/bin/env python3
"""Configured console startup, rollback, close/reopen and service retirement."""
import argparse,json
import generate_tasks
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,verify_machine,require,sha256
from os_boundary import emulator,run_to
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(t,out,mode,optimize,paced=False,from_build=None):
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text()) if paced else PIN
    bridge=ROOT/'build/shell-paced-bridge' if paced else ROOT/'build/console-bridge'
    require(sha256(bridge/'AltirraBridgeServer')==pin['emulator']['sha256'],'Unpinned console emulator')
    out.mkdir(parents=True,exist_ok=True)
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs)
        path=directory/'consoledriver.act'
        text=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE CONSOLESTARTPROBE\n')
        lifetime=(ROOT/'lib/console/console-lifetime.inc').read_text()
        needle='  service.generation==+1'
        require(lifetime.count(needle)==1,'Missing worker admission checkpoint')
        lifetime=lifetime.replace(needle,needle+'\n  IF CONSOLESTARTPROBE.reservedBit<>0 THEN item.tc_SigAlloc=item.tc_SigAlloc OR (LONGCARD(1) LSH CONSOLESTARTPROBE.reservedBit) FI')
        probe=directory/'console-lifetime-probe.inc'
        probe.write_text(lifetime)
        text=text.replace(str(ROOT/'lib/console/console-lifetime.inc'),str(probe.resolve()))
        path.write_text(text)
        return directory
    generate_tasks.policy_modules=instrument
    try:
        p=read_build(from_build) if from_build else build(t,ROOT/'tests/programs/native_console_lifetime.act',out,optimize=optimize,tasks=True,task_capacity=8,console=True,image_data=[(0xd0000,bytes(448))])
    finally:generate_tasks.policy_modules=original
    require(p['build']['optimize']==optimize,'Reused build mode differs')

    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin);saved={};stimuli=[]
        def at(name):return next(x['address'] for x in p['image']['data'] if '_NATIVECONSOLELIFETIME_'+name+'_' in x['name'])
        def rendezvous(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
            b.bp_set(p['labels']['done'],condition='dw($2000)!=$ffff')
            original=b.regs
            def regs():
                r=original();pc=int(r['PC'].lstrip('$'),16)
                if pc in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(0x2000)==0xffff,'Console stopped before lifecycle checkpoint')
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],3000,60,condition)
            finally:b.regs=original
        def restored():
            require(b.memdump(saved['at'],960)==saved['screen'],'Screen not restored')
            require(b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'] and b.memdump(520,2)==saved['key'] and b.memdump(566,2)==saved['break'],'Console ownership not restored')
        def before(b):
            saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16),key=b.memdump(520,2),**{'break':b.memdump(566,2)})
            saved['screen']=b.memdump(saved['at'],960)
            b.poke(at('MODE'),mode)
            if mode==5:b.poke(0x57,1)
            if mode==4:
                rendezvous(f'db(${at("CHECKPOINT"):x})=5');restored();b.poke(at('GATE'),1)
            if mode==9:
                b._cmd_ok('KEY ALL up')
                for checkpoint,key in ((10,'A'),(11,'B'),(12,'C'),(13,'D')):
                    rendezvous(f'db(${at("CHECKPOINT"):x})={checkpoint}')
                    b._cmd_ok(f'KEY {key} down');rendezvous(f'@frame>={b.eval_expr("@frame")+4}')
                    b._cmd_ok(f'KEY {key} up');rendezvous(f'@frame>={b.eval_expr("@frame")+4}')
                    stimuli.append(dict(checkpoint=checkpoint,key=key,held_frames=4,released_frames=4));b.poke(at('GATE'),1)
            b.bp_clear_all()
        expected=4 if mode in (1,2) else 0xff95 if mode==5 else 0
        try:rt,_=execute(b,p,before_run=before,expected_status=expected,timeout=240,frame_limit=12000)
        except Exception:
            print('Checks/checkpoint',data(b,p['image'],'checks',True),data(b,p['image'],'checkpoint'),flush=True);raise
        if mode!=4:restored()
        else:require(rt['os_calls']==1 and bytes(v-32 for v in b'ROM') in b.memdump(saved['at'],960),'Unexpected ROM console result')
        require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt reserve touched')
        ownership(b,p,p['output'])
        if mode==3:require(data(b,p['image'],'childDone')==[1],'Child did not finish after root')
        require(data(b,p['image'],'checkpoint')==[{0:4,1:1,2:2,3:3,4:7,5:0,6:6,7:6,8:6,9:14}[mode]],'Missing cleanup checkpoint')
        return dict(status='pass',build=p['build'],machine=machine,pin=pin,runtime=rt,mode=mode,checks=data(b,p['image'],'checks',True),stimuli=stimuli)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),default='opt');a.add_argument('--mode',type=int,choices=range(10),default=0);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--paced',action='store_true');a.add_argument('--from-build',type=Path);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(None if args.from_build else compiler(ROOT/'build/actionc'),out,args.mode,args.case=='opt',args.paced,args.from_build)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Lifetime passed',args.mode,args.case,flush=True)
