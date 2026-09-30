#!/usr/bin/env python3
"""Run three DOS fixture tasks in the eight-slot profile and inspect stack use."""
import argparse,json
from pathlib import Path
import test_dos_client as fixture
from native_program import ROOT,compiler,require
original_build=fixture.build
original_execute=fixture.execute

def build(*args,**kwargs):return original_build(*args,**kwargs,task_capacity=8)
def execute(b,p,**kwargs):
    snapshots=[];kernel_snapshot=[];original_dump=b.memdump
    def dump(address,size):
        # execute reads STATUS immediately at the completion breakpoint, before
        # its far-memory helper reuses retired bank-zero stack space.
        if address==0x2000 and size==64 and not snapshots:
            for pool in p['build']['memory']['task_pools']:
                snapshots.append(original_dump(pool['stack_base'],pool.get('stack_bytes',1536)))
            low,high=p['build']['memory']['regions']['kernel-stack']
            kernel_snapshot.append(original_dump(low+16,high-low-32))
        return original_dump(address,size)
    b.memdump=dump
    try:runtime,state=original_execute(b,p,**kwargs)
    finally:b.memdump=original_dump
    require(len(snapshots)==len(p['build']['memory']['task_pools']),'Missing pre-helper stack snapshot')
    observed=[]
    for slot,(pool,raw) in enumerate(zip(p['build']['memory']['task_pools'],snapshots)):
        size=pool.get('stack_bytes',1536)
        touched=next((i for i,v in enumerate(raw) if v!=0xa5),size)
        require(touched>=256,'Touched reserved interrupt headroom in slot '+str(slot))
        observed.append(dict(slot=slot,reserved_bytes=size,touched_bytes=size-touched,untouched_above_floor=touched-256))
    runtime['stack_observations']=observed
    raw=kernel_snapshot[0];first=next((i for i,v in enumerate(raw) if v!=0xa5),len(raw))
    runtime['kernel_stack_observation']=dict(reserved_bytes=len(raw),touched_bytes=len(raw)-first,untouched_from_base=first,interrupt_reserve_bytes_touched=max(0,256-first))
    return runtime,state

def ownership(b,p,out):
    from banked_test_memory import read
    c=p['build']['memory']['constants'];seed=(out/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    require(read(b,c['TABLE'],c['TABLE_BYTES'],out)==seed,'Eight-slot ownership mismatch')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    fixture.build=build;fixture.execute=execute;fixture.clean_ownership=ownership
    result={'status':'running'}
    try:
        result=fixture.run(compiler(ROOT/'build/actionc'),out,args.case=='opt')
        result['scope']='Three live tasks using the eight-slot stack sizes; touched-byte watermark is a lower bound on reserved stack depth; native frame/domain guards also checked'
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Eight-slot DOS stack probe passed',args.case,result['runtime']['stack_observations'],flush=True)
