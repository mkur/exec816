#!/usr/bin/env python3
"""Run emitted Layers geometry and scene checks on the pinned hosted machine."""
import argparse
import json
import random
import struct
from pathlib import Path

from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from test_cooperative import data


def geometry_cases():
    base = (0, 0, 16, 12)
    cuts = [(-4, -4, -1, -1), (16, 0, 20, 12), (0, 0, 16, 12),
            (3, 2, 10, 9), (0, 3, 8, 7), (8, 3, 16, 7),
            (4, 0, 12, 6), (4, 6, 12, 12), (4, 4, 4, 7),
            (-32768, -32768, 32767, 32767)]
    rows = [(base, cut, (2, 1, 14, 11)) for cut in cuts]
    rows += [((0, 0, 0, 0), base, base),
             ((-32768, -32768, 32767, 32767), (-1, -1, 1, 1),
              (-32768, -32768, 32767, 32767))]
    rng = random.Random(20261004)
    def rectangle():
        left, right = sorted(rng.randint(-24, 24) for _ in range(2))
        top, bottom = sorted(rng.randint(-24, 24) for _ in range(2))
        return left, top, right, bottom
    rows += [(rectangle(), rectangle(), rectangle()) for _ in range(116)]
    return rows


def contains(rect, x, y):
    return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]


def check_region(raw, base, cut, clip=None):
    count, = struct.unpack_from('<H', raw)
    require(count <= 4, 'Unbounded single subtraction')
    rects = [struct.unpack_from('<4h', raw, 2 + i * 8) for i in range(count)]
    require(all(r[0] < r[2] and r[1] < r[3] for r in rects), 'Empty/inverted piece')
    # Coordinate compression checks every cell in the partition, including
    # signed extremes, without duplicating the native subtraction algorithm.
    bounds = [base, cut, *rects, *([clip] if clip is not None else [])]
    xs = sorted({r[k] for r in bounds for k in (0, 2)})
    ys = sorted({r[k] for r in bounds for k in (1, 3)})
    for x in xs:
        for y in ys:
            expected = contains(base, x, y) and not contains(cut, x, y)
            if clip is not None:
                expected &= contains(clip, x, y)
            actual = sum(contains(r, x, y) for r in rects)
            require(actual == int(expected), f'Coverage/overlap at {(x, y)}: {rects}')


def run(out, mode):
    out.mkdir(parents=True, exist_ok=True)
    rows = geometry_cases()
    inputs = struct.pack('<H', len(rows)) + b''.join(
        struct.pack('<12h', *base, *cut, *clip) for base, cut, clip in rows)
    output_size = len(rows) * 68
    report = dict(status='running', tier='development', mode=mode,
                  bank_zero_delta=dict(fixed=0, root_kernel=0, per_task=[0]*8, idle=0))
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
                'Unpinned Layers emulator')
        program = build(compiler(ROOT/'build/actionc'),
                        ROOT/'tests/programs/native_layers.act', out/'program',
                        optimize=mode == 'opt', tasks=True, task_capacity=8,
                        console=False, image_data=[(0xd0000, inputs),
                            (0xe0000, bytes([0xa5]) * (output_size + 32))])
        report.update(build=program['build'], emulator_sha256=sha256(BRIDGE/'AltirraBridgeServer'))
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROM, PIN)
            try:
                report['runtime'], _ = execute(bridge, program, timeout=180, frame_limit=12000)
            except Exception:
                print('Layers checks', data(bridge, program['image'], 'checks', True), flush=True)
                raise
            ownership(bridge, program, program['output'])
            raw = bridge.memdump(0xe0000, output_size + 32)
            require(raw[:16] == raw[-16:] == bytes([0xa5])*16, 'Output guards changed')
            for index, (base, cut, clip) in enumerate(rows):
                at = 16 + index * 68
                check_region(raw[at:at+34], base, cut)
                check_region(raw[at+34:at+68], base, cut, clip)
            report['checks'] = data(bridge, program['image'], 'checks', True)[0]
            report['geometry_cases'] = data(bridge, program['image'], 'geometryCases', True)[0]
            require(report['geometry_cases'] == len(rows), 'Missing emitted geometry cases')
            (out/'regions.bin').write_bytes(raw)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Layers passed', mode, report['checks'], 'checks', flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.mode)
