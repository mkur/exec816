#!/usr/bin/env python3
"""Focused desktop service execution on the pinned hosted 65816."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, require, sha256, verify_machine, read_build
from os_boundary import emulator
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from test_cooperative import data
from desktop_budget import delta as desktop_delta
from stack_budget import bank_zero_delta, stack_usage
from generate_desktop import files, layout
from build_bitmap_console import drawing


def run(out, mode, existing=None):
    out.mkdir(parents=True, exist_ok=True)
    for path, expected in files().items():
        require(path.read_text() == expected, 'Stale desktop records')
    require(sha256(BRIDGE / 'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
            'Unpinned desktop emulator')
    report = dict(status='running', tier='development', slice='DT1', mode=mode,
                  layouts=layout(), qualification=False)
    try:
        if existing:p=read_build(existing)
        else:
            foreign=drawing(out,mode=='opt',widgets=True)
            source=out/'native-widget-probe.act'
            text=(ROOT/'tests/programs/native_desktop.act').read_text()
            text=text.replace('  root=EXEC.FindTask(NULL)',
                '  Require(DESKWIDGETS.Bind($%x,$%x)<>0)\n  root=EXEC.FindTask(NULL)' %
                (foreign['symbols']['WidgetEntry'],foreign['symbols']['WidgetPacket']))
            source.write_text(text)
            from generate_memory import PROFILE
            profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
            memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
            p=build(compiler(ROOT/'build/actionc'),source,out/'program',optimize=mode=='opt',memory_profile=memory,
                tasks=True,task_capacity=8,console=False,console_deferred=True,foreign_image=foreign)
        report.update(build=p['build'], bank_zero_delta=bank_zero_delta(p['build']['memory']),
                      reserved_bank_zero_delta=desktop_delta(p['build']['memory']))
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROM, PIN)
            try:
                report['runtime'], _ = execute(bridge, p, timeout=120, frame_limit=6000)
            except Exception:
                print('Desktop checks:', data(bridge, p['image'], 'checks', True), flush=True)
                for name in ('peerStage', 'held', 'finished', 'inject'):
                    print(name, data(bridge, p['image'], name), flush=True)
                raise
            ownership(bridge, p, p['output'])
            report['checks'] = data(bridge, p['image'], 'checks', True)[0]
            report['stacks'] = stack_usage(bridge, p['build']['memory'])
            require(report['checks'] >= 100, 'Missing service assertions')
            require(all(v['remaining_above_floor'] >= 0 for v in report['stacks'].values()),
                    'Desktop fixture exceeded its interrupt floor')
        with emulator(BRIDGE, ROM, out / 'held-removal', pin=PIN) as bridge:
            def before(b):
                symbol = next(d for d in p['image']['data'] if '_VARIANT_' in d['name'])
                b.poke(symbol['address'], 1)
            report['held_removal'], _ = execute(bridge, p, before_run=before,
                                                expected_status=4, timeout=120, frame_limit=6000)
            require(data(bridge, p['image'], 'peerStage') == [1], 'Wrong held-removal boundary')
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Desktop DT1 passed', mode, report['checks'], 'checks', flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.from_build)
