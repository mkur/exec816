#!/usr/bin/env python3
"""Native GemARC paths, enumeration failure, allocation rollback and dates."""
import argparse,json
from pathlib import Path
from native_program import ROOT
from prepare_gemarc import prepare,PORT
from test_c_runtime import fixture
from test_c_process import run as process_run


def run(out,reuse=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True);prepare(out/'prepared')
    source=out/'prepared/source/src/apps'
    result=process_run(out,True,reuse=reuse,rebuild_app=reuse,app_sources=[ROOT/'tests/programs/gemarc_paths.c',
        *[PORT/'native'/name for name in ('path.c','io.c','metadata.c')],ROOT/'c/calypsi/file-list.c'],
        app_options=dict(includes=[source,PORT/'native',ROOT/'c/calypsi',ROOT/'c/runtime'],minimum_stack=2560,
            definitions={str(PORT/'native/path.c'):['-Dmalloc=GemArcPathMalloc','-DExNextBatch=GemArcPathNext']}),
        fixture_source=fixture(out,'abi'),expected_completed=2,native_optimize=True,
        release_compiler=True,task_capacity=12,loader_failures=False,ram=True,
        media_files={'CORPUS.ARC':b'\x1a\0'})
    result['gemarc_paths']=dict(executions=2,enumerated_files=65,batch_limit=64,
        failures=['allocation-1','allocation-2','second-enumeration-batch','read-only-media'],
        timestamps='2024-02-29 23:59:58 round trip',exact_heap_restoration=True)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true');args=parser.parse_args()
    run(args.output,args.from_build)
