"""Native lock/FIB packets over actual SIO and declared damaged media copies."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,sha256,require
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership
from mydos_fixtures import Image

def run(t,out,mode,size,variant='normal'):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr';disk=Image(source.read_bytes())
    manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text())
    volume=next(v for v in manifest['volumes'] if v['sector_bytes']==size)
    require(sha256(source)==volume['sha256'],'Unpinned original media')
    rows=[e for e in volume['entries'] if e['parent']==361]
    rows+= [dict(name='D1',flags=16,count=8,parent=0,path='')]
    rows+= [next(e for e in volume['entries'] if e['path']==n) for n in ('TOOLS/SUB','TOOLS/SUB/DATA.BIN')]
    lengths={f['path']:f['bytes'] for f in volume['files']};oracle=bytearray()
    for e in rows:
        kind=(1 if e['parent']==0 else 2) if e['flags']&16 else -3
        oracle+=struct.pack('<14s4i2x',e['name'].encode(),kind,lengths.get(e['path'],0),e['count'],5 if e['flags']&32 else 0)
    index={'normal':0,'empty':1,'name':2,'chain':3}[variant]
    if variant=='empty':
        at=disk.offset(next(e for e in rows if e['path']=='TOOLS/SUB')['start']);disk.data[at:at+disk.size]=bytes(disk.size)
    if variant=='name':
        e=rows[8];at=disk.offset(e['parent']+e['ordinal']//8)+(e['ordinal']%8)*16;disk.data[at+5]=33
    if variant=='chain':
        e=rows[8];at=disk.offset(e['start'])+disk.size-3
        high=e['start']>>8 if e['flags']&4 else (e['ordinal']<<2)|(e['start']>>8)
        disk.data[at:at+2]=bytes((high,e['start']&255))
    media=out/'volume.atr';media.write_bytes(disk.data);before=sha256(media)
    paths=bytearray(128)
    for at,path in enumerate(('D1:','D1:TOOLS','D1:TOOLS/SUB','D1:TOOLS/SUB/DATA.BIN')):
        value=path.encode()+b'\0';paths[at*32:at*32+len(value)]=value
    p=build(t,ROOT/'tests/programs/dos_directories.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,
        dos_mounts=[dict(alias='D1',unit=49,sectors=disk.count,sector_bytes=size)],
        image_data=[(0xd1000,bytes(paths)),(0xcffd0,bytes([165])*32+bytes(260)+bytes([165])*32),(0xd0200,bytes(260)),(0xd0400,bytes(260)),(0xe0000,bytes(260)),(0xe4000,bytes(oracle))])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        def before_run(b):b.poke(next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_DOSDIRTEST_VARIANT_')),index)
        try:runtime,_=execute(b,p,before_run=before_run,timeout=3600 if size==256 else 600,frame_limit=30000)
        except Exception:
            print('native state',b.memdump(0x2000,64).hex(),flush=True)
            print('checks',data(b,p['image'],'checks',True),'other checks',data(b,p['image'],'otherChecks',True),flush=True)
            for i,pool in enumerate(p['build']['memory']['task_pools']):(out/f'fault-stack-{i}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            raise
        ownership(b,p,out)
        from banked_test_memory import read
        require(read(b,0xcffd0,32,out)==bytes([165])*32 and read(b,0xcfff0+260,32,out)==bytes([165])*32,'FIB canary damage')
        require(sha256(media)==before,'Media changed')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True),other_checks=data(b,p['image'],'otherChecks',True),sector_bytes=size,variant=variant,media_sha256=before,original_sha256=volume['sha256'],oracle=rows,expected_sizes=lengths,oracle_sha256=__import__('hashlib').sha256(oracle).hexdigest())
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--size',type=int,choices=(128,256),required=True);a.add_argument('--variant',choices=('normal','empty','name','chain'),default='normal');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case,args.size,args.variant)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS directories passed',args.case,args.size,args.variant,flush=True)
