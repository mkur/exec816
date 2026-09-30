#!/usr/bin/env python3
"""Regress unchanged launch profiles and Lists after the Task API migration."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, PLATFORM_PIN, build, compiler, execute, platform_files, sha256, verify_machine
from os_boundary import emulator
from test_banked import PIN
from test_cooperative import check as cooperative_check
from test_preemptive import check as preemptive_check
from test_lists import named_case, preemptive_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir',type=Path,required=True)
    parser.add_argument('--bridge-dir',type=Path,required=True)
    parser.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output',type=Path,default=ROOT/'build/tasks-exec-regressions')
    parser.add_argument('--case',action='append',help='Select regression cases; may be repeated')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    toolchain = compiler(args.compiler_dir)
    platform_files(args.bridge_dir,args.rom)
    report = {'schema_version':1,'status':'running','cases':[],
              'driver_sha256':sha256(Path(__file__))}
    try:
        for banked,pin in ((False,PLATFORM_PIN),(True,PIN)):
            with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output/str(banked),pin=pin) as bridge:
                config = verify_machine(bridge,args.rom,pin)
                for optimize in (False,True):
                    mode = 'opt' if optimize else 'raw'
                    for kind in (('banked',) if banked else ('single','cooperative','preemptive')):
                        name = kind+'-'+mode
                        if args.case and name not in args.case: continue
                        print('Running '+name+'...',flush=True)
                        source = 'hello' if kind == 'single' else 'cooperative' if kind == 'cooperative' else 'preemptive'
                        program = build(toolchain,ROOT/f'examples/{source}.act',output/name,optimize=optimize,
                                        cooperative=kind!='single',preemptive=kind in ('preemptive','banked'),banked=banked)
                        result,screen = execute(bridge,program,frame_limit=1200,timeout=180)
                        observed = {}
                        if kind == 'cooperative':
                            observed = cooperative_check(bridge,program,'demo',result,screen)
                        elif kind in ('preemptive','banked'):
                            observed = preemptive_check(bridge,program,'demo',result,screen)
                        report['cases'].append({'name':name,'status':'pass','platform':pin,'config':config,
                                                'build':program['build'],'runtime':result,'observed':observed})
                    if banked:
                        for kind in ('named','private-probe','shared-probe'):
                            name = 'lists-'+kind+'-'+mode
                            if args.case and name not in args.case: continue
                            print('Running '+name+'...',flush=True)
                            if kind == 'named':
                                observed = named_case(bridge,toolchain,output/name,optimize)
                            else:
                                observed = preemptive_case(bridge,toolchain,output/name,optimize,kind=='shared-probe',True,timeout=180)
                            report['cases'].append({'name':name,'status':'pass','platform':pin,'config':config,'observed':observed})
        if args.case and {case['name'] for case in report['cases']} != set(args.case):
            raise RuntimeError('Unknown regression case')
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed '+str(len(report['cases']))+' platform and Lists regressions')


if __name__ == '__main__':
    main()
