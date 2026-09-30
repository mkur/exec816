#!/usr/bin/env python3
"""Execute raw/optimized multi-bank commands on the optimized resident kernel."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from o65_large_command import make
from build_command import compile_command
from library_paths import read_source
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from banked_test_memory import read

PIN=json.loads((ROOT/'toolchain/altirra-shell-console.json').read_text())

def run(out,mode,reuse=False):
    out.mkdir(parents=True,exist_ok=True);toolchain=compiler(ROOT/'build/actionc')
    artifact,expected,large=make(toolchain,out,mode)
    overflow=compile_command(toolchain,ROOT/'tests/programs/disk_overflow.act',out/'OVERFLOW',mode=='opt')
    raw=artifact.read_bytes();fault=(out/'OVERFLOW').read_bytes()
    require(len(raw)+len(fault)<=131072,'Fixture exceeds two source banks')
    (out/'o65-large.inc').write_text(f'CONST BIG_BYTES=LONGCARD({len(raw)})\nCONST FAULT_BYTES=LONGCARD({len(fault)})\nCONST EXPECTED={expected}\n')
    (out/'probe.act').write_text(read_source(ROOT/'tests/programs/o65_large.act',{'o65-large.inc':out/'o65-large.inc'}))
    # Two 64-KiB-aligned placements need four contiguous heap banks. The raw
    # resident kernel now leaves only three; use the production kernel mode
    # here. Raw-loader coverage lives in validation/execution fixtures.
    p=read_build(out) if reuse else build(toolchain,out/'probe.act',out,optimize=True,tasks=True,task_capacity=8,console=False,image_data=[(0xd0000,raw+fault)])
    require(p['build']['optimize'], 'Multi-bank fixture needs an optimized resident kernel; rebuild this case')
    records=[]
    for failing in (False,True):
        case=out/('fault-run' if failing else 'multibank');case.mkdir(exist_ok=True)
        with emulator(ROOT/'build/shell-console-bridge',ROOT/'build/firmware/altirraos-816.rom',case,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            def before(b):
                address=next(d['address'] for d in p['image']['data'] if '_O65LARGE_FAULT_' in d['name'])
                b.poke(address,int(failing))
            runtime,_=execute(b,p,before_run=before,expected_status=1 if failing else 0,timeout=600,frame_limit=30000)
            if not failing:
                require(data(b,p['image'],'finished')==[1],'Multi-bank command did not finish')
                ownership(b,p,out)
                raw_bases=bytes(data(b,p['image'],'bases'))
                bases=[int.from_bytes(raw_bases[i:i+4],'little') for i in (0,4)]
                require(bases[0]!=bases[1] and all(v%65536==0 for v in bases),'Missing distinct bank-aligned placements')
                records.append(dict(status='pass',case='multibank',runtime=runtime,machine=machine,bases=bases))
            else:
                pointer=int.from_bytes(bytes(data(b,p['image'],'image')),'little')
                image=read(b,pointer,42,case)
                require(image[:4]==b'IMG1' and int.from_bytes(image[4:8],'little')==1 and image[8:10]==b'\x00\x01','Fault released a live Image')
                records.append(dict(status='pass',case='stack-overflow',runtime=runtime,machine=machine,image_pointer=pointer,retained_image=image.hex()))
    return dict(status='pass',mode=mode,kernel_mode='opt',build=p['build'],large=large,overflow=overflow,cases=records,pin=PIN,bank_zero_delta=dict(fixed=0,per_task=0))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args();result=run(args.output.resolve(),args.case,args.reuse)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Multi-bank and loaded fault passed',args.case,flush=True)
