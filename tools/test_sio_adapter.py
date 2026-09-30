#!/usr/bin/env python3
"""Run the production native SIO primitives inside the real Task kernel."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,execute,verify_machine,require,sha256
from os_boundary import emulator
from sio_transactions import PIN,disk_image
from test_cooperative import data
from ports_budget import current
from banked_test_memory import read as far_read
from sio_adapter_trace import analyze

def run(t,out,optimize,variant=0,trace=False,program=None):
    p=program or build(t,ROOT/'tests/programs/sio_adapter.act',out,optimize=optimize,tasks=True,io_test_device=True,
        image_data=[(a,bytes([0xa5])*256) for a in (0x8ffa0,0xcffa0)])
    disk_image(out/'disk.atr')
    if trace:
        os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k,v in p['labels'].items() if k.startswith(('sio_','native_','signal_route','dispatch_','context_restore'))))
    else:
        for key in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(key,None)
    bridge_dir=ROOT/('build/altirra-sio-observer' if trace else 'build/altirra-irq-bridge')
    expected=json.loads((ROOT/'toolchain/altirra-sio-observer.json').read_text())['binary_sha256'] if trace else PIN['emulator']['sha256']
    require(sha256(bridge_dir/'AltirraBridgeServer')==expected,'Unpinned SIO emulator')
    machine_out=out/('observed' if trace else 'replay');machine_out.mkdir(exist_ok=True)
    with emulator(bridge_dir,ROOT/'build/firmware/altirraos-816.rom',machine_out,pin=PIN) as bridge:
        for k,v in PIN['configuration'].items():bridge.config(k,str(v).lower() if isinstance(v,bool) else v)
        bridge.config('diskemu','fastest')
        machine=verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',PIN)
        snapshots={}
        def before(b):
            if variant==2:b.poke(0x42,3)
            for at,n in ((0x20a,10),(0x42,1),(0x232,1),(0x10,1)):
                snapshots[at]=b.memdump(at,n)
            if trace:b.profile_start()
            b.mount(0,str(out/'disk.atr'))
            address=next(d['address'] for d in p['image']['data'] if '_VARIANT_' in d['name'])
            b.poke(address,0 if variant==2 else variant)
        try:
            runtime,_=execute(bridge,p,before_run=before,expected_status=0xff93 if variant in (1,4) else 0,timeout=240,frame_limit=12000)
        except Exception:
            print('checks',data(bridge,p['image'],'checks',True), 'results',data(bridge,p['image'],'results',True),flush=True)
            # Diagnostic data only; never persist private bridge credentials.
            (out/'failure.json').write_text(json.dumps(dict(regs=bridge.regs(),pokey=bridge.pokey(),labels=p['labels']),indent=2)+'\n')
            raise
        if trace:bridge.profile_stop()
        if variant not in (1,4):
            for at,value in snapshots.items():require(bridge.memdump(at,len(value))==value,'SIO restoration '+hex(at))
        state=far_read(bridge,p['build']['task_storage']['BASE']+0x800,128,out)
        if variant==5:require(int.from_bytes(state[58:60],"little")>=9,"Missing emulation callbacks")
        for address in (0x8ffa0,0xcffa0):
            payload=far_read(bridge,address,256,out)
            require(payload[:32]==bytes([0xa5])*32 and payload[160:]==bytes([0xa5])*96,'SIO buffer guard')
        checks=data(bridge,p['image'],'checks',True)
        results=data(bridge,p['image'],'results',True)
        timing=analyze(machine_out/'emulator.log',p['labels']) if trace else None
        if timing:require(timing['verdict']=='pass','SIO byte/phase deadline: '+str(timing['violations']))
        result=dict(machine=machine,timing=timing,hardware_state=state.hex(),name=('timeout' if variant else 'transactions')+('-opt' if optimize else '-raw'),
            status='pass',build=p['build'],runtime=runtime,checks=checks,results=results,
            helper_bytes=len((out/'hosted.bin.signals').read_bytes()))
    if trace:
        replay=run(t,out,optimize,variant,False,program=p)
        for name in ('checks','results','hardware_state','runtime'):
            require(result[name]==replay[name],'Observer/replay differs: '+name)
        result['replay']=dict(status='identical',xex_sha256=sha256(p['xex']),emulator_sha256=PIN['emulator']['sha256'])
    return result

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--trace',action='store_true')
    a.add_argument('--case',choices=('raw','opt'),default='opt');a.add_argument('--variant',type=int,default=0)
    a.add_argument('--output',type=Path,default=ROOT/'build/sio-adapter');args=a.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',bank_zero=current(),cases=[])
    try:
        report['cases'].append(run(compiler(ROOT/'build/actionc'),out/args.case,args.case=='opt',args.variant,args.trace))
        report['status']='pass'
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed SIO adapter',args.case,args.variant,flush=True)
if __name__=='__main__':main()
