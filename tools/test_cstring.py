#!/usr/bin/env python3
"""Focused resident CSTRING imports: disk loading, two callers and retirement."""
import argparse
import json
from pathlib import Path
from build_command import compile_command
from generate_program import library_contracts
from library_paths import read_source
from make_data_disk import make
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from o65_fixtures import inspect
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(ROOT/'build/actionc')
    media=out/'media';media.mkdir(exist_ok=True)
    command=compile_command(toolchain,ROOT/'tests/programs/cstring_command.act',media/'CSTR',mode=='opt')
    for suffix in ('.options.json','.profile.json'):
        (media/('CSTR'+suffix)).replace(out/('CSTR'+suffix))
    raw=(media/'CSTR').read_bytes();info=inspect(raw)
    names={spec['symbol'] for spec in library_contracts(toolchain['directory'])[0]['providers'].values()}
    library_names=set(names)
    names.add('exec816_readargs_v1')
    require(names.issubset(info['imports']),'Fixture must exercise all library imports')
    report=json.loads((out/'CSTR.profile.json').read_text())
    require(not any(r['name'].startswith(('M_CSTRING_', 'M_DOSARGS_')) for r in report['routines']),'Command copied resident library routines')
    relocations=[r for r in info['relocations'] if r['tag']&31==0 and info['imports'][r['index']] in names]
    require(relocations and all(r['section']==2 and r['tag']==192 for r in relocations),'Expected ordinary direct native calls')
    imported=info['imports'].index('exec816_readargs_v1')
    name_at=raw.index(b'exec816_readargs_v1\0')
    include=(f'CONST FIXTURE_BYTES={len(raw)}, RELOCATION_COUNT={len(relocations)}\n'
             f'CONST OLD_DESCRIPTOR={raw.index(b"__a816_o65_compact_v3")+20}, OLD_ENTRY={raw.index(b"__a816_entry_v2")+14}, OLD_MAGIC={info["descriptor_at"]+3}, NATIVE_REVISION={info["descriptor_at"]+4}\n'
             f'CONST IMPORT_NAME={name_at}, IMPORT_VERSION={name_at+len("exec816_readargs_v")}, IMPORT_SIGNATURE={info["positions"][f"import{imported}.signature"]}\n'
             +'LONGCARD ARRAY relocationOffsets=['+' '.join(str(r['offset']) for r in relocations)+']\n'
             +'BYTE ARRAY relocationImports=['+' '.join(str(r['index']) for r in relocations)+']\n')
    (out/'cstring-fixture.inc').write_text(include)
    (media/'DATA.TXT').write_bytes(b'cstrings\n')
    files=make(out/'sdfs.atr',media,binary_names={'CSTR'},filesystem='sdfs',sector_bytes=128)
    source=out/'probe.act'
    source.write_text(read_source(ROOT/'tests/programs/cstring_resident.act',{'cstring-fixture.inc':out/'cstring-fixture.inc'}))
    mounts=json.loads((ROOT/'config/shell-sdfs.json').read_text())['mounts']
    program=build(toolchain,source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=False,dos_mounts=mounts)
    providers=json.loads((out/'providers.json').read_text())['providers']
    library=[r for r in program['image']['routines'] if r['name'].startswith('M_CSTRING_IMPL_')]
    require(len(library)==len(library_names),'Expected one resident implementation')
    for provider in [p for p in providers if p['name'] in library_names]:
        require(any(r['address']==provider['address'] and r['size']==provider['size'] for r in library),'Provider is not the implementation entry')
    parser=[r for r in program['image']['routines'] if r['name'].startswith(('M_DOSARGS_', 'M_PROGRAMAPI_READARGS_'))]
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as bridge:
        for name,value in PIN['configuration'].items():bridge.config(name,str(value).lower() if isinstance(value,bool) else value)
        bridge.config('diskemu','generic56k');bridge.mount(0,str(out/'sdfs.atr'))
        machine=verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
        except Exception:
            print({name:data(bridge,program['image'],name) for name in ('checks','firstId','secondId','finished')},flush=True)
            raise
        ownership(bridge,program,out)
        require(data(bridge,program['image'],'finished')==[1],'Resident fixture did not finish')
        checks=int.from_bytes(bytes(data(bridge,program['image'],'checks')),'little')
        placements=data(bridge,program['image'],'placements')
    return dict(status='pass',tier='development',mode=mode,build=program['build'],pin=PIN,machine=machine,
                runtime=runtime,command=command,command_bytes=len(raw),library=library,
                resident_code_bytes=sum(r['size'] for r in library),argument_parser=parser,
                argument_parser_code_bytes=sum(r['size'] for r in parser),provider_bytes=next(len(s['bytes']) for s in program['image']['segments'] if bytes(s['bytes'][:4])==b'EPV2'),checks=checks,placements=placements,
                direct_library_relocations=len(relocations),imports=info['imports'],media_sha256=sha256(out/'sdfs.atr'),
                bank_zero_delta=dict(fixed=0,per_task=0))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    record=dict(status='running')
    try:record=run(out,args.case)
    except Exception as error:record.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Resident CSTRING passed',args.case,record['checks'])
