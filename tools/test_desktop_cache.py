#!/usr/bin/env python3
"""Compare automatic command snapshots and forced misses with complete pixels."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from bitmap_console_oracle import Terminal
from build_bitmap_console import build_bitmap
from desktop_budget import delta
from gem_render_oracle import Raster, font_bytes
from generate_desktop import layout
from library_paths import read_source
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_desktop_presentation import desktop, frame, rectangle, text
from test_dos_stack import execute, ownership
from test_gem_cursor import overlay
from test_gem_interactive import pixels
from test_mouse_observe import BRIDGE, PIN, ROM


def scene(stage, font):
    raster = Raster(font)
    desktop(raster)
    shell_focus = stage < 4 or stage == 12
    frame(raster, (32, 24, 560, 208), b'Exec816 Shell', shell_focus)
    terminal = Terminal(64, 20)
    terminal.feed(b'ABC')
    terminal.paint(raster, 5, 5, shell_focus)
    panels = []
    if stage < 12:
        panels.append((0, 3, False))
    if 2 <= stage < 12:
        panels.append((192, 7 if stage == 11 else 6 if stage >= 9 else 4,
                       4 <= stage <= 10))
    if 3 <= stage <= 9 and stage != 8:
        x = 192 if stage in (5, 9) else 273 if stage == 7 else 384
        panels.append((x, 5, False))
    for x, pen, focused in panels:
        frame(raster, (x, 0, x+160, 80), b'Cache', focused, pen, close=True)
        text(raster, x+11, 19, b'XYZ', bg=pen)
    return overlay(raster, (320, 120))


def run(out, forced_miss=False, replay=False, production=False):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    require(not (production and forced_miss), 'Production control cannot force misses')
    cache = read_source(ROOT/'lib/desktop/deskcache.act')
    observations = (
        ('BYTE active,activeSlot', 'BYTE active,activeSlot\nLONGCARD captures,restores'),
        ('  active=ACTIVE_CAPTURE', '  captures==+1\n  active=ACTIVE_CAPTURE'),
        ('  active=ACTIVE_RESTORE', '  restores==+1\n  active=ACTIVE_RESTORE'),
    )
    for before, after in (() if production else observations):
        require(cache.count(before) == 1, 'Cache observation boundary changed')
        cache = cache.replace(before, after)
    if forced_miss:
        start = cache.index('  BYTE index', cache.index('PUBLIC BYTE FUNC Lookup'))
        end = cache.index('; With exactly two slots', start)
        cache = cache[:start]+'\nRETURN(NO_SLOT)\n\n'+cache[end:]
    (out/'deskcache.act').write_text(cache)
    p = read_build(out/'program') if replay else build_bitmap(
        ROOT/'tests/programs/desktop_cache.act', out, desktop=True, stack_checks=True)
    at = lambda mod, name: next(d['address'] for d in p['image']['data']
                               if f'_{mod}_{name.upper()}_' in d['name'])
    report = dict(status='running', slice='DR6', tier='development', qualification=False,
                  forced_miss=forced_miss, production=production, scenes=[], mode='opt')
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            report['machine'] = verify_machine(b, ROM, PIN)
            def read(mod, name, size=4):
                return int.from_bytes(b.memdump(at(mod, name), size), 'little')
            def before(bridge):
                font = font_bytes(out/'selected/src/vdi/font8x8.c')
                previous = b.eval_expr('@clk') & 0xffffffff
                for stage in range(1, 13):
                    marker = p['labels']['native_nmi']
                    condition = f'dw(${at("CACHEPOLICY", "checkpoint"):x})={stage}'
                    b.bp_clear_all()
                    b.bp_set(marker, condition=condition)
                    b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                    run_to(b, marker, condition=condition, frame_limit=12000, timeout=180)
                    directory = out/f'stage-{stage}'
                    directory.mkdir(exist_ok=True)
                    clock = b.eval_expr('@clk') & 0xffffffff
                    row = dict(stage=stage, elapsed_cycles=(clock-previous) & 0xffffffff,
                               pixels=pixels(b, directory, scene(stage, font)))
                    if not production:
                        row.update(captures=read('DESKCACHE', 'captures'),
                                   restores=read('DESKCACHE', 'restores'))
                    row['ids'] = {n: read('CACHEPOLICY', n)
                                  for n in ('first', 'second', 'third', 'reopened')}
                    structures = layout()
                    raw = b.memdump(read('DESKSTATE', 'service', 3), structures['Service']['size'])
                    row['slots'] = []
                    for index in range(2):
                        offset = structures['Service']['fields']['snapshots'] + index*structures['Snapshot']['size']
                        fields = structures['Snapshot']['fields']
                        row['slots'].append({name: int.from_bytes(
                            raw[offset+fields[name]:offset+fields[name]+size], 'little')
                            for name, size in [('window', 4), ('revision', 4), ('valid', 1), ('pinned', 1)]})
                    report['scenes'].append(row)
                    previous = clock
                    b.memload(at('CACHEPOLICY', 'gate'), stage.to_bytes(2, 'little'))
                b.bp_clear_all()
            report['runtime'], _ = execute(b, p, before_run=before, timeout=240, frame_limit=16000)
            ownership(b, p, p['output'])
            report['checks'] = read('CACHEPOLICY', 'checks', 2)
            report['stack_usage'] = stack_usage(b, p['build']['memory'])
            require(all(r['remaining_above_floor'] > 0 for r in report['stack_usage'].values()),
                    'Command cache stack floor')
        rows = report['scenes']
        live = lambda row: {s['window']: s for s in row['slots'] if s['valid']}
        require(set(live(rows[2])) == {rows[2]['ids']['second'], rows[2]['ids']['third']},
                'Three clean clients did not evict the oldest of two slots')
        second = rows[2]['ids']['second']
        require(live(rows[3])[second] == live(rows[2])[second], 'Frame focus invalidated client pixels')
        if not production:
            require(rows[3]['captures'] == rows[2]['captures'], 'Frame focus recaptured the client')
        require(second not in live(rows[8]), 'Hidden replacement kept a valid old snapshot')
        require(live(rows[9])[second]['revision'] > live(rows[3])[second]['revision'],
                'Exposed replacement did not capture its new revision')
        require(second not in live(rows[10]) and rows[10]['ids']['reopened'] in live(rows[10]),
                'Reopened window inherited a retired identity')
        require(not live(rows[11]), 'Retirement retained eligible snapshots')
        require(all(not s['pinned'] for row in rows for s in row['slots']), 'Settled slot remains pinned')
        if forced_miss:
            require(all(row['restores'] == 0 for row in rows), 'Forced miss restored pixels')
        elif not production:
            require(rows[5]['restores'] > rows[4]['restores'], 'Aligned exposure missed a valid snapshot')
            require(rows[7]['restores'] == rows[6]['restores'], 'Odd exposure widened a cache copy')
            require(rows[9]['restores'] == rows[8]['restores'], 'Hidden replacement restored stale pixels')
        report.update(status='pass', reserved_bank_zero_delta=delta(p['build']['memory']),
                      build_sha256=sha256(out/'program/build.json'), xex_sha256=sha256(p['xex']),
                      timing_scope='One sample per scene, including requests, all repairs, idle capture and two PAL frames; not a latency percentile')
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--forced-miss', action='store_true')
    parser.add_argument('--production', action='store_true')
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    run(args.output, args.forced_miss, args.replay, args.production)
