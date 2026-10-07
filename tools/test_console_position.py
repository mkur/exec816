#!/usr/bin/env python3
"""Focused positioned-write provider, FIFO, cancellation and bitmap spans."""
import argparse
import json
from contextlib import nullcontext
from pathlib import Path

import adapter_state as adapter
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_cooperative import data


def run(out, compiler_dir, mode='opt', bitmap=False, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    shape = mode == 'raw'
    source = ROOT/'tests/programs'/('console_position_shape.act' if shape else 'console_position.act')
    if bitmap:
        from build_bitmap_console import build_bitmap
        from test_mouse_observe import PIN, BRIDGE, ROM
        p = read_build(out/'program') if reuse else build_bitmap(
            source, out, True, compiler_dir=compiler_dir,
            image_data=[(0x30fffd, b' 1229')])
        foreign = json.loads((out/'c-image.json').read_text())
        if reuse:
            require(sha256(out/'launcher.act') == p['build']['source_sha256'],
                    'Changed replay launcher')
            for group in ('task_inputs', 'console_inputs', 'banked_inputs'):
                for name, expected in p['build'].get(group, {}).items():
                    path = ROOT/name
                    if path.is_file():
                        require(sha256(path) == expected, 'Changed replay input: '+name)
    else:
        PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
        BRIDGE, ROM = ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom'
        p = build(compiler(compiler_dir), source, out, optimize=not shape,
                  tasks=True, task_capacity=8, console=True,
                  image_data=[(0x30fffd, b' 1229')])
    from generate_program import ABI, physical
    args, incoming, result = physical(ABI['providers']['WriteAt'])
    routine = next(r for r in p['image']['routines'] if r['name'].startswith('M_PROGRAMAPI_WRITEAT_'))
    require([{k: a[k] for k in ('offset', 'size', 'alignment')} for a in routine['arguments']] == args
            and routine['outgoing_bytes'] == incoming and routine['result_bytes'] == result,
            'Emitted positioned provider shape mismatch')
    observations = []
    if bitmap:
        from bitmap_console_trace import observation, intervals
        observer = observation(foreign, p, True, module='POSITIONTEST')
    else:
        observer = nullcontext({})
    with observer as marks, emulator(BRIDGE, ROM, out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, ROM, PIN)
        def before(b):
            if bitmap:
                b.profile_start()
            if shape:
                return
            at = next(d['address'] for d in p['image']['data'] if '_POSITIONTEST_CHECKPOINT_' in d['name'])
            gate = next(d['address'] for d in p['image']['data'] if '_POSITIONTEST_GATE_' in d['name'])
            for stage, number in ((1, b'00000'), (2, b' 1229'), (3, b'    9')):
                condition = f'dw(${at:x})={stage}'
                b.bp_clear_all()
                b.bp_set(p['labels']['native_nmi'], condition=condition)
                b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                run_to(b, p['labels']['native_nmi'], 6000, 60, condition)
                require(b.peek16(adapter.STATE) == 65535, 'Fixture stopped early')
                if bitmap:
                    from gem_render_oracle import Raster, font_bytes
                    from bitmap_console_oracle import Terminal
                    from test_gem_interactive import pixels
                    terminal = Terminal(80, 30)
                    terminal.feed(b'PRIME SEARCH\n\nPrimes    '+number+b'\nLatest    00000\nPass      0000000000')
                    model = Raster(font_bytes(out/'selected/src/vdi/font8x8.c'))
                    terminal.paint(model, 0, 0, True)
                    folder = out/f'stage-{stage}'
                    folder.mkdir(exist_ok=True)
                    observations.append(dict(stage=stage, pixels=pixels(b, folder, model.packed())))
                b.memload(gate, stage.to_bytes(2, 'little'))
            b.bp_clear_all()
        try:
            runtime, _ = execute(b, p, before_run=before, timeout=180, frame_limit=9000)
        except Exception:
            if not shape:
                print('Position checks:', data(b, p['image'], 'checks', True), flush=True)
            raise
        require(data(b, p['image'], 'finished') == [1], 'Fixture incomplete')
        ownership(b, p, p['output'])
        if bitmap:
            b.profile_stop()
    drawing = intervals(out/'emulator.log', marks, 3) if bitmap else []
    for entry in drawing:
        if entry['kind'] == 'work' and entry['stage'] in (2, 3):
            calls = entry['calls']
            require(calls.get('GemDrawingText', 0) == 1, 'Field needs one text draw')
            require(calls.get('_text_record', 0) == 5, 'Field must draw exactly five glyphs')
            require(not any(calls.get(k, 0) for k in
                    ('GemDrawingFill', 'GemDrawingCopy', 'GemDrawingScrollStart')),
                    'Positioned field cleared or scrolled the display')
    return dict(status='pass', tier='development', mode=mode, bitmap=bitmap,
                runtime=runtime, build=p['build'], machine=machine,
                observations=observations, drawing=drawing,
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--case', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--bitmap', action='store_true')
    parser.add_argument('--reuse', action='store_true', help='Replay the recorded bitmap image')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.compiler_dir, args.case, args.bitmap, args.reuse)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Positioned console checks passed:', args.case, args.bitmap, flush=True)
