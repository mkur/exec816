#!/usr/bin/env python3
"""Actual loaded archive engine over the common C runtime and native files."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from prepare_gemarc import prepare,PORT
from test_gemarc_host import corpus,member
from test_c_runtime import fixture
from test_c_process import run as process_run


def run(out,reuse=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    prepare(out/'prepared');source=out/'prepared/source/src/apps'
    sources=[ROOT/'tests/programs/gemarc_core.c',source/'arcfile.c',source/'arccodec.c',
        PORT/'native/io.c',PORT/'native/metadata.c']
    inputs=b''.join(member(*item) for item in corpus())+b'\x1a\0'
    result=process_run(out,True,reuse=reuse,rebuild_app=reuse,app_sources=sources,
        app_options=dict(includes=[source,PORT/'native',ROOT/'c/runtime'],minimum_stack=2560,
            extra_inputs=[source/'arcfile.h',source/'arccodec.h',PORT/'native/platform.h'],
            definitions={str(ROOT/'c/runtime/files.c'):['-DEXEC_CRT_TEST','-DRename=GemArcTestRename']},
            probes=[(sources[0],[('ARC_ENTRY',33),('ARC_ENTRY csize',21),('ARC_RECOVERY',515)])]),
        fixture_source=fixture(out,'files'),expected_completed=4,native_optimize=True,
        task_capacity=12,
        release_compiler=True,loader_failures=False,writable=True,ram=True,
        media_files={'CORPUS.ARC':inputs,'FAIL.DAT':bytes(range(256))*60})
    require(result['runtime']['native_irq_count']>0 and result['runtime']['native_nmi_count']>0,'Missing IRQ/NMI')
    result['archive_core']=dict(methods=[1,2,3,4,8,9],dictionary_clear=True,
        failure_cases=['read','short-write','consumed-close','publication-rename','cancel'],
        executions=4,private_allocations=9,payload_bytes=84610)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true');args=parser.parse_args();run(args.output,args.from_build)
