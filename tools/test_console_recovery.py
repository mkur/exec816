#!/usr/bin/env python3
"""Existing real serial recovery oracles with the configured console resident."""
import argparse,json
from pathlib import Path
import test_sio_recovery as recovery
from native_program import ROOT,build,compiler
from test_dos_stack import execute,ownership

def run(out,optimize,toolchain=None):
    # These cases do not spawn the old fixture's hardcoded blocker Tasks.
    # Keep its actual fault responder and all existing error/post/pointer checks.
    def configured(*args,**kwargs):return build(*args,**kwargs,console=True,task_capacity=8)
    recovery.build=configured;recovery.execute=execute;recovery.clean_ownership=ownership
    result=recovery.run(toolchain if toolchain is not None else compiler(ROOT/'build/actionc'),out,optimize,['checksum','device','short','firstcause','framing','protocol'])
    for case in result['cases']:
        assert case['runtime']['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0
    result['scope']='Existing checksum/device/short/first-cause/framing/protocol oracles with console startup; real D8 peripheral faults; no injected keyboard in these recovery cases. Console/heap retention on unsafe exit is independently checked by console-lifetime qualification.'
    return result
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(out,args.case=='opt')
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Console recovery passed',args.case,flush=True)
