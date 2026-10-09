#!/usr/bin/env python3
"""Execute upper-bank ownership operations at both qualified kernel origins."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,platform_files,require,verify_machine
from os_boundary import emulator
from test_banked import PIN
from test_cooperative import data
from banked_test_memory import read


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir',type=Path,required=True)
    p.add_argument('--bridge-dir',type=Path,required=True)
    p.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--output',type=Path,default=ROOT/'build/signals-tests/upper-table')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    report=dict(schema_version=1,status='running',platform=PIN,cases=[])
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),out,pin=PIN) as bridge:
            report['machine']=verify_machine(bridge,args.rom,PIN)
            for bank in (2,3):
                for mode in ('raw','opt'):
                    name=f'bank{bank}-{mode}';print('Running '+name+'...',flush=True)
                    program=build(toolchain,ROOT/'tests/programs/upper_bank_table.act',out/name,
                        tasks=True,task_capacity=8,kernel_bank=bank,optimize=mode=='opt')
                    at=next(d['address'] for d in program['image']['data'] if '_KERNELBANK_' in d['name'])
                    result,_=execute(bridge,program,before_run=lambda b:b.poke(at,bank),load_timeout=180)
                    checks=data(bridge,program['image'],'checks',True)
                    require(checks==[0x500]+[1]*11,'Upper bank manager: '+str(checks))
                    c=program['build']['memory']['constants']
                    table=read(bridge,c['TABLE'],c['TABLE_BYTES'],program['output'])
                    require(table==(program['output']/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']],
                        'Ownership mutation escaped release or changed reserved banks')
                    report['cases'].append(dict(name=name,status='pass',build=program['build'],runtime=result,
                        observed=dict(checks=checks,table=list(table))))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four upper-table operation cases')


if __name__=='__main__':main()
