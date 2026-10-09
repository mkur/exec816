#!/usr/bin/env python3
"""Qualify actual queued device traffic with four/eight simultaneously live tasks."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,verify_machine,sha256
from os_boundary import emulator,run_to
from sector_images import disk_image
from test_cooperative import data
from banked_test_memory import read as far_read
from test_sio_device import PIN
from sio_concurrent_trace import analyze

def run(t,out,optimize,capacity,speed,bank,trace=False,program=None,key=False,fault=None,sector_size=128):
    require(sector_size==128 or (sector_size==256 and speed==0 and not fault),'Unsupported sector profile')
    source=ROOT/'tests/programs/sio_concurrent.act'
    if speed==2:
        # The short NONE exchange can finish between root phase samples. Its
        # CPU progress is checked from passive routine entries during the wire.
        (out/'io-names.inc').write_bytes((source.parent/'io-names.inc').read_bytes())
        text=source.read_text().replace('AND activeWork<>0','AND (activeWork<>0 OR speed=2)')
        source=out/'sio_concurrent.act';source.write_text(text)
    if fault:
        from sio_concurrent_faults import source as fault_source
        source=fault_source(source,out,fault)
    p=program or build(t,source,out,optimize=optimize,tasks=True,task_capacity=capacity,kernel_bank=bank,image_data=[(0xd0000,bytes(512))])
    machineout=out/('observed' if trace else 'replay');machineout.mkdir(exist_ok=True)
    for unit in (0,1):disk_image(machineout/f'disk{unit}.atr',sector_size)
    for k in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(k,None)
    marks={k:v for k,v in p['labels'].items() if k.startswith(('sio_','native_','signal_route','signal_post','tasks_forbid','tasks_permit'))}
    marks.update({r['name']:r['address'] for r in p['image']['routines'] if r['name'].startswith(('M_SIODRIVER_','M_SIOCONCURRENT_'))})
    marks['root_dp']=p['build']['memory']['task_pools'][0]['dp']
    marks['collected']=next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_SIOCONCURRENT_RECORDCOLLECTION_'))
    if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k,v in marks.items() if k!='root_dp'))
    binary=ROOT/('build/altirra-sio-multi-observer' if trace else 'build/altirra-sio-multi')
    require(sha256(binary/'AltirraBridgeServer')==(PIN['observer']['binary_sha256'] if trace else PIN['emulator']['sha256']),'Unpinned concurrency emulator')
    with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',machineout,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu',('fastest','810','happy1050')[speed])
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            for unit in (0,1):b.mount(unit,str(machineout/f'disk{unit}.atr'))
            for name,value in [('SPEED',speed)]:
                symbol=next(d for d in p['image']['data'] if '_'+name+'_' in d['name']);b.poke(symbol['address'],value)
            symbol=next(d for d in p['image']['data'] if '_SECTORSIZE_' in d['name'])
            for index,value in enumerate(sector_size.to_bytes(2,'little')):b.poke(symbol['address']+index,value)
            if trace:b.profile_start()
            if key:
                symbol=next(d for d in p['image']['data'] if '_ACTIVEMIRROR_' in d['name'])
                condition=f'db(${symbol["address"]:x})=1' if speed!=2 else 'db($f0801)=1'
                b.bp_set(p['labels']['native_irq'],condition=condition)
                run_to(b,p['labels']['native_irq'],frame_limit=12000,timeout=240,condition=condition)
                b.key('A');b.bp_clear_all()
        try:runtime,_=execute(b,p,before_run=before,expected_status=0xff93 if fault=='timeout' else 0,timeout=600,frame_limit=30000)
        except Exception:
            print('failure counters',{n:data(b,p['image'],n,True) for n in ('checks','submitted','collected','outstanding','workRounds','activeWork')},flush=True)
            raise
        if trace:b.profile_stop()
        observed={n:data(b,p['image'],n,True)[0] for n in ('checks','submitted','collected','peakTasks','peakOutstanding','workRounds','activeWork','heapRounds','registryRounds','portRounds','signalRounds')}
        count=(capacity-2)*6
        require(observed['peakTasks']==capacity and observed['submitted']==observed['collected']==count,'Incomplete simultaneous workload')
        require(fault=='timeout' or speed==2 or observed['activeWork']>0,'No background work during transfers')
        order=data(b,p['image'],'submittedOrder')[:count];collected=data(b,p['image'],'collectedOrder')[:count]
        require(sorted(order)==sorted(collected) and len(set(order))==count,'Duplicate or lost request identity')
        c=p['build']['memory']['constants']
        if fault!='timeout':require(far_read(b,c['TABLE'],c['TABLE_BYTES'],out)==(out/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']],'Bank ownership leak')
        hardware=far_read(b,p['build']['task_storage']['BASE']+0x800,128,out)
        posts=int.from_bytes(hardware[56:58],'little')
        if fault=='timeout':
            require(hardware[0]==hardware[45]==1 and 1<=posts<count,'Missing offline ownership')
            require(hardware[12:15]==hardware[16:19]==bytes(3),'Retained caller buffer')
            observed.update({n:data(b,p['image'],n,True)[0] for n in ('timeoutReplies','offlineReplies')})
        else:
            require(hardware[0]==hardware[1]==hardware[45]==0,'Bus did not shut down cleanly')
            require(posts==(count//2 if fault else count),'Terminal post count mismatch')
        (out/'functional.json').write_text(json.dumps(dict(runtime=runtime,observed=observed,submission_order=order,collection_order=collected,hardware=hardware.hex(),marks=marks),indent=2)+'\n')
        timing=analyze(machineout/'emulator.log',marks,order,collected,speed,sector_size) if trace else None
        if timing:
            (out/'timing.json').write_text(json.dumps(timing,indent=2)+'\n')
            require(timing['verdict']=='pass','Wire timing failed: '+str(timing['violations']))
        result=dict(status='pass',build=p['build'],runtime=runtime,machine=machine,observed=observed,submission_order=order,collection_order=collected,hardware=hardware.hex(),timing=timing,key_during_active=key,speed=speed,fault=fault,sector_size=sector_size)
    if trace:
        replay=run(t,out,optimize,capacity,speed,bank,False,p,key,sector_size=sector_size)
        for field in ('runtime','observed','submission_order','collection_order','hardware'):require(result[field]==replay[field],'Observer changed '+field)
        result['replay']=dict(status='identical',xex_sha256=sha256(p['xex']),emulator_sha256=PIN['emulator']['sha256'])
    return result

def main():
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),default='opt');a.add_argument('--capacity',type=int,choices=(4,8),default=4)
    a.add_argument('--speed',type=int,choices=(0,1,2),default=0);a.add_argument('--bank',type=int,default=2);a.add_argument('--trace',action='store_true');a.add_argument('--key',action='store_true');a.add_argument('--fault',choices=('queued','timeout'));a.add_argument('--output',type=Path,default=ROOT/'build/sio-concurrent')
    a.add_argument('--sector-size',type=int,choices=(128,256),default=128)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result={'status':'running'}
    require(not(args.fault and args.trace),'Fault controls are separate from normal timing')
    try:result=run(compiler(ROOT/'build/actionc'),out,args.case=='opt',args.capacity,args.speed,args.bank,args.trace,key=args.key,fault=args.fault,sector_size=args.sector_size)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Concurrent SIO passed',args.case,args.capacity,args.speed,args.bank,flush=True)
if __name__=='__main__':main()
