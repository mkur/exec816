"""Raw/optimized bounded IDE writes, with complete-media and guard oracles."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,read_build,require
from test_ideplus import ide_emulator
from test_ideplus_write import observe_readbacks
from ideplus_media import pattern_fixture,put_sector
from test_cooperative import data
from test_heap_api import clean_ownership
from os_boundary import run_to
import adapter_state

def adapter_ranges(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),
        ROOT/'tests/programs/ideplus_read_adapter.act',out,optimize=True,
        tasks=True,task_capacity=8)
    original,_=pattern_fixture();disk=out/'ide.img';disk.write_bytes(original)
    with ide_emulator(out,disk) as b:
        try:runtime,_=execute(b,p,timeout=120,frame_limit=6000)
        except Exception:
            print('adapter checks',data(b,p['image'],'checks',True),'phase',data(b,p['image'],'phase',True),flush=True);raise
        clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
    require(disk.read_bytes()==original,'Adapter read changed media')
    (out/'results.json').write_text(json.dumps(dict(status='pass',tier='development',build=p['build'],runtime=runtime,checks=checks),indent=2)+'\n')
    print('IDE read adapter passed',flush=True)

def read_ranges(out,mode,reuse=False,selected=None):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),
        ROOT/'tests/programs/ideplus_read_ranges.act',out,optimize=mode=='opt',
        tasks=True,task_capacity=8,heap_probe=True,
        image_data=[(0x2dffef,bytes([0xa5])*2050)])
    for name in ('read','mid-read','terminal-read'):
        if selected and name not in selected:continue
        dest=out/name;dest.mkdir(exist_ok=True)
        original,maps=pattern_fixture();disk=dest/'ide.img';disk.write_bytes(original)
        injected=name!='read';spans=3 if name=='mid-read' else 4
        with ide_emulator(dest,disk) as b:
            def before(b):
                at=next(d['address'] for d in p['image']['data'] if '_EXPECTEDERROR_' in d['name'])
                b.memload(at,bytes([3 if injected else 0]))
                if injected:
                    address=0x2dfff0+(spans-1)*512
                    cases=[]
                    for slot,pool in enumerate(p['build']['memory']['task_pools']):
                        ptr=pool['dp']+0x80
                        cases.append(f'((db(${adapter_state.CURRENT:x})={slot})&(dw(${ptr:x})=${address&65535:x})&(db(${ptr+2:x})=${address>>16:x}))')
                    marker=adapter_state.TEST_RELOCATION_SENTINEL+128
                    point=p['labels']['ideplus_probe_4']
                    require(b.memdump(point,4)==b'\xea'*4,'Changed read checkpoint')
                    b.memload(marker,bytes.fromhex('ea 6b'))
                    b.memload(point,b'\x22'+marker.to_bytes(3,'little'))
                    condition='('+'|'.join(cases)+')'
                    b.bp_set(marker,condition=condition)
                    run_to(b,marker,frame_limit=3000,timeout=30,condition=condition)
                    ready=next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_IDEPLUSDRIVER_READY_'))
                    b.memload(ready,bytes.fromhex('a9 03 00 6b'))
                    b.memload(point,b'\xea'*4);b.bp_clear_all()
            try:runtime,_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
            except Exception:
                print(name,'checks',data(b,p['image'],'checks',True),flush=True);raise
            clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
            if injected:
                actual=b.memdump(0x2dfff0,2048)
                from ideplus_media import get_sector
                wanted=b''.join(get_sector(original,maps[0]['start'],i) for i in range(spans))+bytes([0xa5])*(2048-spans*512)
                require(actual==wanted,'Failed range changed unexpected destination bytes')
        require(disk.read_bytes()==original,'Read range changed media')
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',mode=mode,build=p['build'],runtime=runtime,checks=checks,completed_pio_spans=spans if injected else None),indent=2)+'\n')
        print('IDE read range passed',mode,name,flush=True)

def run(out,mode,reuse=False,selected=None):
    out.mkdir(parents=True,exist_ok=True)
    if reuse:
        p=read_build(out)
    else:
        observe_readbacks(out)
        source=out/'ideplus_ranges.act'
        source.write_text((ROOT/'tests/programs/ideplus_ranges.act').read_text())
        p=build(compiler(ROOT/'build/actionc',release=True),source,out,
                optimize=mode=='opt',tasks=True,task_capacity=8,heap_probe=True,
                image_data=[(0x2dffef,bytes([0xa5])*2050)])
    require(p['build']['optimize']==(mode=='opt'),'Wrong range NIR mode')
    for name,protected,failed in (('writable',False,False),('protected',True,False),('failed',False,True),('mid-range',False,False)):
        if selected and name not in selected:continue
        injected=name=='mid-range'
        dest=out/name;dest.mkdir(exist_ok=True)
        original,maps=pattern_fixture(readonly=protected);expected=bytearray(original)
        disk=dest/'ide.img';disk.write_bytes(original)
        if not protected and not failed and not injected:
            for sector in range(4):
                payload=bytes((i^(i>>8)^0x93)&255 for i in range(sector*512,(sector+1)*512))
                put_sector(expected,maps[0]['start'],sector,payload)
        with ide_emulator(dest,disk,writable=not failed) as bridge:
            def before(b):
                for field,value in (('PROTECTED',protected),('EXPECTEDERROR',3 if failed or injected else 0)):
                    at=next(d['address'] for d in p['image']['data'] if '_IDEPLUSRANGES_'+field+'_' in d['name'])
                    b.memload(at,bytes([value]))
                if injected:
                    # At the third completed PIO span, DP $80 contains its
                    # source. Qualify against the current Task's fixed DP pool;
                    # the bridge does not expose full native D/S registers.
                    cases=[]
                    for slot,pool in enumerate(p['build']['memory']['task_pools']):
                        ptr=pool['dp']+0x80
                        cases.append(f'((db(${adapter_state.CURRENT:x})={slot})&(dw(${ptr:x})=$03f0)&(db(${ptr+2:x})=$2e))')
                    # The bridge sets bank-zero breakpoints only. Borrow two
                    # bytes of existing test scratch for a register-neutral
                    # native rendezvous at the existing four-NOP PIO checkpoint.
                    marker=adapter_state.TEST_RELOCATION_SENTINEL+128
                    point=p['labels']['ideplus_probe_5']
                    require(b.memdump(point,4)==b'\xea'*4,'Changed PIO checkpoint')
                    b.memload(marker,bytes.fromhex('ea 6b'))
                    b.memload(point,b'\x22'+marker.to_bytes(3,'little'))
                    condition='('+'|'.join(cases)+')'
                    b.bp_set(marker,condition=condition)
                    run_to(b,marker,frame_limit=3000,timeout=20,condition=condition)
                    ready=next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_IDEPLUSDRIVER_READY_'))
                    # Test-only ATA failure before the fourth payload. No frame
                    # was entered: return the normal BYTE result in native A16.
                    b.memload(ready,bytes.fromhex('a9 03 00 6b'))
                    b.memload(point,b'\xea'*4)
                    b.bp_clear_all()
            try:runtime,_=execute(bridge,p,before_run=before,timeout=120,frame_limit=6000)
            except Exception:
                print(name,'checks',data(bridge,p['image'],'checks',True),flush=True);raise
            clean_ownership(bridge,p,out)
            checks=data(bridge,p['image'],'checks',True)
        require(disk.read_bytes()==expected,'Range changed wrong physical bytes or neighbours')
        # The pinned ATA model buffers the entire command before host commit.
        # Mid-range PIO failure therefore leaves this image unchanged; real
        # media may have a partial mutation, which the ABI does not roll back.
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',mode=mode,build=p['build'],runtime=runtime,checks=checks,injected_after_pio_sectors=3 if injected else None,persisted_sectors_on_injected_failure=0 if injected else None),indent=2)+'\n')
        print('IDE range passed',mode,name,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--reads',action='store_true')
    parser.add_argument('--adapter',action='store_true')
    parser.add_argument('--case',action='append',choices=('writable','protected','failed','mid-range','read','mid-read','terminal-read'))
    args=parser.parse_args()
    if args.adapter:adapter_ranges(args.output,args.reuse)
    else:(read_ranges if args.reads else run)(args.output,args.mode,args.reuse,args.case)
