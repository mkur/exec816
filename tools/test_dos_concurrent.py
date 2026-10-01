"""Concurrent read-only MyDOS over the real queued SIO device."""
import adapter_state as adapter
import argparse,json,os,shutil,time
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,sha256,require
from os_boundary import emulator,run_to
from test_sio_device import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from banked_test_memory import read

def run(t,out,mode,size,capacity=8,bank=1,speed=0,trace=False,program=None,key=False):
    out.mkdir(parents=True,exist_ok=True)
    mounts=[dict(alias='D'+str(i+1),unit=49+i,sectors=720 if size==128 else 2000,sector_bytes=size,profile=1 if speed==0 else 2) for i in range(2)]
    paths=bytearray(224)
    names=('D1:TOOLS/SUB/DATA.BIN','D2:TOOLS/SUB/DATA.BIN','D1:LARGE.BIN','D1:TOOLS/SUB','D2:TOOLS/SUB','D1:','DATA.BIN')
    for i,name in enumerate(names):paths[32*i:32*i+len(name)+1]=name.encode()+b'\0'
    p=program or build(t,ROOT/'tests/programs/dos_concurrent.act',out,tasks=True,task_capacity=capacity,kernel_bank=bank,optimize=mode=='opt',dos_mounts=mounts,image_data=[(0xd0000,bytes(2048)),(0xd1000,bytes(paths))])
    machineout=out/('observed' if trace else 'replay');machineout.mkdir(exist_ok=True)
    images=[]
    for unit in range(2):
        media=machineout/f'volume{unit}.atr';shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',media);images.append((media,sha256(media)))
    for k in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(k,None)
    # Observe only boundaries consumed by the oracle. Unused instruction
    # markers make the long-file observer unnecessarily expensive on the host.
    marks={k:p['labels'][k] for k in ('sio_start','sio_shutdown','sio_retire','sio_alarm','sio_watchdog','signal_post','tasks_forbid','tasks_permit')}
    marks['root_dp']=p['build']['memory']['task_pools'][0]['dp']
    marks.update({r['name']:r['address'] for r in p['image']['routines'] if r['name'].startswith('M_DOSCONCURRENT_BACKGROUND_')})
    if trace:
        from dos_concurrent_trace import packet_marks
        marks.update(packet_marks(p))
        os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k,v in marks.items() if k!='root_dp'))
    binary=ROOT/('build/altirra-sio-multi-observer' if trace else 'build/altirra-sio-multi')
    require(sha256(binary/'AltirraBridgeServer')==(PIN['observer']['binary_sha256'] if trace else PIN['emulator']['sha256']),'Unpinned emulator')
    with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',machineout,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest' if speed==0 else '810')
        for i,(media,_) in enumerate(images):b.mount(i,str(media))
        def before(b):
            for name,value,n in [('SECTORSIZE',size,2),('LIVEADDRESS',p['build']['task_storage']['LIVE'],4)]:
                at=next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_DOSCONCURRENT_'+name+'_'));b.memload(at,value.to_bytes(n,'little'))
            if trace:b.profile_start()
            if key:
                at=next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_DOSCONCURRENT_ACTIVEMIRROR_'));condition=f'db(${at:x})=1'
                b.bp_set(p['labels']['native_irq'],condition=condition);run_to(b,p['labels']['native_irq'],frame_limit=30000,timeout=600,condition=condition);b.key('A');b.bp_clear_all()
        # At most 1200 full sectors in the DD workload, 512 SD. Allow the
        # device's 1/2s active cap plus 0.3s preparation/recovery per sector and
        # 60s finite CPU/setup margin. Host and guest limits remain distinct.
        sectors_bound=1200 if size==256 else 512
        guest_seconds=int(sectors_bound*((2 if speed else 1)+0.3)+60)
        host_seconds=7200 if size==256 else 3600
        original_regs=b.regs;next_report=[time.monotonic()+60]
        def monitored_regs():
            regs=original_regs()
            if time.monotonic()>=next_report[0]:
                print('Progress',mode,size,capacity,bank,{n:data(b,p['image'],n,True) for n in ('checks','workRounds','clientsDone')},'PC',regs['PC'],'clients',[[b.eval_expr(f'db(${0xd0400+i*128+j:x})') for j in (22,23,24,25)] for i in range(capacity-3)],flush=True)
                next_report[0]=time.monotonic()+60
            return regs
        b.regs=monitored_regs
        try:runtime,_=execute(b,p,before_run=before,timeout=host_seconds,frame_limit=guest_seconds*50)
        except Exception:
            print('native state',b.memdump(adapter.STATE,64).hex(),flush=True)
            print('counters',{n:data(b,p['image'],n,True) for n in ('checks','workRounds','clientsDone')},flush=True)
            for i,pool in enumerate(p['build']['memory']['task_pools']):(out/f'fault-stack-{i}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            raise
        finally:b.regs=original_regs
        if trace:b.profile_stop()
        observed={n:data(b,p['image'],n,True)[0] for n in ('checks','peakTasks','workRounds','activeWork','heapRounds','portRounds','signalRounds','clientsDone')}
        observed['totalBytes']=int.from_bytes(bytes(data(b,p['image'],'totalBytes')),'little')
        require(observed['peakTasks']==capacity and observed['clientsDone']==capacity-3 and observed['activeWork']>0,'Missing simultaneous workload/progress')
        expected_bytes=(capacity-3)*(777+24)+(70003-777 if size==256 else 0)
        require(observed['totalBytes']==expected_bytes,'Incorrect complete-file byte count')
        ownership(b,p,out);hardware=read(b,p['build']['task_storage']['BASE']+0x800,128,out)
        require(hardware[0]==hardware[1]==hardware[45]==0 and hardware[12:15]==hardware[16:19]==bytes(3),'Bus ownership retained')
        require(all(sha256(path)==old for path,old in images),'Media modified')
        posts=int.from_bytes(hardware[56:58],'little');require(0<posts<=sectors_bound,'Workload exceeded sector bound')
        require(runtime['native_nmi_count']>0 and runtime['vbi_dispatches']>0,'Missing retained VBI scheduling')
        (out/('observed-functional.json' if trace else 'functional.json')).write_text(json.dumps(dict(build=p['build'],runtime=runtime,observed=observed,hardware=hardware.hex(),marks=marks),indent=2)+'\n')
        timing=None
        if trace:
            from dos_concurrent_trace import analyze
            timing=analyze(machineout/'emulator.log',marks,[v[0] for v in images],size,speed,posts,observed['totalBytes'],guest_seconds)
            require(timing['packets']['count']==21*(capacity-3)+2 and len(timing['packets']['caller_dps'])==capacity-2,'Missing caller/packet trace')
            (out/'timing.json').write_text(json.dumps(timing,indent=2)+'\n');require(timing['verdict']=='pass','DOS timing failed: '+str(timing['violations']))
        result=dict(status='pass',build=p['build'],runtime=runtime,machine=machine,observed=observed,capacity=capacity,kernel_bank=bank,sector_bytes=size,speed=speed,key_during_active=key,hardware=hardware.hex(),wire_commands=posts,media=[v for _,v in images],timing=timing,marks=marks,limits=dict(host_seconds=host_seconds,guest_seconds=guest_seconds,sectors=sectors_bound))
    if trace:
        replay=run(t,out,mode,size,capacity,bank,speed,False,p,key)
        for field in ('runtime','observed','hardware'):require(result[field]==replay[field],'Observer changed '+field)
        result['replay']=dict(status='identical',xex_sha256=sha256(p['xex']),emulator_sha256=PIN['emulator']['sha256'])
    return result
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--size',type=int,choices=(128,256),required=True);a.add_argument('--capacity',type=int,choices=(4,8),default=8);a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--speed',type=int,choices=(0,1),default=0);a.add_argument('--trace',action='store_true');a.add_argument('--key',action='store_true');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    require(not(args.speed and args.size!=128),'Stock profile is 128 only')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case,args.size,args.capacity,args.bank,args.speed,args.trace,key=args.key)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Concurrent DOS passed',args.case,args.size,args.capacity,args.bank,flush=True)
