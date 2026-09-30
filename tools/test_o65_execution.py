#!/usr/bin/env python3
"""Native relocation, checked providers and retained Process image lifetime."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from library_paths import read_source
from build_command import compile_command
from o65_fixtures import inspect
from o65_oracle import build_oracle, reference
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from banked_test_memory import read

PIN = json.loads((ROOT/'toolchain/altirra-shell-console.json').read_text())


def run(out, mode, bank):
    out.mkdir(parents=True,exist_ok=True)
    toolchain = compiler(ROOT/'build/actionc')
    artifact = out/'command.o65'
    command_build = compile_command(toolchain,ROOT/'tests/programs/loaded_command.act',artifact,mode=='opt')
    raw = artifact.read_bytes()
    info = inspect(raw)
    ordinary = 1
    file_base = 0x10000 if bank==3 else 0xe0000
    snapshot_base = file_base+0x8000
    (out/'o65-execution-fixture.inc').write_text(f'CONST FILE_BASE=${file_base:x}\nCONST SNAPSHOT_BASE=${snapshot_base:x}\nCONST FIXTURE_BYTES={len(raw)}\nCONST PROVIDER_SIGNATURE={info["positions"][f"import{ordinary}.signature"]}\n')
    source = read_source(ROOT/'lib/dos/o65memory.act').replace('USE EXEC\n','USE EXEC\nUSE O65CONTROL\n')
    source = source.replace('RETURN(EXEC.AllocMem', '  O65CONTROL.allocations==+1\n'
                            '  IF O65CONTROL.failAt<>0 AND O65CONTROL.allocations=O65CONTROL.failAt THEN RETURN(BYTE POINTER(0)) FI\nRETURN(EXEC.AllocMem')
    (out/'o65memory.act').write_text(source)
    (out/'o65control.act').write_text((ROOT/'tests/programs/o65control.act').read_text())
    fixture = out/'probe.act'
    fixture.write_text(read_source(ROOT/'tests/programs/o65_execution.act',{'o65-execution-fixture.inc':out/'o65-execution-fixture.inc'}))
    program = build(toolchain,fixture,out,optimize=mode=='opt',tasks=True,task_capacity=8,
                    console=False,kernel_bank=bank,image_data=[(file_base,raw),(snapshot_base,bytes(16384))])
    provider_manifest = json.loads((out/'providers.json').read_text())
    selected = [next(p for p in provider_manifest['providers'] if p['name']==name) for name in info['imports']]
    oracle = build_oracle(toolchain)
    with emulator(ROOT/'build/shell-console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as bridge:
        machine = verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:
            runtime,_ = execute(bridge,program,timeout=240,frame_limit=12000)
        except Exception:
            print({name:data(bridge,program['image'],name) for name in ('checks','iteration','firstId','secondId')},flush=True)
            raise
        ownership(bridge,program,out)
        provider_checks = data(bridge,program['image'],'providerChecks',True)[0]
        require(provider_checks == 17, 'Incomplete provider matching regressions')
        encoded = bytes(data(bridge,program['image'],'bases'))
        placements = []
        for variant in range(2):
            bases = [int.from_bytes(encoded[i:i+4],'little') for i in range(variant*12,variant*12+12,4)]
            placement = dict(bases=bases,allowed=[dict(address=65536,size=0xff0000)],reserved=[],nmi_extra_stack=0,providers=selected)
            expected = reference(oracle,artifact,placement=placement)
            require('error' not in expected,'Reference placement failed: '+str(expected))
            payload = bytearray()
            for i in range(2):
                section = bytearray(info['sections'][i][1])
                for segment in expected['segments']:
                    if bases[i] <= segment['address'] < bases[i]+len(section):
                        start = segment['address']-bases[i]
                        section[start:start+len(segment['bytes'])] = bytes(segment['bytes'])
                payload += section
            payload += bytes(info['sections'][2][1])
            require(read(bridge,snapshot_base+variant*8192,len(payload),out)==payload,'Native relocation differs from Rust oracle')
            placements.append(placement)
        require(placements[0]['bases'][0]!=placements[1]['bases'][0],'Missing distinct text placements')
        return dict(status='pass',mode=mode,kernel_bank=bank,build=program['build'],machine=machine,
                    runtime=runtime,checks=int.from_bytes(bytes(data(bridge,program['image'],'checks')),'little'),
                    provider_checks=provider_checks,
                    command_build=command_build,placements=placements,allocation_failures=6,
                    native_processes=6,override_sha256=sha256(out/'o65memory.act'),bank_zero_delta=dict(fixed=0,per_task=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--kernel-bank',type=int,default=1)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out,args.case,args.kernel_bank)
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('o65 execution passed',args.case,result['checks'],flush=True)
