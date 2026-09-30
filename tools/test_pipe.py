#!/usr/bin/env python3
"""D3 native pipe blocking, ownership, cancellation and failure checks."""
import argparse
import json
from pathlib import Path
from library_paths import read_source
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out,mode,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/pipe_stream.act'
    text=read_source(ROOT/'lib/dos/dospipe.act').replace('USE EXEC\n','USE EXEC\nUSE PIPEPROBE\n',1)
    text=text.replace('EXEC.AllocMem(', 'PIPEPROBE.Alloc(').replace('EXEC.AllocSignal($ff)', 'PIPEPROBE.Signal()')
    (out/'dospipe.act').write_text(text)
    p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc'),source,out,optimize=mode=='opt',
                                          tasks=True,task_capacity=8,console=True,dos_mounts=[])
    require(p['build']['source_sha256']==sha256(source), 'Stale pipe fixture')
    binary=ROOT/'build/shell-paced-bridge/AltirraBridgeServer';rom=ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(binary)==PIN['emulator']['sha256'] and sha256(rom)==PIN['rom']['sha256'],'Unpinned machine')
    with emulator(binary.parent,rom,out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,rom,PIN)
        runtime,_=execute(b,p,timeout=120,frame_limit=6000)
        require(data(b,p['image'],'completed',True)==[6], 'Missing pipe scenarios')
        ownership(b,p,out)
        checks=data(b,p['image'],'checks',True)
    return dict(status='pass',tier='development',mode=mode,checks=checks,build=p['build'],runtime=runtime,
                machine=machine,pin=PIN,bank_zero_delta=dict(fixed=0,per_task=0),
                fault_override_sha256=sha256(out/'dospipe.act'),
                source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in
                  (source,ROOT/'lib/dos/dospipe.act',ROOT/'tests/programs/pipeprobe.act',Path(__file__))})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    result=run(args.output.resolve(),args.case,args.reuse)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Pipe checks passed:',args.case,result['checks'])
