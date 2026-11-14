#!/usr/bin/env python3
"""Loaded GEMDOS source subset on the pinned native Process/DOS provider."""
import argparse
import json
from pathlib import Path
from native_program import ROOT
from generate_gemdos_compat import expected_layout
from c_program import ABI
from test_c_runtime import fixture
from test_c_process import run as process_run


def run(out,mode,abi=False,reuse=False,filesystem='sdfs',metadata=False):
    out.mkdir(parents=True,exist_ok=True)
    definitions={} if metadata else {name:['-DEXEC_CRT_TEST'] for name in ('allocation.c','files.c')}
    source='dos_examine_fh.c' if metadata else 'gemdos_compat.c'
    if abi:definitions[source]=['-DGEMDOS_ABI_ONLY']
    native=fixture(out,'abi' if abi and not metadata else 'files')
    if metadata:
        text=native.read_text().replace('DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)',
            'DOS.Open(BYTE POINTER(c"SYS:FHDATA.DAT"),DOS.MODE_OLDFILE)')
        text=text.replace('  LET oldInput=',
            '  Require(DOS.Seek(input,11,DOS.OFFSET_BEGINNING)=0)\n  LET oldInput=')
        text=text.replace('  DOS.SelectInput(oldInput)',
            '  Require(DOS.Seek(input,0,DOS.OFFSET_CURRENT)=11)\n  DOS.SelectInput(oldInput)')
        native.write_text(text)
    record=process_run(out,mode=='opt',reuse=reuse,rebuild_app=reuse,
        app_sources=[ROOT/'tests/programs'/source],
        app_options=dict(gemdos=True,minimum_stack=ABI['stack_floor_bytes'],
            includes=[ROOT/'c/runtime',ROOT/'c/compat/gemdos'],definitions=definitions,
            probes=[(ROOT/'c/compat/gemdos/layout.c',expected_layout())]),
        fixture_source=native,expected_completed=2 if abi and not metadata else 4,
        media_files={'FHDATA.DAT':bytes(n&255 for n in range(513)),'EMPTY.DAT':b''} if metadata else None,
        native_optimize=True,release_compiler=True,writable=True,ram=True,
        observe_stacks=not abi,filesystem=filesystem,loader_failures=False)
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('GEMDOS',mode,'ABI' if abi else filesystem,'passed',flush=True)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case',choices=('raw','opt'),default='opt')
    p.add_argument('--abi',action='store_true')
    p.add_argument('--metadata',action='store_true')
    p.add_argument('--from-build',action='store_true')
    p.add_argument('--variant-from',type=Path,help='Reuse native emission with a rebuilt APP')
    p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    a=p.parse_args()
    if a.variant_from:
        from test_c_process import variant
        variant(a.variant_from.resolve(),a.output.resolve(),a.filesystem)
    run(a.output.resolve(),a.case,a.abi,a.from_build or bool(a.variant_from),a.filesystem,a.metadata)
