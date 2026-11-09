#!/usr/bin/env python3
"""Exercise GemARC against an actually exhausted writable SDFS disk."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from prepare_gemarc import prepare,PORT
from test_c_runtime import fixture
from test_c_process import run as process_run
from filesystem_audit import Audit


def run(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True);prepare(out/'prepared')
    source=out/'prepared/source/src/apps'
    result=process_run(out,True,app_sources=[ROOT/'tests/programs/gemarc_disk_full.c',
        source/'arcfile.c',source/'arccodec.c',PORT/'native/io.c',PORT/'native/metadata.c'],
        app_options=dict(includes=[source,PORT/'native'],minimum_stack=2560),
        fixture_source=fixture(out,'abi'),expected_completed=2,native_optimize=True,
        release_compiler=True,task_capacity=12,loader_failures=False,writable=True)
    audit=Audit((out/'system.atr').read_bytes());allocation=audit.sdfs()
    require(audit.files['FULL.ARC']==b'\x1a\0' and 'FILL.DAT' not in audit.files,
            'Disk-full failure damaged original archive or retained fill file')
    result['disk_full']=dict(actual_backend_exhaustion=True,executions=2,
        original_preserved=True,allocation=allocation)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
