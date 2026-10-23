#!/usr/bin/env python3
"""Actual loaded QED navigation, redraw and independent-client exposure checks."""
import argparse
from pathlib import Path
from native_program import ROOT
from prepare_qed import prepare
from build_c_program import build as application
from test_qed_editing import build_editor
from test_qed_native import process_run
from qed_viewport_observe import interact


def run(out,reuse=False,reuse_app=False,scenario='all',native_from=None):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    if native_from:
        import shutil
        from test_c_process import variant
        variant(native_from.resolve(),out,'sdfs');reuse=True
        shutil.copytree(native_from.resolve()/'selected',out/'selected',dirs_exist_ok=True)
    prepare(out/'inputs')
    application(out/'peer',[ROOT/'tests/programs/qed_peer.c'],minimum_stack=1024)
    provider=out/'c-image.json' if reuse else ROOT/'build/qed-editing/qe2-modes-opt/c-image.json'
    return process_run(out,True,reuse=reuse,rebuild_app=reuse,
        app_builder=lambda target:build_editor(target,provider,reuse_app),
        fixture_source=ROOT/'tests/programs/qed_viewport.act',expected_completed=4,
        native_optimize=True,release_compiler=True,stack_observation_index=3,
        profile_all=True,ram=True,
        interaction=lambda *args:interact(*args,scenario=scenario),loader_failures=False,
        retirement_timeout=90,media_files={
            'PEER.APP':(out/'peer/program.app').read_bytes(),
            'QED.RSC':(out/'inputs/resource/QED.RSC').read_bytes()})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true')
    parser.add_argument('--reuse-app',action='store_true')
    parser.add_argument('--scenario',choices=['all','long','geometry'],default='all')
    parser.add_argument('--native-from',type=Path)
    args=parser.parse_args()
    result=run(args.output,args.from_build,args.reuse_app,args.scenario,args.native_from)
    print(result['status'],result['completed'])
