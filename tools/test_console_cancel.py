#!/usr/bin/env python3
"""Interrupt console requests, retain exact reply ownership and committed bytes."""
from library_paths import read_source
import argparse,json
from pathlib import Path
import generate_tasks
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_console_display import terminal
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def run(out,optimize,bank):
    out.mkdir(parents=True,exist_ok=True)
    for f in ('console_cancel.act','waitprobe.act'):(out/f).write_bytes((ROOT/'tests/programs'/f).read_bytes())
    source=read_source(ROOT/'lib/dos/doscancel.act').replace('USE EXEC','USE EXEC\nUSE WAITPROBE')
    source=source.replace('  EXEC.SendIO(request)','  WAITPROBE.Before(request) EXEC.SendIO(request) WAITPROBE.Submitted(request)')
    source=source.replace('        EXEC.AbortIO(request)','        WAITPROBE.Aborted(request) EXEC.AbortIO(request)')
    source=source.replace('error=EXEC.WaitIO(request)','error=EXEC.WaitIO(request) WAITPROBE.Collected(request)')
    source=source.replace('RETURN(EXEC.WaitIO(request))','error=EXEC.WaitIO(request) WAITPROBE.Collected(request) RETURN(error)')
    (out/'doscancel.act').write_text(source)
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs)
        p=directory/'consoledriver.act';s=p.read_text().replace('USE EXEC\n','USE EXEC\nUSE WAITPROBE\n')
        s=s.replace('  FinishRead(instance,request)','  WAITPROBE.Copied(instance,request)\n  FinishRead(instance,request)')
        p.write_text(s);return directory
    generate_tasks.policy_modules=instrument
    try:p=build(compiler(ROOT/'build/actionc'),out/'console_cancel.act',out,optimize=optimize,tasks=True,task_capacity=8,console=True,kernel_bank=bank)
    finally:generate_tasks.policy_modules=original
    def at(name,module='CONSOLECANCELTEST'):return next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    events=[];screens=[];saved={}
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        cs=p['build']['memory']['console_storage'];instance=cs['INSTANCE'];capture=cs['CAPTURE']
        def far(a,n):return bytes(b.eval_expr(f'db(${a+i:x})') for i in range(n))
        def pointer(a):return int.from_bytes(far(a,3),'little')
        def rendezvous(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);b.bp_set(p['labels']['done'],condition='dw($2000)!=$ffff')
            original_regs=b.regs
            def regs():
                r=original_regs()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):
                    require(b.peek16(0x2000)==0xffff,'Console cancel stopped: '+hex(b.peek16(0x2000))+' checks='+str(b.peek16(at('checks'))))
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],20000,400,condition)
            finally:b.regs=original_regs
        def frames(n):rendezvous(f'@frame>={b.eval_expr("@frame")+n}')
        def phase(n):
            rendezvous(f'db(${at("phase"):x})={n}')
            print('Cancel phase',n,'checks',b.peek16(at('checks')),flush=True)
        def go():b.poke(at('gate'),1)
        def key(name,state):
            require(b._cmd_ok(f'KEY {name} {state}')['raw_scan'],'Physical key required')
            events.append(dict(key=name,state=state,frame=b.eval_expr('@frame')))
        def press(name,condition=None):
            key(name,'down')
            if condition:rendezvous(condition)
            else:frames(2)
            key(name,'up');frames(2)
        def break_down():key('BREAK','down')
        def break_up():key('BREAK','up');frames(2)
        def waiting():rendezvous(f'db(${cs["INSTANCE"]+51:x})=2')
        def typed(text,line):
            for index,char in enumerate(text):
                if char=='\n':press('RETURN')
                else:press(char.upper(),f'dw(${line+2:x})={index+1}')
        def pending(scope):rendezvous(f'db(${scope+18:x})=1')
        def before(b):
            saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752));saved['screen']=b.memdump(saved['at'],960)
            b._cmd_ok('KEY ALL up')
            phase(1);scope=pointer(at('scope'));line=pointer(at('line'))
            break_down();pending(scope);break_up();go()
            phase(2);go();waiting();break_down();phase(3);break_up()
            go();waiting();typed('abc',line);break_down();phase(4);break_up()
            go();waiting();typed('ok\n',line)
            phase(8);go();rendezvous(f'db(${at("stage","WAITPROBE"):x})=1')
            break_down();rendezvous(f'db(${capture+40:x})=1');b.poke(at('gate','WAITPROBE'),1)
            phase(9);break_up();go();waiting();frames(3)
            require(b.peek(at('phase'))==b'\x09','Stale signal completed Read')
            press('A');phase(5);go()
            target=pointer(at('target','WAITPROBE'))
            rendezvous(f'(db(${target+6:x})=5)&(db(${at("sends","WAITPROBE"):x})=1)')
            require(pointer(instance+37)!=target,'Write was not queued behind peer')
            break_down();pending(scope);break_up();phase(6);go()
            rendezvous(f'(dw(${target+26:x})>=1000)&(db(${instance+20:x})=1)')
            break_down();phase(7);break_up()
            count=int.from_bytes(b.memdump(at('results')+5*4,4),'little',signed=True)
            expected=bytes(10 if (i+1)%40==0 else 65 for i in range(count))
            cells,screen,cursor=terminal(expected)
            rendezvous(f'dw(${instance+14:x})>=dw(${instance+16:x})');frames(3)
            require(far(pointer(instance),960)==cells,'Canceled Write prefix differs from retained screen')
            require(b.memdump(saved['at'],960)==screen,'Canceled Write prefix differs from physical screen')
            screens.append(dict(bytes=count,cursor=cursor,screen_sha256=__import__('hashlib').sha256(screen).hexdigest()))
            go();rendezvous(f'db(${at("stage","WAITPROBE"):x})=1')
            rendezvous(f'db(${target+6:x})=7')
            break_down();pending(scope);break_up();b.poke(at('gate','WAITPROBE'),1)
            phase(10);go();waiting();break_down();phase(11);break_up()
            go();waiting();press('S');press('U');press('F');press('RETURN')
            phase(12);go();waiting();typed('z\n',line)
            phase(13);break_down();pending(scope);break_up();go();phase(14);b.bp_clear_all()
        runtime,_=execute(b,p,before_run=before,timeout=1800,frame_limit=90000)
        ownership(b,p,out)
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'OS console not restored')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,pin=PIN,
                    checks=data(b,p['image'],'checks',True),results=data(b,p['image'],'results'),errors=data(b,p['image'],'errors'),
                    events=events,screens=screens,observers={n:sha256(out/n) for n in ('doscancel.act','waitprobe.act','task-kernel/consoledriver.act')},
                    bank_zero=dict(fixed_delta=0,per_task_delta=0))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True)
    a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(out,args.case=='opt',args.bank)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Console cancellation passed',args.case,args.bank,flush=True)
