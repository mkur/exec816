#!/usr/bin/env python3
"""Exercise fixed GUI component failures through the emitted native bootstrap."""
import argparse
import json
from pathlib import Path

from make_data_disk import make
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator
from test_dos_stack import execute, ownership


def run(bundle, output, names=None):
    output.mkdir(parents=True, exist_ok=True)
    program = read_build(bundle)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    component = (bundle/'media/GEMSYS.BIN').read_bytes()
    ready = next(d['address'] for d in program['image']['data'] if '_GEMCOMPONENT_READY_' in d['name'])
    error = next(d['address'] for d in program['image']['data'] if '_GEMCOMPONENT_ERROR_' in d['name'])
    report = dict(status='running', tier='development', qualification=False, cases=[])
    cases = {'missing':None, 'wrong-build':component[:12]+bytes([component[12]^1])+component[13:],
             'truncated':component[:2048],
             'bad-checksum':component[:-1]+bytes([component[-1]^1]),
             'trailing-data':component+b'X'}
    if manifest['filesystem']=='sdfs':
        cases['read-error']=component
    if names:
        require(set(names)<=cases.keys(),'Unknown component failure case')
        cases={name:cases[name] for name in names}
    try:
        with emulator(ROOT/'build/mouse-bridge',ROOT/'build/firmware/altirraos-816.rom',output,
                      pin=manifest['pin']) as b:
            for key,value in manifest['configuration'].items():
                b.config(key,str(value).lower() if isinstance(value,bool) else value)
            report['machine'] = verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',manifest['pin'])
            b.mount(7,str(bundle/'work.atr'))
            for name, payload in cases.items():
                case = output/name
                media = case/'media'
                media.mkdir(parents=True,exist_ok=True)
                if payload is not None:
                    (media/'GEMSYS.BIN').write_bytes(payload)
                make(case/'system.atr',media,binary_names={'GEMSYS.BIN'} if payload is not None else set(),
                     filesystem=manifest['filesystem'],sector_bytes=manifest['sector_bytes'],
                     sectors=manifest['mounts'][0]['sectors'])
                if name=='read-error':
                    # A bad backlink in the second map page fails a real DOS
                    # read after the header and initial payload have succeeded.
                    from make_sdfs_fixtures import Media
                    damaged=Media((case/'system.atr').read_bytes())
                    row=damaged.row(damaged.entry(damaged.word(25),'GEMSYS.BIN'))
                    first=int.from_bytes(row[1:3],'little')
                    second=damaged.word(damaged.at(first))
                    require(second!=0,'Fixture needs a second map page')
                    damaged.put(damaged.at(second)+2,second)
                    (case/'system.atr').write_bytes(damaged.raw)
                b.mount(0,str(case/'system.atr'))
                runtime,_ = execute(b,{**program,'output':case},expected_status=0xfc90,
                                    timeout=240,frame_limit=12000)
                require(b.memdump(ready,1)==b'\0','Failed component was published')
                failure = int.from_bytes(b.memdump(error,4),'little')
                require(failure!=0,'Missing component diagnostic')
                ownership(b,program,bundle)
                report['cases'].append(dict(name=name,error=failure,runtime=runtime))
                print(name,'passed',flush=True)
        report['status']='pass'
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',action='append')
    args=parser.parse_args()
    run(args.bundle.resolve(),args.output.resolve(),args.case)
