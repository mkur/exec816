#!/usr/bin/env python3
"""Physical session chords, retained edits, grouped panes and exact presentation."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from generate_console import constants, glyphs
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_dos_stack import execute, ownership


def run(out, bitmap=False, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 8192
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    source = ROOT/'tests/programs/console_sessions.act'
    if bitmap:
        from build_bitmap_console import build_bitmap
        from test_mouse_observe import PIN, BRIDGE, ROM
        program = read_build(out/'program') if reuse else build_bitmap(
            source, out, release_compiler=True, memory_profile=memory)
    else:
        PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
        BRIDGE, ROM = ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom'
        program = read_build(out) if reuse else build(
            compiler(ROOT/'build/actionc', release=True), source, out,
            optimize=True, tasks=True, task_capacity=8, console=True,
            dos_mounts=[], memory_profile=memory)
    if reuse:
        for group in ('task_inputs', 'console_inputs', 'banked_inputs'):
            for name, expected in program['build'].get(group, {}).items():
                path = ROOT/name
                if path.is_file():
                    require(sha256(path) == expected, 'Changed replay input: '+name)
    c = constants()
    captured = []
    with emulator(BRIDGE, ROM, out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, ROM, PIN)
        at = lambda name: next(d['address'] for d in program['image']['data']
                               if '_CONSOLESESSIONTEST_'+name.upper()+'_' in d['name'])
        byte = lambda address: b.memdump(address, 1)[0]
        storage = program['build']['memory']['console_storage']
        def reach(condition):
            b.bp_clear_all()
            b.bp_set(program['labels']['native_nmi'], condition=condition)
            b.bp_set(program['labels']['done'], condition=adapter.STOPPED)
            run_to(b, program['labels']['native_nmi'], 12000, 45, condition)
            require(b.peek16(adapter.STATE) == 65535, 'Session console stopped early')
        def frames(count=5):
            reach(f'@frame>={b.eval_expr("@frame")+count}')
        def phase(value):
            reach(f'db(${at("phase"):x})={value}')
            frames(8)
        def key(name, ctrl=False, shift=False):
            if ctrl: b._cmd_ok('KEY CTRL down')
            if shift: b._cmd_ok('KEY SHIFT down')
            b._cmd_ok(f'KEY {name} down')
            frames(4)
            b._cmd_ok(f'KEY {name} up')
            if shift: b._cmd_ok('KEY SHIFT up')
            if ctrl: b._cmd_ok('KEY CTRL up')
            frames(4)
        def ptr(address):
            return int.from_bytes(b.memdump(address, 3), 'little')
        def screen():
            # All selected rectangles must match retained cells, including caret.
            windows = storage['WINDOWS']
            expected = bytearray((80*30) if bitmap else (40*24))
            width = 80 if bitmap else 40
            views = []
            waits = []
            for slot in range(4):
                entry = windows+c['WINDOWS_ITEMS']+slot*c['WINDOW_SIZE']
                if byte(entry+c['WINDOW_STATE']) != c['WIN_LIVE']: continue
                view = ptr(entry+c['WINDOW_VIEW'])
                if not byte(view+c['PRESENTATION_VISIBLE']): continue
                instance = ptr(entry+c['WINDOW_INSTANCE'])
                cursor = b.peek16(instance+c['INSTANCE_LINESTART'])+b.peek16(instance+c['INSTANCE_COLUMN'])
                waits += [f'db(${instance+c["INSTANCE_DIRTYROWS"]:x})=0',
                          f'dw(${view+c["PRESENTATION_INDEX"]:x})={cursor}']
            if waits: reach('&'.join('('+condition+')' for condition in waits))
            # A settled model may commit after this frame's scanout passed it.
            if bitmap: frames(2)
            if bitmap:
                from gem_render_oracle import Raster, font_bytes
                raster = Raster(font_bytes(out/'selected/src/vdi/font8x8.c'))
            for slot in range(4):
                entry = windows+c['WINDOWS_ITEMS']+slot*c['WINDOW_SIZE']
                if byte(entry+c['WINDOW_STATE']) != c['WIN_LIVE']: continue
                view = ptr(entry+c['WINDOW_VIEW'])
                if not byte(view+c['PRESENTATION_VISIBLE']): continue
                instance = ptr(entry+c['WINDOW_INSTANCE'])
                cells = ptr(instance+c['INSTANCE_CELLS'])
                count = b.peek16(instance+c['INSTANCE_COUNT'])
                origin = b.peek16(instance+c['INSTANCE_CELLORIGIN'])
                w, h = b.peek16(instance+c['INSTANCE_WIDTH']), b.peek16(instance+c['INSTANCE_HEIGHT'])
                left, top = b.peek16(view+c['PRESENTATION_LEFT']), b.peek16(view+c['PRESENTATION_TOP'])
                retained = b.memdump(cells, count)
                caret = b.peek16(view+c['PRESENTATION_PREVIOUSCURSOR'])
                cursor_on = byte(view+c['PRESENTATION_CURSORON'])
                for i in range(count):
                    value = retained[(origin+i) % count]
                    if bitmap:
                        x, y = (left+i%w)*8, (top+i//w)*8
                        raster.apply(8, [x, y+6], [value])
                        if cursor_on and i == caret:
                            for column in range(8): raster.pixel(x+column, y+7, 1)
                    else:
                        value = glyphs()[value] if value < 128 else 31
                    if not bitmap and cursor_on and i == caret: value ^= 128
                    expected[(top+i//w)*width+left+i%w] = value
                views.append(dict(slot=slot, width=w, height=h, caret=caret, cursor_on=cursor_on))
            if not bitmap:
                actual = b.memdump(b.peek16(88), 960)
                require(actual == expected, 'Selected screen differs from retained model/caret')
            if bitmap:
                from test_gem_interactive import pixels
                folder = out/f'phase-{byte(at("phase"))}'
                folder.mkdir(exist_ok=True)
                pixels(b, folder, raster.packed())
            captured.append(dict(phase=byte(at('phase')), views=views,
                                 cells=expected.hex()))
        def before(b):
            b._cmd_ok('KEY ALL up')
            phase(1)
            key('A'); key('B'); key('B', ctrl=True)
            key('SPACE', ctrl=True, shift=True)
            phase(2); screen()
            key('SPACE', ctrl=True, shift=True)
            phase(3); screen()
            key('TAB')
            reach(f'db(${at("readerPhase"):x})=2')
            key('SPACE', ctrl=True, shift=True)
            phase(4); screen()
            key('SPACE', ctrl=True, shift=True)
            phase(5); screen()
            key('C'); key('RETURN')
            phase(6); screen()
            old = b.memdump(b.peek16(88), 960) if not bitmap else None
            b.memload(at('gate'), b'\1')
            phase(7); screen()
            if old is not None:
                require(b.memdump(b.peek16(88), 960) == old, 'Hidden pane close erased active view')
            b.memload(at('gate'), b'\1')
            phase(8); screen()
            b.memload(at('gate'), b'\1')
            b.bp_clear_all()
        try:
            runtime, _ = execute(b, program, before_run=before, timeout=240, frame_limit=16000)
        except Exception:
            print('Session checks/phase/reader', data(b, program['image'], 'checks', True),
                  byte(at('phase')), byte(at('readerPhase')), flush=True)
            raise
        require(data(b, program['image'], 'finished') == [1], 'Unfinished console sessions')
        ownership(b, program, program['output'])
        checks = data(b, program['image'], 'checks', True)[0]
    return dict(status='pass', tier='development', bitmap=bitmap, checks=checks,
                build=program['build'], runtime=runtime, machine=machine, snapshots=captured)


def layout(out, raw=False, lifetime=False):
    out.mkdir(parents=True, exist_ok=True)
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 8192
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    program = build(compiler(ROOT/'build/actionc', release=True),
                    ROOT/'tests/programs'/('console_key_lifetime.act' if lifetime else
                                           'console_key_layout.act'), out,
                    optimize=not raw, tasks=True, task_capacity=8,
                    console=lifetime, memory_profile=memory)
    rom = ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge', rom, out, pin=pin) as b:
        for key, value in pin['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, rom, pin)
        runtime, _ = execute(b, program, timeout=180, frame_limit=9000,
                             expected_status=4 if lifetime else 0)
        if not lifetime:
            require(data(b, program['image'], 'finished') == [1], 'Unfinished key layout')
        checks = data(b, program['image'], 'checks', True)[0]
        if not lifetime: ownership(b, program, out)
    return dict(status='pass', tier='development', group='lifetime' if lifetime else 'layout', raw=raw,
                checks=checks, build=program['build'], machine=machine, runtime=runtime)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bitmap', action='store_true')
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--layout', action='store_true')
    parser.add_argument('--raw', action='store_true')
    parser.add_argument('--lifetime', action='store_true')
    args = parser.parse_args()
    result = (layout(args.output.resolve(), args.raw, args.lifetime) if args.layout or args.lifetime else
              run(args.output.resolve(), args.bitmap, args.reuse))
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Console session checks passed', result['checks'], flush=True)
