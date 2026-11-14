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


def run(out,mode,abi=False,reuse=False,filesystem='sdfs'):
    out.mkdir(parents=True,exist_ok=True)
    definitions={name:['-DEXEC_CRT_TEST'] for name in ('allocation.c','files.c')}
    if abi:definitions['gemdos_compat.c']=['-DGEMDOS_ABI_ONLY']
    record=process_run(out,mode=='opt',reuse=reuse,rebuild_app=reuse,
        app_sources=[ROOT/'tests/programs/gemdos_compat.c'],
        app_options=dict(gemdos=True,minimum_stack=ABI['stack_floor_bytes'],
            includes=[ROOT/'c/runtime',ROOT/'c/compat/gemdos'],definitions=definitions,
            probes=[(ROOT/'c/compat/gemdos/layout.c',expected_layout())]),
        fixture_source=fixture(out,'abi' if abi else 'files'),expected_completed=2 if abi else 4,
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
    p.add_argument('--from-build',action='store_true')
    p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    a=p.parse_args()
    run(a.output.resolve(),a.case,a.abi,a.from_build,a.filesystem)
