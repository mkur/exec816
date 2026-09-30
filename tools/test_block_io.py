#!/usr/bin/env python3
"""Checked sectors through the canonical adapter, with real or fixture bytes."""
from library_paths import read_source
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,verify_machine,sha256
from os_boundary import emulator
from sector_images import disk_image
from test_sio_device import PIN
from test_cooperative import data
from banked_test_memory import read as far_read
from test_heap_api import clean_ownership

DRIVER=ROOT/'tests/fixtures/block/driver.inc'

def run(t,out,optimize,backend='sio'):
    out.mkdir(parents=True,exist_ok=True)
    override=None
    shutil.copyfile(ROOT/'tests/programs/block-test-state.inc',out/'block-test-state.inc')
    if backend=='fixture':
        shutil.copyfile(ROOT/'tests/fixtures/block/blockwire.act',out/'blockwire.act');override=sha256(out/'blockwire.act')
    p=build(t,ROOT/'tests/programs/block_io.act',out,optimize=optimize,tasks=True,
        image_data=[(0xaffd0,bytes([0xa5])*320),(0xe0000,bytes(16))])
    disks=[]
    if backend=='sio':
        for unit,size,count in ((0,128,720),(1,256,65535)):
            disk=out/f'disk{unit}.atr';disk_image(disk,size,count);disks.append((disk,sha256(disk)))
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in {**PIN['configuration'],'diskemu':'fastest'}.items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            for unit,(disk,_) in enumerate(disks):b.mount(unit,str(disk))
            if backend=='fixture':b.poke(next(d['address'] for d in p['image']['data'] if '_FAKE_' in d['name']),1)
        try:runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
        except Exception:
            print('checks',data(b,p['image'],'checks',True),'phase',data(b,p['image'],'phase'),
                  'cache facts',data(b,p['image'],'cacheFacts',True),flush=True);raise
        clean_ownership(b,p,out)
        buf=far_read(b,0xaffd0,320,out)
        require(buf[:32]==buf[-32:]==bytes([0xa5])*32,'Block buffer guard changed')
        hardware=far_read(b,p['build']['task_storage']['BASE']+0x800,128,out)
        require(int.from_bytes(hardware[56:58],'little')==(10 if backend=='sio' else 0),'Unexpected wire command count')
        for disk,digest in disks:require(sha256(disk)==digest,'Read modified media')
        return dict(status='pass',backend=backend,override_sha256=override,block_driver_sha256=sha256(DRIVER),build=p['build'],runtime=runtime,machine=machine,
            checks=data(b,p['image'],'checks',True),hardware=hardware.hex(),media={d.name:h for d,h in disks})
def allocation(t,out,optimize,fault):
    out.mkdir(parents=True,exist_ok=True)
    module='blockcache.act' if fault in ('cache-payload','cache-tags') else 'blockio.act'
    if fault=='volume':module='driver.inc'
    text=read_source(DRIVER if fault=='volume' else ROOT/'lib/io'/module)
    replacements={
        'adapter':('adapter=BLOCKTYPES.Adapter POINTER(EXEC.AllocMem(BLOCKTYPES.ADAPTER_SIZE,\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','adapter=BLOCKTYPES.Adapter POINTER(0)'),
        'port':('adapter.port=EXEC.CreateMsgPort()','adapter.port=EXEC.MsgPort POINTER(0)'),
        'transfer':('adapter.request=EXEC.IOSIOReq POINTER(EXEC.CreateIORequest(adapter.port,\n        EXEC.IOSIOREQ_SIZE))','adapter.request=EXEC.IOSIOReq POINTER(0)'),
        'buffer':('adapter.buffer=EXEC.AllocMem(256,EXEC.MEMF_UPPER)','adapter.buffer=BYTE POINTER(0)'),
        'volume':('LET volume=BLOCKTYPES.Volume POINTER(EXEC.AllocMem(\n      BLOCKTYPES.VOLUME_SIZE,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))','LET volume=BLOCKTYPES.Volume POINTER(0)'),
        'owner':('volume.request=EXEC.IOSIOReq POINTER(EXEC.CreateIORequest(adapter.port,\n      EXEC.IOSIOREQ_SIZE))','volume.request=EXEC.IOSIOReq POINTER(0)'),
        'open':('error=EXEC.OpenDevice(name,volume.unit,EXEC.IORequest POINTER(volume.request),0)','error=-1'),
        'cache-payload':('cache.payload=EXEC.AllocMem(payloadBytes,EXEC.MEMF_UPPER OR EXEC.MEMF_LINEAR)', 'cache.payload=NULL'),
        'cache-tags':('cache.tags=BLOCKTYPES.CacheTag POINTER(EXEC.AllocMem(\n      MetadataBytes(blocks),EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))', 'cache.tags=NULL'),
    }
    old,new=replacements[fault];require(text.count(old)==1,'Stale block allocation transform')
    (out/module).write_text(text.replace(old,new))
    source=ROOT/'tests/programs/block_allocation.act'
    if fault=='volume':
        (out/'block_allocation.act').write_text(read_source(source,{'driver.inc':out/module}))
        source=out/'block_allocation.act'
    p=build(t,source,out,optimize=optimize,tasks=True)
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            if fault in ('volume','owner','open'):b.poke(next(d['address'] for d in p['image']['data'] if '_VARIANT_' in d['name']),1)
            if fault in ('cache-payload','cache-tags'):b.poke(next(d['address'] for d in p['image']['data'] if '_VARIANT_' in d['name']),2)
        runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
        clean_ownership(b,p,out)
        return dict(status='pass',fault=fault,build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True),override_sha256=sha256(out/module),block_driver_sha256=sha256(DRIVER))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--fault',choices=('adapter','port','transfer','buffer','volume','owner','open','cache-payload','cache-tags'));a.add_argument('--backend',choices=('sio','fixture'),default='sio');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:
        t=compiler(ROOT/'build/actionc')
        result=allocation(t,out,args.case=='opt',args.fault) if args.fault else run(t,out,args.case=='opt',args.backend)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Block adapter passed',args.case,args.backend,flush=True)
