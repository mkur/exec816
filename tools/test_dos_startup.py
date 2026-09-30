"""Declared single-expression startup failures in emitted native filesystem code."""
from library_paths import library_file, read_source
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,sha256,require
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership
from mydos_fixtures import Image
from banked_test_memory import write as far_write
# Each replacement removes exactly one resource acquisition; successful paths
# still use the production allocator and device. No diagnostic code is shipped.
FAILURES={
 'service':('fsboot','service=FSTYPES.Service POINTER(EXEC.AllocMem(SIZEOF(FSTYPES.Service),\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','service=FSTYPES.Service POINTER(0)',103),
 'admission':('fsboot','worker=DOSCORE.Control(1,BYTE POINTER(@FSWORKER.Worker))','worker=BYTE POINTER(0)',103),
 'adapter':('blockio','adapter=BLOCKTYPES.Adapter POINTER(EXEC.AllocMem(BLOCKTYPES.ADAPTER_SIZE,\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','adapter=BLOCKTYPES.Adapter POINTER(0)',103),
 'reply-port':('blockio','adapter.port=EXEC.CreateMsgPort()','adapter.port=EXEC.MsgPort POINTER(0)',103),
 'transfer':('blockio','adapter.request=EXEC.IOSIOReq POINTER(EXEC.CreateIORequest(adapter.port,\n        EXEC.IOSIOREQ_SIZE))','adapter.request=EXEC.IOSIOReq POINTER(0)',103),
 'buffer':('blockio','adapter.buffer=EXEC.AllocMem(256,EXEC.MEMF_UPPER)','adapter.buffer=BYTE POINTER(0)',103),
 'workspace':('fsinit','service.work=FSBTYPES.Workspace POINTER(EXEC.AllocMem(SIZEOF(\n      FSBTYPES.Workspace),EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','service.work=FSBTYPES.Workspace POINTER(0)',103),
 'operation':('fsinit','service.operation=FSBTYPES.Operation POINTER(EXEC.AllocMem(SIZEOF(\n      FSBTYPES.Operation),EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','service.operation=FSBTYPES.Operation POINTER(0)',103),
 'backend-volume':('mydos','volume.state=EXEC.AllocMem(SIZEOF(MYDOSTYPES.Volume),\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR)','volume.state=BYTE POINTER(0)',103),
 'sdfs-work':('sdfs','work.extra=EXEC.AllocMem(SIZEOF(SDFSTYPES.BackendState),EXEC.MEMF_UPPER\n      OR EXEC.MEMF_CLEAR)','work.extra=BYTE POINTER(0)',103),
 'sdfs-volume':('sdfs','volume.state=EXEC.AllocMem(SIZEOF(SDFSTYPES.Volume),EXEC.MEMF_UPPER\n      OR EXEC.MEMF_CLEAR)','volume.state=BYTE POINTER(0)',103),
 'arrival':('fsinit','service.arrival=EXEC.AllocSignal(-1)','service.arrival=255',103),
 'cancel-signal':('fsinit','registry.cancelSignal=EXEC.AllocSignal(-1)','registry.cancelSignal=255',103),
 'control-port':('fsinit','service.control=FSPORTS.Create(service.arrival)','service.control=EXEC.MsgPort POINTER(0)',103),
 'mount':('fsinit','mount=FSTYPES.Mount POINTER(EXEC.AllocMem(SIZEOF(FSTYPES.Mount),\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','mount=FSTYPES.Mount POINTER(0)',103),
 'parser-volume':('fsinit','mount.volume=FSBTYPES.Volume POINTER(EXEC.AllocMem(SIZEOF(FSBTYPES.Volume),\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','mount.volume=FSBTYPES.Volume POINTER(0)',103),
 'block-volume':('fsinit','block=BLOCKTYPES.Volume POINTER(EXEC.AllocMem(BLOCKTYPES.VOLUME_SIZE,\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','block=BLOCKTYPES.Volume POINTER(0)',103),
 'mount-port':('fsinit','mount.port=FSPORTS.Create(service.arrival)','mount.port=EXEC.MsgPort POINTER(0)',103),
 'owner':('blockio','volume.request=EXEC.IOSIOReq POINTER(EXEC.CreateIORequest(adapter.port,\n      EXEC.IOSIOREQ_SIZE))','volume.request=EXEC.IOSIOReq POINTER(0)',103),
 'device-open':('blockio','error=EXEC.OpenDevice(name,volume.unit,EXEC.IORequest POINTER(volume.request),0)','error=-1',-1),
}
SDFS_FAILURES=('sdfs-work','sdfs-volume')
VARIANTS=tuple(name for name in FAILURES if name not in SDFS_FAILURES)+('metadata-read','format','generation','duplicate-alias','duplicate-unit')
def run(t,out,mode,fault,filesystem='mydos'):
    out.mkdir(parents=True,exist_ok=True);overrides={};error=103
    if fault in FAILURES:
        module,old,new,error=FAILURES[fault];text=read_source(library_file(module+'.act'));require(text.count(old)==1,'Stale startup transform '+fault)
        p=out/f'{module}.act';p.write_text(text.replace(old,new));overrides[p.name]=sha256(p)
    if fault=='metadata-read':
        text=read_source(library_file('blockwire.act'))
        old='  error=INT(CARD(state))'
        require(text.count(old)==1,'Stale metadata completion hook')
        text=text.replace(old,old+'\n  IF error=0 THEN\n    request.io_Error=4\n    request.io_Actual=0\n    error=4\n  FI')
        p=out/'blockwire.act';p.write_text(text);overrides[p.name]=sha256(p);error=4
    fixture='sdfs/sdfs-21-128.atr' if filesystem=='sdfs' else 'mydos/mydos450-128.atr'
    disk=Image((ROOT/'tests/fixtures'/fixture).read_bytes())
    if fault=='format':
        if filesystem=='sdfs':disk=Image((ROOT/'tests/fixtures/mydos/mydos450-128.atr').read_bytes())
        else:disk.data[disk.offset(360)]=0
        error=225
    media=out/'volume.atr';media.write_bytes(disk.data);before=sha256(media)
    mounts=[dict(alias='D1',unit=49,sectors=2000 if filesystem=='sdfs' else 720,sector_bytes=128,format=2 if filesystem=='sdfs' else 1)]
    if fault.startswith('duplicate-'):
        mounts.append(dict(alias='D2',unit=50,sectors=720,sector_bytes=128));error=202
    p=build(t,ROOT/'tests/programs/dos_startup_fail.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,dos_mounts=mounts,image_data=[(0xd1000,b'D1:TOOLS/SUB/DATA.BIN\0')])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        def before_run(b):
            # Build valid production descriptors; corrupt the loaded test image
            # explicitly to exercise the independent native validation gate.
            config=p['build']['task_storage']['BASE']+0x900
            if fault=='duplicate-alias':far_write(b,config+44,b'd1'+bytes(30),out)
            if fault=='duplicate-unit':far_write(b,config+44+32,(49).to_bytes(2,'little'),out)
            for name,value,size in [('EXPECTED',error,4),('EXHAUSTED',int(fault=='generation'),1)]:
                address=next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_DOSFAILTEST_'+name+'_'));b.memload(address,(value&((1<<(size*8))-1)).to_bytes(size,'little'))
        try:runtime,_=execute(b,p,before_run=before_run,timeout=240,frame_limit=12000)
        except Exception:
            print('native state',b.memdump(0x2000,64).hex(),'checks',data(b,p['image'],'checks',True),flush=True)
            for i,pool in enumerate(p['build']['memory']['task_pools']):(out/f'fault-stack-{i}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            raise
        ownership(b,p,out);require(sha256(media)==before,'Media changed')
        return dict(status='pass',fault=fault,filesystem=filesystem,expected_error=error,overrides=overrides,build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True),media_sha256=before)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--format',choices=('mydos','sdfs'),default='mydos');g=a.add_mutually_exclusive_group(required=True);g.add_argument('--fault',choices=VARIANTS+SDFS_FAILURES);g.add_argument('--suite',help='Comma-separated acquisition faults, sharing one emitted image');g.add_argument('--config',action='store_true',help='Native descriptor validation using one image');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:
        if args.config:
            from fsinit_faults import config
            r=config(compiler(ROOT/'build/actionc'),out,args.case)
        elif args.suite:
            from fsinit_faults import run as suite
            r=suite(compiler(ROOT/'build/actionc'),out,args.case,args.suite.split(','),args.format,FAILURES)
        else:
            r=run(compiler(ROOT/'build/actionc'),out,args.case,args.fault,args.format)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS startup rollback passed',args.case,args.fault or 'selected suite',flush=True)
