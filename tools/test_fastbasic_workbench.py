#!/usr/bin/env python3
"""Selectable development checks for the native FastBasic GEM workbench."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, read_build, require, sha256, verify_machine


def wb0(out, reuse=False,provider=False):
    from build_c_program import build as application
    from build_fastbasic import build as fastbasic
    from build_gem_desktop import build_desktop
    from make_data_disk import make
    from os_boundary import emulator
    from test_dos_stack import execute, ownership
    from test_cooperative import data
    from test_mouse_observe import PIN, BRIDGE, ROM
    from stack_budget import stack_usage
    out.mkdir(parents=True, exist_ok=True)
    if not reuse:
        if not provider:
            production=application(out/'app', [ROOT/'examples/gem-basic'/n for n in ('main.c','basic.c')])
            probe=application(out/'probe', [ROOT/'tests/programs/basic_lifecycle.c',ROOT/'examples/gem-basic/basic.c'])
        else:production=json.loads((out/'app/app.json').read_text())
        _,basic=fastbasic(ROOT/'build/fastbasic')
        media=out/'media';media.mkdir(exist_ok=True)
        (media/'PROBE.APP').write_bytes((out/'probe/program.app').read_bytes())
        (media/'FBCI.COM').write_bytes((ROOT/'build/fastbasic/FBCI.COM').read_bytes())
        (media/'HELLO.BAS').write_bytes(b'PRINT "WB0"\x9b')
        make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
             binary_names={p.name for p in media.iterdir()})
        mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2),
                dict(alias='RAM',format=3)]
        if provider:
            from build_bitmap_console import prepare
            from native_program import build,compiler
            foreign=json.loads((out/'c-image.json').read_text())
            for name,digest in foreign['provenance']['source_inputs'].items():
                require(sha256(ROOT/name)==digest,'Changed cached provider source: '+name)
            launcher=prepare(ROOT/'tests/programs/basic_lifecycle.act',out,foreign,desktop=True,aes=True)
            p=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',tasks=True,
                task_capacity=8,foreign_image=foreign,console_deferred=True,
                memory_profile=out/'fixture-memory.json',system_mount='D1',dos_mounts=mounts,
                sdx=True,sdx_drive_a='RAM:',sdx_car_root='SYS:',stack_checks=True)
        else:
            p=build_desktop(out,source=ROOT/'tests/programs/basic_lifecycle.act',
                system_mount='D1',dos_mounts=mounts,sdx=True,sdx_drive_a='RAM:',
                sdx_car_root='SYS:',stack_checks=True,release_compiler=True)
    else:
        p=read_build(out/'program')
        production=json.loads((out/'app/app.json').read_text())
        basic=json.loads((ROOT/'build/fastbasic/build.json').read_text())
    report=dict(status='running',tier='development',qualification=False,slice='WB0',
        source_inputs={str(q.relative_to(ROOT)):sha256(q) for q in [
            ROOT/'examples/gem-basic'/n for n in ('main.c','basic.c','basic.h')]},
        application={k:production[k] for k in ('bytes','sha256','span','verified_banks','abi')},
        fastbasic=basic,build=p['build'],reserved_bank_zero_delta=dict(
            fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0,baseline='existing SDX/GEM profile; 544-byte guest pool retained'))
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned bridge')
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b._cmd_ok('MOUSE ST');b.config('diskemu','generic56k');b.mount(0,str(out/'system.atr'))
            report['machine']=verify_machine(b,ROM,PIN)
            try:
                runtime,_=execute(b,p,timeout=600,frame_limit=30000)
            except Exception:
                report['checks']=data(b,p['image'],'checks',True)
                report['completed']=data(b,p['image'],'completed',True)
                report['primary']=data(b,p['image'],'primary',True)
                report['secondary']=data(b,p['image'],'secondary',True)
                raise
            report['completed']=data(b,p['image'],'completed',True)
            report['checks']=data(b,p['image'],'checks',True)
            require(report['completed'][0]>12,'Incomplete lifecycle/combined-profile/capacity smoke')
            ownership(b,p,p['output'])
            report.update(status='pass',runtime=runtime,stack_usage=stack_usage(b,p['build']['memory']),
                free_upper_words=data(b,p['image'],'freeUpper',True))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--slice',choices=('WB0',),required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--from-build',action='store_true')
    p.add_argument('--reuse-provider',action='store_true',help='WB0: check and reuse the emitted GEM provider')
    a=p.parse_args()
    wb0(a.output.resolve(),a.from_build,a.reuse_provider)
