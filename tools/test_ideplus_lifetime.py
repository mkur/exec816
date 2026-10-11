"""Focused cancellation, bounded faults, PBI NMI boundaries and mixed SIO I/O."""
import argparse
import json
from native_program import ROOT,build,compiler,execute,read_build,require
from test_ideplus import ide_emulator
from ideplus_media import pattern_fixture,put_sector
from generate_memory import PROFILE
from test_cooperative import data
from test_heap_api import clean_ownership
from stack_budget import stack_usage,bank_zero_delta
from os_boundary import run_to
import adapter_state as adapter


def reach(b,at,extra='1'):
    condition=f'(@xpc=${at:x})&({extra})'
    b.bp_set(at & 65535,condition=condition)
    return run_to(b,at & 65535,frame_limit=12000,timeout=180,condition=condition)


def routine(p,name):
    return next(r for r in p['image']['routines'] if r['name'].startswith('M_'+name+'_'))


def run(out,reuse=False,selected=None):
    out.mkdir(parents=True,exist_ok=True)
    profile=out/'profile.json'
    value=json.loads(PROFILE.read_text());value['image_data_bytes']=4096
    profile.write_text(json.dumps(value))
    mounts=[dict(alias='D1',unit=49,profile=4,sector_bytes=256,sectors=2000,format=1)]
    p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ideplus_lifetime.act',out,optimize=True,tasks=True,task_capacity=8,heap_probe=True,console_deferred=True,memory_profile=profile,dos_mounts=mounts,image_data=[(0x2dfff0,bytes([0x55])*512),(0x2e1000,bytes(128))])
    base=p['build']['memory']['ideplus_storage']['BASE']
    cases=['mixed','slots','allocation','busy-stop','timeout','flush-error']+[f'nmi-{i}' for i in range(1,8)]
    for name in cases:
        if selected and name not in selected:continue
        dest=out/name;dest.mkdir(exist_ok=True)
        media,maps=pattern_fixture(readonly=False);expected=bytearray(media)
        error={'timeout':2,'flush-error':3}.get(name,0)
        if name not in ('busy-stop','timeout'):
            put_sector(expected,maps[0]['start'],1,
                       bytes([0x55])*512 if error else bytes((i&255)^0x55 for i in range(512)))
        disk=dest/'ide.img';disk.write_bytes(media)
        sio=dest/'sio.atr';original=(ROOT/'tests/fixtures/filesystem-write/mydos-256.atr').read_bytes();sio.write_bytes(original)
        with ide_emulator(dest,disk,writable=True) as b:
            b.config('diskemu','generic56k')
            def before(b):
                b.mount(0,str(sio))
                for field,value in [('EXPECTEDERROR',error),('BLOCKED',name=='slots'),('ALLOCATION',name=='allocation'),('BUSYSTOP',name=='busy-stop'),('MIXED',name=='mixed')]:
                    at=next(d['address'] for d in p['image']['data'] if '_IDEPLUSLIFETIME_'+field+'_' in d['name'])
                    b.memload(at,bytes([value]))
                if name=='allocation':
                    reach(b,p['labels']['native_cop'],f'db(${base+768+3:x})=1')
                    at=p['labels']['heap_alloc_mem'];original=b.memdump(at,5)
                    b.memload(at,bytes.fromhex('a9 00 00 aa 6b'))
                    b.bp_clear_all()
                    reach(b,p['labels']['native_cop'],f'db(${base+768+3:x})=2')
                    b.memload(at,original)
                    b.bp_clear_all()
                if name.startswith('nmi-'):
                    point=int(name.split('-')[1]);at=p['labels'][f'ideplus_probe_{point}']
                    require(b.memdump(at,4)==b'\xea'*4,'Unexpected NMI checkpoint bytes')
                    b.memload(at,b'\x22'+p['labels']['ideplus_probe_wait'].to_bytes(3,'little'))
                if name=='flush-error':
                    b.memload(p['labels']['ideplus_probe_5'],b'\x22'+p['labels']['ideplus_probe_wait'].to_bytes(3,'little'))
                    reach(b,p['labels']['native_nmi'],f'db(${base+16+10:x})=3')
                    b.memload(base+640+21,b'\2')
                    b.bp_clear_all()
            try:
                runtime,_=execute(b,p,before_run=before,expected_status=4 if name=='busy-stop' else 0,timeout=180,frame_limit=12000)
            except Exception:
                print(name,'checks',data(b,p['image'],'checks',True),'progress',data(b,p['image'],'progress',True),flush=True)
                print('status',b.peek16(adapter.STATE),'regs',b.regs(),flush=True)
                print('bus',b.memdump(base+16,64).hex(),'controller',b.memdump(base+640,32).hex(),flush=True)
                raise
            if name!='busy-stop':clean_ownership(b,p,out)
            if name.startswith('nmi-'):require(b.peek16(base+768+4)==1,'No boundary VBI injected')
            stacks=stack_usage(b,p['build']['memory'])
            require(all(x['remaining_above_floor']>=0 for x in stacks.values()),'Stack reserve crossed')
            checks=data(b,p['image'],'checks',True);progress=data(b,p['image'],'progress',True)
        require(disk.read_bytes()==expected,'Unexpected media change')
        require(sio.read_bytes()==original,'Concurrent SIO read changed media')
        result=dict(status='pass',tier='development',case=name,build=p['build'],runtime=runtime,checks=checks,progress=progress,stacks=stacks,historical_bank_zero_delta=bank_zero_delta(p['build']['memory']),ide_driver_bank_zero_delta=dict(fixed=0,per_task=0,idle=0))
        (dest/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print('IDE lifetime passed',name,flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--reuse',action='store_true');a.add_argument('--case',action='append');a.add_argument('--output',type=__import__('pathlib').Path,default=ROOT/'build/development/ideplus-ip5')
    v=a.parse_args();run(v.output,v.reuse,v.case)
