#!/usr/bin/env python3
"""Real keyboard break delivery without Read, retained routes and overflow."""
import adapter_state as adapter
import argparse,json,os,hashlib
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_banked import changed_image
from dos_concurrent_trace import call_marker
from sio_transaction_trace import read_events,BASE_HZ
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def run(out,optimize,bank,publication=False,removal=False,trace=False):
    out.mkdir(parents=True,exist_ok=True)
    source=out/'foreground_break.act'
    source.write_bytes((ROOT/'tests/programs/foreground_break.act').read_bytes())
    p=build(compiler(ROOT/'build/actionc'),source,out,optimize=optimize,tasks=True,
            task_capacity=8,console=True,kernel_bank=bank)
    def at(name):return next(x['address'] for x in p['image']['data'] if '_FOREGROUNDBREAKTEST_'+name.upper()+'_' in x['name'])
    # Deliberately stall only this qualification image between the two native
    # route stores until a real NMI runs. Keep the original guard and stack use.
    race={}
    if publication:
        start=p['labels']['input_publish'];end=p['labels']['input_publish_end']
        segment=next(s for s in p['image']['segments'] if s['address']<=start< s['address']+len(s['bytes']))
        offset=start-segment['address'];original=bytes(segment['bytes'][offset:offset+end-start])
        route=p['build']['memory']['console_storage']['CAPTURE']+28
        marker=b'\x8f'+route.to_bytes(3,'little');require(original.count(marker)==1,'Ambiguous route publication')
        split=original.index(marker)+4
        stage=at('publishStage').to_bytes(3,'little');gate=at('publishGate').to_bytes(3,'little')
        # A8: skip a released gate; otherwise expose the half-store and wait.
        delay=b'\xe2\x20\xaf'+gate+b'\xd0\x12\xa9\x01\x8f'+stage+b'\xaf'+gate+b'\xf0\xfa\xa9\x00\x8f'+stage+b'\xc2\x20'
        # Admission also publishes zero before enabling hardware. Stall the
        # first high-word rollover route, after the console has acquired input.
        guard=bytes.fromhex('a307c90100d0')+bytes([len(delay)])
        payload=original[:split]+guard+delay+original[split:];base=0xe0000
        p['image']['segments'].append(dict(address=base,bytes=list(payload),writable=False,executable=True))
        segment['bytes'][offset:offset+4]=[0x5c,0,0,14]
        changed_image(p)
        race.update(half=base+split,payload_sha256=hashlib.sha256(payload).hexdigest())
    marks=dict(capture=p['labels']['input_capture'],durable=call_marker(p,'M_CONSOLEFOREGROUND_NOTIFYONE_','tasks_signal'))
    for key in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(key,None)
    if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    events=[];saved={}
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        capture=p['build']['memory']['console_storage']['CAPTURE']
        def rendezvous(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
            b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):
                    require(b.peek16(adapter.STATE)==0xffff,'Foreground fixture stopped before checkpoint; checks='+str(b.peek16(at('checks')))+' status='+hex(b.peek16(adapter.STATE)))
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],12000,240,condition)
            finally:b.regs=original
        def frames(count):rendezvous(f'@frame>={b.eval_expr("@frame")+count}')
        def phase(number):
            rendezvous(f'db(${at("phase"):x})={number}')
            print('Foreground phase',number,'checks',b.peek16(at('checks')),flush=True)
        def key(name,state):
            require(b._cmd_ok(f'KEY {name} {state}')['raw_scan'],'Physical key input required')
            events.append(dict(key=name,state=state,frame=b.eval_expr('@frame')))
        def down(ctrl):
            if ctrl:key('CTRL','down')
            key('C' if ctrl else 'BREAK','down')
        def up(ctrl):
            key('C' if ctrl else 'BREAK','up')
            if ctrl:key('CTRL','up')
            frames(2)
        def before(b):
            saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752));saved['screen']=b.memdump(saved['at'],960)
            b._cmd_ok('KEY ALL up')
            if trace:b.profile_start()
            if removal:b.poke(at('removeMode'),1);return
            if publication:
                b.poke(at('publicationMode'),1)
                rendezvous(f'db(${at("publishStage"):x})=1')
                race.update(nmi_before=b.peek16(adapter.NMI_COUNT),irq_before=b.peek16(adapter.IRQ_COUNT),half_route=b.eval_expr(f'dw(${capture+28:x})')+(b.eval_expr(f'dw(${capture+30:x})')<<16))
                down(False)
                frames(2)
                require(b.peek16(adapter.NMI_COUNT)>=race['nmi_before']+2,'NMI did not enter split publication')
                require(b.peek16(adapter.IRQ_COUNT)==race['irq_before'],'IRQ observed a split route')
                require(b.eval_expr(f'db(${capture+40:x})')==0,'Split route published break')
                race.update(nmi_after=b.peek16(adapter.NMI_COUNT),irq_after=b.peek16(adapter.IRQ_COUNT))
                b.poke(at('publishGate'),1)
                phase(20)
                scope=int.from_bytes(b.memdump(at('scope'),3),'little')
                rendezvous(f'db(${scope+18:x})=1')
                published=int.from_bytes(b.memdump(capture+28,4),'little')
                scope_tag=int.from_bytes(b.memdump(scope+14,4),'little')
                require(published==scope_tag and published>>16==1,'IRQ route torn after publication')
                race['published_route']=published
                up(False);b.poke(at('gate'),1)
            phase(1);b.poke(at('gate'),1);frames(2);down(True);phase(2);up(True)
            b.poke(at('gate'),1);frames(2);down(False);phase(21);up(False)
            count=b.eval_expr(f'dw(${capture+10:x})');down(False)
            rendezvous(f'dw(${capture+10:x})>{count}');up(False)
            b.poke(at('gate'),1);phase(3)
            b.poke(at('gate'),1);phase(4);down(True)
            rendezvous(f'db(${capture+40:x})=1');up(True);b.poke(at('gate'),1);phase(5)
            b.poke(at('gate'),1);phase(6);down(False)
            rendezvous(f'db(${capture+40:x})=1');up(False);b.poke(at('gate'),1);phase(7)
            b.poke(at('gate'),1);phase(8);down(True)
            rendezvous(f'db(${capture+40:x})=1');up(True);b.poke(at('gate'),1);phase(9)
            rendezvous(f'(db(${capture+40:x})=0)&(db(${capture+1:x})=db(${capture+2:x}))')
            b.poke(at('gate'),1);phase(10);b.poke(at('gate'),1);frames(2);down(True)
            phase(11);key('C','up');key('CTRL','up');b.bp_clear_all()
        runtime,_=execute(b,p,before_run=before,expected_status=4 if removal else 0,timeout=1200,frame_limit=60000)
        if trace:b.profile_stop()
        if removal:
            require(b.peek(at('phase'))[0]==0 and b.peek16(at('checks'))>10,'Removal guard not reached')
        else:
            require(b.peek(at('phase'))[0]==11,'Foreground completion missing')
            require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'Console not restored')
            ownership(b,p,out)
        timing=None
        if trace:
            observations=read_events(out/'emulator.log')
            times=lambda name:[t for t,e in observations if e[0]=='cpu' and int(e[4],16)==marks[name]]
            captures,delivered=times('capture'),times('durable')
            require(len(captures)==7 and len(delivered)==4,'Missing/repeated physical break delivery')
            samples=[dict(kind=name,capture=captures[i],durable=d,ms=(d-captures[i])/BASE_HZ*1000) for name,i,d in zip(('compute','wait','translated-loss-held','ring-full-held'),(0,1,3,4),delivered)]
            require(all(0<=s['ms']<=100 for s in samples[:2]),'Break delivery exceeded 100 ms')
            timing=dict(marks=marks,samples=samples,captures=len(captures),signals=len(delivered),limit_ms=100,
                        scope='Passive capture entry to worker Signal call after durable pending store. First two samples have no intentional Forbid hold; last two include fixture holds. Two live Tasks during delivery; eight-Task timing remains B5.')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,pin=PIN,
                    checks=[b.peek16(at('checks'))],events=events,publication=race,removal_guard=removal,
                    timing=timing,
                    fixture_sha256=sha256(source),bank_zero=dict(fixed_delta=0,per_task_delta=0))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True)
    a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--publication',action='store_true');a.add_argument('--removal',action='store_true')
    a.add_argument('--trace',action='store_true')
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(out,args.case=='opt',args.bank,args.publication,args.removal,args.trace)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Foreground break passed',args.case,args.bank,flush=True)
