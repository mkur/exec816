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
from generate_layers import layout

INPUT_FILES = ('abi/layers.json', 'lib/display/layertypes.act',
               'lib/display/regions.act', 'lib/display/layers.act',
               'lib/display/layers-update.inc', 'tests/programs/layers-damage-checks.inc', 'tools/generate_layers.py',
               'tools/test_layers.py', 'tests/programs/native_layers.act',
               'tests/programs/layers-paint.inc',
               'tests/programs/layers-update-checks.inc',
               'tests/programs/layers-bank-checks.inc',
               'tests/programs/layers-external-checks.inc')


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


def scene_commands():
    # op, client handle slot, four signed operands, expected status
    def cmd(op=0, slot=0, a=0, b=0, c=0, d=0, status=0):
        return op, slot, a, b, c, d, status
    return [cmd(), cmd(1, 1, 0, 0, 24, 20), cmd(2, 1, 1), cmd(7, 1),
            cmd(1, 2, 8, 4, 32, 24), cmd(2, 2, 1), cmd(7, 1),
            cmd(1, 3, 4, 8, 20, 16), cmd(2, 3, 1),
            cmd(1, 4, 12, 0, 16, 24), cmd(2, 4, 1),
            cmd(6, 1, 10, 2, 18, 14),
            cmd(1, 5, 0, 0, 8, 24, status=2),
            cmd(3, 1, 1), cmd(5, 1, 4, 2), cmd(2, 3, 0),
            cmd(6, 3, 4, 8, 20, 16), cmd(5, 3, 0, 0),
            cmd(2, 3, 1), cmd(3, 1, 0),
            cmd(4, 2), cmd(1, 5, 0, 0, 8, 24), cmd(2, 5, 1),
            cmd(5, 5, 24, 0), cmd(4, 2, status=7),
            cmd(5, 1, -1, 0, status=1), cmd(5, 1, 32767, 0, status=1),
            cmd(2, 5, 1), cmd(3, 5, 1), cmd(5, 5, 24, 0),
            cmd(2, 5, 2, status=1), cmd(3, 5, 2, status=1)]


def scene_oracle(commands, include_raster=False):
    layers, handles, order = {}, {}, []
    next_id, rebuilds = 1, 1
    snapshots = []
    for op, slot, a, b, c, d, status in commands:
        if status == 0 and op:
            if op == 1:
                ident = next_id
                next_id += 1
                handles[slot] = ident
                layers[ident] = dict(bounds=(a, b, c, d), shown=False,
                                     model=bytearray((i+ident*17) & 127 for i in range(768)))
                order.insert(0, ident)
            else:
                ident = handles[slot]
                layer = layers[ident]
                if op == 2 and layer['shown'] != bool(a):
                    layer['shown'] = bool(a)
                    rebuilds += 1
                elif op == 3:
                    position = 0 if a else len(order)-1
                    if order.index(ident) != position:
                        order.remove(ident)
                        order.insert(position, ident)
                        rebuilds += int(layer['shown'])
                elif op == 4:
                    rebuilds += int(layer['shown'])
                    del layers[ident]
                    order.remove(ident)
                elif op == 5:
                    l, t, r, bottom = layer['bounds']
                    if (l, t) != (a, b):
                        layer['bounds'] = (a, b, a+r-l, b+bottom-t)
                        rebuilds += int(layer['shown'])
                elif op == 6:
                    l, t, r, bottom = layer['bounds']
                    for y in range(bottom-t):
                        for x in range(r-l):
                            if contains((a, b, c, d), x+l, y+t):
                                layer['model'][y*32+x] = 80+slot
                elif op == 7:
                    l, t, r, bottom = layer['bounds']
                    for y in range(bottom-t-1):
                        layer['model'][y*32:y*32+r-l] = layer['model'][(y+1)*32:(y+1)*32+r-l]
                    start = (bottom-t-1)*32
                    layer['model'][start:start+r-l] = bytes([77])*(r-l)
        pixels = bytes(next((i for i in order if layers[i]['shown'] and
                             contains(layers[i]['bounds'], x, y)), 0)
                       for y in range(24) for x in range(32))
        if include_raster:
            raster = bytes(layers[ident]['model'][(index//32-layers[ident]['bounds'][1])*32
                +index%32-layers[ident]['bounds'][0]] if ident else 0
                for index, ident in enumerate(pixels))
            snapshots.append((rebuilds, pixels, raster))
        else:
            snapshots.append((rebuilds, pixels))
    return snapshots


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


def check_bank_scene(raw):
    records = layout()
    require(raw[:16] == raw[-16:] == bytes([0xa5])*16, 'Bank-crossing scene guards changed')
    scene = raw[16:-16]
    pixels = bytearray([255])*(640*240)
    expected = bytearray(640*240)
    bounds = [(64, 40, 192, 80), (256, 96, 384, 136),
              (448, 152, 576, 192), (160, 168, 288, 216)]
    for ident, (l, t, r, b) in enumerate(bounds, 1):
        for y in range(t, b):
            expected[y*640+l:y*640+r] = bytes([ident])*(r-l)
    counts = []
    for slot in range(5):
        at = records['Scene']['fields']['items'] + slot*records['Layer']['size']
        ident, = struct.unpack_from('<I', scene, at)
        require(ident == (slot+1 if slot < 4 else 0), 'Cross-bank identity changed')
        at += records['Layer']['fields']['visible']
        count, = struct.unpack_from('<H', scene, at)
        require(0 < count <= 81, 'Cross-bank region count')
        counts.append(count)
        for index in range(count):
            l, t, r, b = struct.unpack_from('<4h', scene, at+2+index*8)
            require(0 <= l < r <= 640 and 0 <= t < b <= 240, 'Cross-bank geometry')
            for y in range(t, b):
                row = slice(y*640+l, y*640+r)
                require(pixels[row] == bytes([255])*(r-l), 'Cross-bank visibility overlap')
                pixels[row] = bytes([ident])*(r-l)
    require(pixels == expected, 'Cross-bank full-screen oracle failed')
    return dict(address=0x11fff0, bytes=len(scene), region_counts=counts,
                pixels_checked=len(pixels))


def check_damage_batches(raw):
    require(raw[:16] == raw[-16:] == bytes([0xa5])*16, 'Damage stream guards changed')
    cuts = [(40+i*128, 20+i*40, 80+i*128, 40+i*40) for i in range(4)]
    total = 0
    for batch in range(8):
        expected = {(x,y) for y in range(232+batch) for x in range(batch,640)
                    if not any(contains(cut,x,y) for cut in cuts)}
        at = 16+batch*layout()['Region']['size']
        count, = struct.unpack_from('<H', raw, at)
        require(0 < count <= 96, 'Damage batch overflow')
        actual = set()
        for i in range(count):
            l,t,r,b = struct.unpack_from('<4h', raw, at+2+i*8)
            require(0 <= l < r <= 640 and 0 <= t < b <= 240, 'Damage extent')
            pixels = {(x,y) for y in range(t,b) for x in range(l,r)}
            require(not actual & pixels, 'Duplicate visibility within a batch')
            actual |= pixels
        require(actual == expected, 'Independent damage/visibility coverage: '+str(batch))
        total += count
    require(total > 96, 'Missing streamed product-capacity case')
    return dict(batches=8, fragments=total, independent_pixel_union=True)


def run(out, mode):
    out.mkdir(parents=True, exist_ok=True)
    rows = geometry_cases()
    inputs = struct.pack('<H', len(rows)) + b''.join(
        struct.pack('<12h', *base, *cut, *clip) for base, cut, clip in rows)
    output_size = len(rows) * 68
    commands = scene_commands()
    scene_input = struct.pack('<H', len(commands)) + b''.join(
        struct.pack('<BB4hH', *cmd) for cmd in commands)
    scene_size = len(commands)*1540
    report = dict(status='running', tier='development', mode=mode,
                  inputs={p: sha256(ROOT/p) for p in INPUT_FILES},
                  bank_zero_delta=dict(fixed=0, root_kernel=0, per_task=[0]*8, idle=0))
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
                'Unpinned Layers emulator')
        program = build(compiler(ROOT/'build/actionc'),
                        ROOT/'tests/programs/native_layers.act', out/'program',
                        optimize=mode == 'opt', tasks=True, task_capacity=8,
                        console=False, image_data=[(0xd0000, inputs),
                            (0xd2000, scene_input),
                            (0xe0000, bytes([0xa5]) * (output_size + 32)),
                            (0xf0000, bytes([0xa5]) * (scene_size + 32)),
                            (0xe4000, bytes([0xa5]) * (8*layout()['Region']['size']+32)),
                            (0x11ffe0, bytes([0xa5]) * (layout()['Scene']['size'] + 32))])
        routines = [r for r in program['image']['routines']
                    if r['name'].startswith(('M_LAYERS_', 'M_REGIONS_'))]
        globals_ = [d for d in program['image']['data']
                    if d['name'].startswith(('M_LAYERS_', 'M_REGIONS_'))]
        require(not globals_, 'Layers introduced mutable global storage')
        report.update(build=program['build'], emulator_sha256=sha256(BRIDGE/'AltirraBridgeServer'),
                      rom_sha256=sha256(ROM), library=dict(code_bytes=sum(r['size'] for r in routines),
                      max_local_stack_peak=max(r['local_stack_peak'] for r in routines),
                      mutable_global_bytes=0, scene_bytes=layout()['Scene']['size']),
                      bank_zero_budget=program['build']['memory']['bank_zero_budget'])
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROM, PIN)
            try:
                report['runtime'], _ = execute(bridge, program, timeout=180, frame_limit=12000)
            except Exception:
                print('Layers checks', data(bridge, program['image'], 'checks', True), flush=True)
                print('Scene cases/size/phase', [data(bridge, program['image'], name, True)
                      for name in ('sceneCases', 'sceneSize', 'scenePhase')], flush=True)
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
            scenes = bridge.memdump(0xf0000, scene_size+32)
            require(scenes[:16] == scenes[-16:] == bytes([0xa5])*16, 'Scene guards changed')
            for index, (rebuilds, pixels, raster) in enumerate(scene_oracle(commands, True)):
                at = 16+index*1540
                require(scenes[at:at+4] == struct.pack('<I', rebuilds),
                        f'Unexpected visibility rebuild at scene {index}')
                require(scenes[at+4:at+772] == pixels, f'Independent scene oracle failed: {index}')
                require(scenes[at+772:at+1540] == raster,
                        f'Incremental damage paint differs from full recomposition: {index}')
            report['scene_cases'] = data(bridge, program['image'], 'sceneCases', True)[0]
            require(report['scene_cases'] == len(commands), 'Missing scene cases')
            for name in ('paints', 'copies', 'redraws', 'maxRects', 'maxPaintRects'):
                report[name] = data(bridge, program['image'], name, True)[0]
                require(report[name] > 0, 'Missing drawing path: '+name)
            (out/'scenes.bin').write_bytes(scenes)
            bank_scene = bridge.memdump(0x11ffe0, layout()['Scene']['size']+32)
            damage = bridge.memdump(0xe4000, 8*layout()['Region']['size']+32)
            report['damage_batches'] = check_damage_batches(damage)
            (out/'damage-batches.bin').write_bytes(damage)
            report['bank_crossing'] = check_bank_scene(bank_scene)
            (out/'bank-scene.bin').write_bytes(bank_scene)
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
