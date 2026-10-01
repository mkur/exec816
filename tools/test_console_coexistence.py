#!/usr/bin/env python3
"""Physical POKEY keyboard scan with the native SIO driver (slice 1)."""
import adapter_state as adapter
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from test_dos_stack import execute
from os_boundary import emulator,run_to
from sector_images import disk_image
from test_cooperative import data
from banked_test_memory import read as far_read
from sio_adapter_trace import analyze
from sio_transaction_trace import read_events,stats,BASE_HZ
from sio_concurrent_trace import alarm_observations,LIMITS

def masked_input_probe(p):
    from native_program import command
    from test_banked import changed_image
    out=p['output'];im=p['image']
    symbols={n:next(d['address'] for d in im['data'] if '_'+n+'_' in d['name']) for n in ('GATE','GATEREADY')}
    routine=next(r for r in im['routines'] if '_HOLDIRQS_' in r['name'])
    (out/'masked.cfg').write_text('MEMORY { RAM: start=$0e0000,size=$1000,file=%O; } SEGMENTS { PROBE: load=RAM,type=ro; }\n')
    command(['ca65','-D',f"READY={symbols['GATEREADY']}",'-D',f"GATE={symbols['GATE']}",'-o',out/'masked.o',ROOT/'tests/programs/console_masked_input.s'])
    command(['ld65','-C',out/'masked.cfg','-o',out/'masked.bin',out/'masked.o'])
    im['segments'].append(dict(address=0xe0000,bytes=list((out/'masked.bin').read_bytes()),writable=False,executable=True))
    segment=next(v for v in im['segments'] if v['address']==routine['address'])
    segment['bytes'][:4]=[0x5c,0,0,14]
    changed_image(p)

PIN=json.loads((ROOT/'toolchain/altirra-console.json').read_text())

def validate_capture(captured,state):
    require(len(state)==288 and not state[0] and not state[3],'Input ownership/overflow')
    # BREAK's keycode is immaterial: the event kind determines its byte.
    actual=[0x100 if v>>8==1 else v for v in captured]
    require(actual==[0x3f,0x15,0x7f,0xbf,0x100,0x0c,0x1c],f'Lost/duplicate/misqualified key events: {actual}')

def check_alarms(observed,labels):
    times=lambda name:[t for t,e in observed if e[0]=='cpu' and int(e[4],16)==labels[name]]
    start=times('sio_start')[0];stop=times('sio_shutdown')[0]
    active=[(t,e) for t,e in observed if start<=t<=stop]
    result={}
    for channel,name in ((0,'sio_alarm'),(1,'sio_watchdog')):
        delays,cancelled,missing=alarm_observations(active,times(name),times('sio_terminal'),stop,channel)
        require(delays and all(0<=v/BASE_HZ*1e6<=LIMITS['alarm_lateness_us'] for v in delays+cancelled+missing),
                'Console/SIO alarm lateness: '+name)
        result[name]=dict(service=stats(delays),cancelled_or_terminal=stats(cancelled+missing))
    return result

def run(t,out,optimize,mode=1,order=0,sector_size=128,trace=False,program=None,native=False,nmi=False):
    require(not trace or mode in (1,3),'Wire tracing requires continuous or recovering SIO')
    out.mkdir(parents=True,exist_ok=True)
    module='NATIVECONSOLEINPUT' if native else 'NATIVECONSOLEPROBE'
    p=program or build(t,ROOT/('tests/programs/native_console_input.act' if native else 'tests/programs/native_console_probe.act'),out,optimize=optimize,
            tasks=True,task_capacity=8,io_test_device=True,irq_probe=(1 if nmi else 0) if native else 10,console_test=native,
            image_data=[(0xd0000,bytes(62))] if native else ())
    if native and program is None:
        p['build']['console_fixture_inputs']={name:sha256(ROOT/name) for name in (
            'tests/programs/native_console_input.act','tests/programs/console_input_checks.inc',
            'tests/programs/console_masked_input.s','tools/test_console_coexistence.py','tools/test_console_input.py')}
    if native and mode==5 and program is None:masked_input_probe(p)
    machineout=out/('observed' if trace else 'replay');machineout.mkdir(exist_ok=True)
    for k in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS','EXEC816_SIO_FAULT_FILE'):
        os.environ.pop(k,None)
    if trace:
        os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',
            EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k,v in p['labels'].items() if k.startswith(('sio_','native_','console_','signal_route'))))
    require(sha256(ROOT/'build/console-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned console emulator')
    disk_image(machineout/'disk.atr',sector_size)
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',machineout,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','fastest')
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        events=[];saved={};observations={}
        def hardware():
            return {name:b.memdump(at,n).hex() for name,at,n in (
                ('irq_mask',0x10,1),('skctl_shadow',0x232,1),('vectors',0x208,12),('break_vector',0x236,2))}
        def symbol(name):
            matches=[d['address'] for d in p['image']['data'] if d['name'].startswith('M_'+module+'_'+name.upper()+'_')]
            require(len(matches)==1,'Missing/ambiguous probe symbol: '+name)
            return matches[0]
        def key(name,state):
            result=b._cmd_ok(f'KEY {name} {state}')
            require(result['raw_scan'],'Cooked keyboard input is not a scan test')
            events.append(dict(key=name,state=state,frame=b.eval_expr('@frame')))
        def checkpoint(frames=1,initial=False):
            b.bp_clear_all()
            cond=f'db(${symbol("ready"):x})=1' if initial else f'@frame>={b.eval_expr("@frame")+frames}'
            b.bp_set(p['labels']['native_nmi'],condition=cond)
            run_to(b,p['labels']['native_nmi'],frame_limit=600,timeout=30,condition=cond)
        def payload_checkpoint():
            state=p['build']['task_storage']['BASE']+0x800
            cond=f'(db(${state+1:x})=11)&(dw(${state+10:x})<8)'
            b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=cond)
            run_to(b,p['labels']['native_irq'],frame_limit=600,timeout=30,condition=cond)
        def retire_probe():
            if not native:b.bp_clear_all();return
            cond=f'db(${symbol("released"):x})=1'
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=cond)
            run_to(b,p['labels']['native_nmi'],frame_limit=600,timeout=30,condition=cond)
            cap=p['build']['task_storage']['BASE']+0xc00
            before=[b.eval_expr(f'db(${cap+i:x})') for i in range(32)]
            require(before[0]==0 and before[26]==0,'Callback binding not retired')
            key('ALL','up');checkpoint(4);key('C','down');checkpoint(4);key('C','up');checkpoint(4)
            after=[b.eval_expr(f'db(${cap+i:x})') for i in range(32)]
            require(before==after,'Key after release reached retired producer state')
            observations['retired_callback_unchanged']=True
            b.poke(symbol('retireGate'),1);b.bp_clear_all()
        def before(b):
            saved.update(hardware())
            b.mount(0,str(machineout/'disk.atr'))
            b.poke(symbol('mode'),mode);b.poke(symbol('order'),order)
            b.poke(symbol('sectorBytes'),sector_size&255);b.poke(symbol('sectorBytes')+1,sector_size>>8)
            key('ALL','up')
            if trace:b.profile_start()
            if mode==2:
                b.bp_clear_all();b.bp_set(p['labels']['sio_probe_os'])
                run_to(b,p['labels']['sio_probe_os'],frame_limit=600,timeout=30)
            else:checkpoint(initial=True)
            if native:
                observations['consumer_before_keys']=b.eval_expr('db($d000c)')
                require(observations['consumer_before_keys']==4,'Keyboard consumer was not waiting')
            if mode in (4,5):
                if mode==5:
                    cond=f'db(${symbol("gateReady"):x})=1'
                    b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=cond)
                    run_to(b,p['labels']['native_nmi'],frame_limit=600,timeout=30,condition=cond)
                for index in range(70 if mode==4 else 2):
                    name='A' if index%2==0 else 'B'
                    key(name,'down');checkpoint(4);key(name,'up');checkpoint(4)
                cap=p['build']['task_storage']['BASE']+0xc00
                observations['raw_before_release']=[b.eval_expr(f'db(${cap+i:x})') for i in range(4)]
                observations['skstat']=b.memdump(0xd20f,1).hex()
                if mode==4:require(observations['raw_before_release']==[1,64,0,1],'Raw ring did not fill/drop new')
                else:require(int(observations['skstat'],16)&0x40==0,'No physical keyboard overrun')
                b.poke(symbol('gate'),1)
                cond=f'db(${symbol("losses"):x})=1'
                b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=cond)
                run_to(b,p['labels']['native_nmi'],frame_limit=600,timeout=30,condition=cond)
                key('ESC','down');retire_probe();return
            for name,modifier,hold in [('A',None,120),('B',None,4),('A','SHIFT',4),('A','CTRL',4),('BREAK',None,4),('RETURN',None,4)]:
                # Real matrix scanning/debounce follows injection. Start later
                # presses at the beginning of a payload, not only in rotational
                # gaps between sectors. The long first hold spans setup/retire.
                if mode in (1,3) and (name!='A' or modifier):payload_checkpoint()
                if modifier:key(modifier,'down')
                key(name,'down');checkpoint(max(hold,32) if nmi else hold);key(name,'up')
                if modifier:key(modifier,'up')
                checkpoint(32 if nmi else 4)
            key('ESC','down');retire_probe()
        try:runtime,_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
        except Exception:
            print('Probe counters',{n:data(b,p['image'],n,True) for n in ('checks','received','transfers')},flush=True)
            raise
        if trace:b.profile_stop()
        if native and nmi:
            observations['post_nmi_checkpoints']=b.peek16(adapter.PROBE1)
            require(observations['post_nmi_checkpoints']>0,'No injected NMI during keyboard posting')
        key('ALL','up')
        restored=hardware()
        require(saved==restored,'Shared hardware state was not restored: '+str((saved,restored))+ ' capture='+far_read(b,p['build']['task_storage']['BASE']+0xc00,32,out).hex())
        count=data(b,p['image'],'received',True)[0]
        captured=data(b,p['image'],'events',True)[:count]
        from generate_console import constants
        cp=far_read(b,p['build']['task_storage']['BASE']+0xc00,constants()['CAPTURE_SIZE'] if native else 288,out)
        c=p['build']['memory']['constants']
        require(far_read(b,c['TABLE'],c['TABLE_BYTES'],out)==(out/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']],
                'Bank ownership leak')
        result=dict(status='observed',mode=mode,order=order,sector_size=sector_size,build=p['build'],machine=machine,runtime=runtime,
            injected=events,captured=captured,checks=data(b,p['image'],'checks',True),transfers=data(b,p['image'],'transfers',True),
            input_state=cp.hex(),native_events=int.from_bytes(cp[10:12],'little'),emulation_events=int.from_bytes(cp[12:14],'little'),
            input_observations=observations,losses=data(b,p['image'],'losses') if native else [],
            failures=data(b,p['image'],'failures',True),media_sha256=sha256(machineout/'disk.atr'),hardware_before=saved,hardware_after=restored)
        (out/'functional.json').write_text(json.dumps(result,indent=2)+'\n')
        if native:
            require(not cp[0] and not cp[3],'Input ownership/overflow')
            require(captured==([27] if mode in (4,5) else [97,98,65,1,3,10,27]),'Incorrect translated input: '+str(captured))
            require(result['losses']==([1] if mode in (4,5) else [0]),'Incorrect loss report count')
        else:validate_capture(captured,cp)
        require(mode not in (1,3) or result['transfers'][0]>=10,'Insufficient sustained SIO')
        require(mode!=3 or result['failures']==[1],'Recovery not exercised')
        require(mode!=2 or result['emulation_events']>0,'Emulation callback was not exercised')
        if trace:
            observed=read_events(machineout/'emulator.log')
            timing=analyze(machineout/'emulator.log',p['labels'],all_events=observed)
            begin=p['labels']['signal_route_begin'];end=p['labels']['signal_route_return']
            entered=None;durations=[]
            for tick,event in observed:
                if event[0]!='cpu':continue
                pc=int(event[4],16)
                if pc==begin:
                    require(entered is None,'Nested IRQ routing');entered=tick
                elif pc==end:
                    require(entered is not None,'Unpaired IRQ routing');durations.append(tick-entered);entered=None
            require(entered is None and durations,'Incomplete IRQ trace')
            timing['combined_irq_routing']=stats(durations)
            timing['capture_sio_phases']=[int(event[5],16)&255 for tick,event in observed
                if event[0]=='cpu' and int(event[4],16)==p['labels']['console_capture_phase' if native else 'console_probe_phase']]
            require(11 in timing['capture_sio_phases'],'No keyboard event captured during a serial payload')
            timing['alarms']=check_alarms(observed,p['labels'])
            (out/'timing.json').write_text(json.dumps(timing,indent=2)+'\n')
            require(timing['verdict']=='pass','Serial timing: '+str(timing['violations']))
            result['timing']=timing
        result['status']='pass'
    if trace:
        replay=run(t,out,optimize,mode,order,sector_size,False,p,native,nmi)
        for field in ('runtime','captured','checks','transfers','input_state','native_events','emulation_events','injected','failures'):
            require(result[field]==replay[field],'Observer changed '+field)
        result['replay']={'status':'identical','xex_sha256':sha256(p['xex']),'emulator_sha256':PIN['emulator']['sha256']}
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),default='opt')
    parser.add_argument('--mode',type=int,choices=(0,1,2,3),default=1)
    parser.add_argument('--order',type=int,choices=(0,1),default=0)
    parser.add_argument('--sector-size',type=int,choices=(128,256),default=128)
    parser.add_argument('--trace',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'build/console-slice1/probe')
    a=parser.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);result={'status':'running'}
    try:result=run(compiler(ROOT/'build/actionc'),out,a.case=='opt',a.mode,a.order,a.sector_size,a.trace)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Console coexistence passed',a.case,a.mode,a.order,a.sector_size,flush=True)
if __name__=='__main__':main()
