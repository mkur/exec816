#!/usr/bin/env python3
"""SM5: a small interaction/UPDATE case and loaded MGVIEW beside Counter."""
import argparse
import json
from pathlib import Path
import shutil
from contextlib import nullcontext
from unittest.mock import patch

from build_c_program import build as application
from build_gem_desktop import build_desktop
from build_mgview import build as viewer
from c_program import ABI
from make_data_disk import make
from measure_mgview import run as scroll
from native_program import ROOT, read_build, require, sha256
from test_aes_migration import inputs as interaction_inputs, run as interaction
from test_mgview import DOCUMENT, LAYOUT


def reuse_app(source, target):
    """Reuse admitted application ABI and unchanged sources, never its provider."""
    record=json.loads((source/'app.json').read_text())
    require(record['abi']==ABI,'Stale application ABI: '+str(source))
    require(sha256(source/'program.app')==record['sha256'],'Changed APP: '+str(source))
    for name,digest in record['inputs'].items():
        require(Path(name).is_file() and sha256(Path(name))==digest,
                'Changed cached application input: '+name)
    target.mkdir(parents=True,exist_ok=True)
    for name in ('app.json','program.app'):
        shutil.copyfile(source/name,target/name)
    for path in source.glob('*.lst'):
        shutil.copyfile(path,target/path.name)
    return dict(mode='reused',source=str(source),sha256=record['sha256'],abi=ABI['version'])


def build_scroll(out, apps_from=None, reuse_c=False):
    out.mkdir(parents=True,exist_ok=True)
    apps={}
    for name in ('mgview',):
        target=out/'apps'/name
        if apps_from:
            apps[name]=reuse_app(apps_from/'apps'/name,target)
        else:
            if name=='mgview':
                record=viewer(target,probes=[(ROOT/'tests/programs/mgview_layout.c',LAYOUT)])
            else:
                record=application(target,[ROOT/'examples/gem-counter'/n for n in
                    ('main.c','counter.c')],minimum_stack=ABI['stack_floor_bytes'])
            apps[name]=dict(mode='built',sha256=record['sha256'],abi=ABI['version'])
    # This builds the current shared provider and native fixture only. There is
    # no application catalog, demo packaging or QED build in this path.
    provider=nullcontext()
    if reuse_c:
        cached=json.loads((out/'c-image.json').read_text())
        for name,digest in {**cached['provenance']['source_inputs'],
                            **cached['provenance']['header_inputs']}.items():
            require(sha256(ROOT/name)==digest,'Changed cached provider input: '+name)
        require(cached['provenance']['compiler_flags'][-1]=='-O2','Wrong cached C mode')
        provider=patch('build_gem_desktop.drawing',lambda *args,**kwargs:cached)
    with provider:
        program=build_desktop(out,source=ROOT/'tests/programs/c_mgview.act',
            build_applications=False,program_output=out/'program',release_compiler=True,
            system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                sector_bytes=256,profile=4,format=2)])
    media=out/'media';media.mkdir(exist_ok=True)
    for name in apps:
        shutil.copyfile(out/'apps'/name/'program.app',media/(name.upper()+'.APP'))
    (media/'VIEW.TXT').write_bytes(DOCUMENT)
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
        binary_names={'MGVIEW.APP','VIEW.TXT'})
    record=dict(inputs=interaction_inputs(),apps=apps,
        xex_sha256=sha256(program['xex']),provider_sha256=sha256(out/'c-image.json'))
    (out/'fixture.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def reuse_interaction(folder):
    require(json.loads((folder/'inputs.json').read_text())==interaction_inputs(),
            'Changed completed interaction inputs')
    result=json.loads((folder/'results.json').read_text())
    program=read_build(folder/'program')
    require(result['status']=='pass' and result['runtime']['status']==0
            and result['runtime']['guards']=='intact','Incomplete interaction check')
    require(result['build']['xex_sha256']==sha256(program['xex']),
            'Changed interaction executable')
    return result


def run(out, apps_from=None, interaction_from=None, reuse=False, presenter=True, reuse_c=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',qualification=False,
        reserved_bank_zero_delta=dict(fixed=0,root=0,kernel=0,idle=0,per_public_task=0))
    try:
        folder=interaction_from or out/'interaction'
        tested=reuse_interaction(folder) if interaction_from else interaction(folder,reuse=reuse,reuse_c=reuse_c)
        report['interaction']=dict(capture=str(folder),results_sha256=sha256(folder/'results.json'),
            checks=tested['AESChecks'],failures=tested['AESFailures'],
            progress=tested['progress'],keyboard=tested['keyboardReady'],
            callback=tested['callbackReady'],native_sha256=tested['build']['xex_sha256'])
        cache=out/'viewer'
        if reuse:
            fixture=json.loads((cache/'fixture.json').read_text())
            require(fixture['inputs']==interaction_inputs(),'Changed viewer fixture inputs')
            require(sha256(read_build(cache/'program')['xex'])==fixture['xex_sha256'],
                    'Changed viewer native image')
        else:
            fixture=build_scroll(cache,apps_from,reuse_c)
        report['apps']=fixture['apps']
        observed=scroll(cache,out/'scroll',presenter=presenter,expect_copy_units=1)
        report['scroll']=dict(capture=str(out/'scroll'),results_sha256=sha256(out/'scroll/results.json'),
            native_sha256=observed['native_sha256'],samples=observed['audit']['samples'])
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('SM5 interaction and MGVIEW/Counter acceptance passed',flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apps-from',type=Path,help='Reuse matching MGVIEW/Counter APPs from this fixture')
    parser.add_argument('--interaction-from',type=Path,help='Reuse a completed interaction check with matching inputs')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--reuse',action='store_true',help='Replay matching emitted fixtures without builds')
    mode.add_argument('--reuse-c',action='store_true',help='Rebuild native policy with verified cached C providers')
    parser.add_argument('--no-presenter',action='store_true',help='Omit detailed manager phase tracing')
    args=parser.parse_args()
    run(args.output,args.apps_from.resolve() if args.apps_from else None,
        args.interaction_from.resolve() if args.interaction_from else None,
        args.reuse,not args.no_presenter,args.reuse_c)
