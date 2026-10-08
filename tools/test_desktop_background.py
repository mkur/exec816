#!/usr/bin/env python3
"""Check sparse/full background repair and observe production drawing boundaries.

The optional old painter is a test-only module override for matched comparisons.
Breakpoints read fill packets; passive PC traces count uploads and launches.
Neither observer inserts instructions or storage into the executable.
"""
import argparse
import json
import os
import shutil
from bisect import bisect_right
from pathlib import Path

import adapter_state as adapter
from bitmap_console_performance import native_markers
from build_bitmap_console import build_bitmap
from console_turn_profile import markers, flat_markers, analyze_events
from dos_concurrent_trace import call_marker
from gem_render_oracle import Raster, font_bytes
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from sio_transaction_trace import BASE_HZ, read_events
from stack_budget import stack_usage
from test_desktop_presentation import desktop, rectangle, frame, text, menu_bar
from test_dos_stack import execute, ownership
from test_gem_cursor import overlay
from test_gem_interactive import pixels
from test_mouse_observe import BRIDGE, ROM, PIN


BOUNDS = (31, 29, 191, 109)
CLIENT = (39, 45, 183, 101)
DAMAGE = [(40, 46, 70, 56), (56, 52, 82, 64), (32, 99, 44, 108),
          (38, 32, 98, 40), (176, 97, 190, 107)]
NAMES = ('empty desktop', 'first empty client', 'five retained commands',
         'shortened label', 'focus title', 'overlapping sparse damage',
         'full repaint', 'short title and empty black client', 'closed',
         'long retained text and title', 'vertically clipped long repair',
         'closed after text continuation', 'minimum-width long title',
         'minimum-width empty title', 'closed minimum window')


def scene(stage, font):
    raster = Raster(font)
    desktop(raster)
    if 2 <= stage <= 8:
        frame(raster, BOUNDS, b'X' if stage == 8 else b'Background',
              5 <= stage <= 7, 0 if stage == 8 else 3, close=True)
        if 3 <= stage <= 7:
            for bounds, pen in [((3, 3, 45, 15), 5), ((90, 3, 134, 7), 6),
                                ((101, 11, 133, 17), 7), ((110, 31, 139, 49), 9)]:
                left, top, right, bottom = bounds
                rectangle(raster, (39+left, 45+top, 39+right, 45+bottom), pen)
            text(raster, 42, 64, b'Long label' if stage == 3 else b'OK', bg=3)
    if stage in (10, 11):
        frame(raster, (17, 19, 623, 99), b'A long title across paint steps',
              False, 3, close=True)
        text(raster, 28, 38, bytes(65+i % 26 for i in range(70)), bg=3)
        rectangle(raster, (575, 39, 604, 45), 5)
    if stage in (13,14):
        frame(raster,(575,193,607,225),b'Minimum title' if stage==13 else b'',True,close=True)
    menu_bar(raster, b'Background' if 5 <= stage <= 7 else
             b'Minimum title' if stage==13 else b'' if stage==14 else b'Desktop')
    return overlay(raster, (320, 120))


def pixel_set(bounds):
    left, top, right, bottom = bounds
    return {(x, y) for y in range(top, bottom) for x in range(left, right)}


def check_fills(rows):
    client = pixel_set(CLIENT)
    first = rows[1]['fills']
    backgrounds = [f for f in first if f['pen'] == 3]
    require(backgrounds, 'Missing empty-client background')
    require(set().union(*(pixel_set(f['bounds']) for f in backgrounds)) == client,
            'Client background does not cover every pixel')
    require(sum(len(pixel_set(f['bounds'])) for f in backgrounds) == len(client),
            'Duplicate empty-client background pass')
    require(all(not (pixel_set(f['bounds']) & client) for f in first if f['pen'] != 3),
            'Frame background overwrites client pixels')
    allowed = set().union(*(pixel_set(r) for r in DAMAGE))
    require(rows[5]['fills'], 'Missing sparse repair')
    require(all(pixel_set(f['bounds']) <= allowed for f in rows[5]['fills']),
            'Sparse fill escaped its damage clips')


def run(out, replay=False, painter=None, observe=True):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    require(not (replay and painter), 'A painter override requires a fresh build')
    override = out/'program/deskpaint.act'
    if painter:
        override.parent.mkdir(exist_ok=True)
        override.write_text(painter.read_text())
    elif not replay:
        require(not override.exists(), 'Use a fresh output directory without an old painter')
    p = read_build(out/'program') if replay else build_bitmap(
        ROOT/'tests/programs/desktop_background.act', out, desktop=True)
    require(p['build']['optimize'], 'Rendering checks use optimized code')
    foreign = json.loads((out/'c-image.json').read_text())
    definitions = markers(p, foreign, out/'drawing')
    definitions['spans'].update(native_markers(p, [('DESKPAINT_PAINTSTRIP', 'paint_strip'),
                                                 ('DESKINPUT_SERVICE', 'input_service')]))
    points = flat_markers(definitions)
    points.update({name: foreign['symbols'][name] for name in ('start', '_VbxeUpload', '_VbxeTextUpload')})
    points['drawing_call'] = p['labels']['console_bitmap_call']
    copies = [foreign['symbols'][name] for name in
              ('GemDrawingCopy', 'GemDrawingCopyStart', 'GemDrawingScrollStart')]
    points.update({f'copy_{i}': pc for i, pc in enumerate(copies)})
    # The bridge only sets bank-zero PC breakpoints. Observe the existing
    # FindTask gateway called by Display.OwnerEnter while a drawing packet is live.
    # A fill can validate ownership several times; correlate samples with the
    # passive drawing-call trace instead of counting gateway crossings as fills.
    find_caller = call_marker(p, 'M_DISPLAY_OWNERENTER_', 'tasks_find_task', after=True)
    # @s and REGS expose only S8; @ra uses the complete native S internally.
    # Reject an ambiguous low-word return before relying on that expression.
    needle = b'\x22'+p['labels']['tasks_find_task'].to_bytes(3, 'little')
    callers = [segment['address']+i+4 for segment in p['image']['segments']
               for i in range(len(segment['bytes'])-3)
               if bytes(segment['bytes'][i:i+4]) == needle]
    require([pc for pc in callers if pc & 65535 == find_caller & 65535] == [find_caller],
            'Ambiguous FindTask return address')
    environment = ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS')
    saved_env = {key: os.environ.get(key) for key in environment}
    for key in environment:
        os.environ.pop(key, None)
    if observe:
        os.environ['EXEC816_LATENCY_TRACE'] = '1'
        os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{v:x}' for v in set(points.values()))
    report = dict(slice='DR4', tier='development', qualification=False, status='running',
                  observer=observe, painter_override=sha256(override) if override.exists() else None,
                  build_sha256=sha256(out/'program/build.json'), xex_sha256=sha256(p['xex']), scenes=[])
    at = lambda name: next(d['address'] for d in p['image']['data']
                           if '_BACKGROUNDTEST_'+name.upper()+'_' in d['name'])
    packet = foreign['symbols']['ConsoleBitmapPacket']
    abi = json.loads((ROOT/'abi/console-bitmap.json').read_text())
    fields = abi['fields']
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
                    'Unpinned emulator')
            report['machine'] = verify_machine(b, ROM, PIN)
            def before(b):
                if observe:
                    b.profile_start()
                previous = b.eval_expr('@clk') & 0xffffffff
                for stage, name in enumerate(NAMES, 1):
                    fills = []
                    marker = p['labels']['native_nmi']
                    condition = f'dw(${at("checkpoint"):x})={stage}'
                    b.bp_clear_all()
                    b.bp_set(marker, condition=condition)
                    b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                    call = p['labels']['tasks_find_task']
                    if observe and stage > 1:
                        b.bp_set(call, condition=
                                 f'(@ra=${find_caller & 65535:x})&'
                                 f'(dw(${packet:x})={abi["operations"]["FILL"]})')
                    original = b.regs
                    def registers():
                        value = original()
                        pc = int(value['PC'].lstrip('$'), 16)
                        if pc == p['labels']['done']:
                            require(b.peek16(adapter.STATE) == 65535,
                                    'Desktop stopped: '+str(b.peek16(adapter.STATE)))
                        if observe and stage > 1 and pc == call:
                            raw = b.memdump(packet, fields['background']+2)
                            word = lambda key: int.from_bytes(raw[fields[key]:fields[key]+2], 'little')
                            require(word('operation') == abi['operations']['FILL'], 'Wrong fill stop')
                            x, y, width, height = (word(k) for k in ('x', 'y', 'width', 'height'))
                            fills.append(dict(cycle=b.eval_expr('@clk') & 0xffffffff,
                                              bounds=[x, y, x+width, y+height], pen=word('background')))
                            b.resume()
                        return value
                    b.regs = registers
                    try:
                        run_to(b, marker, condition=condition, frame_limit=12000, timeout=180)
                    finally:
                        b.regs = original
                    end = b.eval_expr('@clk') & 0xffffffff
                    folder = out/f'stage-{stage}'
                    folder.mkdir(exist_ok=True)
                    report['scenes'].append(dict(stage=stage, name=name, begin_cycle=previous, end_cycle=end,
                        settled_ms=((end-previous) & 0xffffffff)/BASE_HZ*1000, fills=fills,
                        fill_pixels=sum((f['bounds'][2]-f['bounds'][0])*(f['bounds'][3]-f['bounds'][1]) for f in fills),
                        pixels=pixels(b, folder, scene(stage, font_bytes(out/'selected/src/vdi/font8x8.c')))))
                    previous = end
                    b.memload(at('gate'), stage.to_bytes(2, 'little'))
                b.bp_clear_all()
            report['runtime'], _ = execute(b, p, before_run=before, frame_limit=20000, timeout=180)
            ownership(b, p, p['output'])
            if observe:
                b.profile_stop()
            report['checks'] = b.peek16(at('checks'))
            report['stack_usage'] = stack_usage(b, p['build']['memory'])
            require(all(v['remaining_above_floor'] > 0 for v in report['stack_usage'].values()),
                    'Presenter stack floor')
        if observe:
            trace = out/'background-trace.log'
            shutil.copy2(out/'emulator.log', trace)
            events = read_events(trace)
            profile = analyze_events(events, definitions)
            (out/'worker-profile.json').write_text(json.dumps(profile, indent=2)+'\n')
            calls = [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == points['drawing_call']]
            for row in report['scenes']:
                align = lambda t: t+round((events[0][0]-t)/(1 << 32))*(1 << 32)
                start, end = align(row['begin_cycle']), align(row['end_cycle'])
                fills = {}
                for sample in row['fills']:
                    index = bisect_right(calls, align(sample['cycle']))-1
                    require(index >= 0 and calls[index] >= start, 'Uncorrelated fill sample')
                    if index in fills:
                        require(fills[index]['bounds'] == sample['bounds'] and
                                fills[index]['pen'] == sample['pen'], 'Fill packet changed during drawing')
                    else:
                        fills[index] = sample
                row['fill_gateway_samples'] = len(row['fills'])
                row['fills'] = list(fills.values())
                row['fill_pixels'] = sum((f['bounds'][2]-f['bounds'][0])*(f['bounds'][3]-f['bounds'][1])
                                         for f in row['fills'])
                hits = [int(e[4], 16) for t, e in events if e[0] == 'cpu' and start <= t < end]
                paint = [s for s in profile['routine_spans'] if s['kind'] == 'paint_strip'
                         and start <= s['start'] < s['end'] <= end]
                row.update(fill_calls=len(row['fills']), fill_packed_equivalent_bytes=row['fill_pixels']/2,
                           launches=hits.count(points['start']),
                           raw_uploads=hits.count(points['_VbxeUpload']),
                           text_uploads=hits.count(points['_VbxeTextUpload']),
                           async_launches=hits.count(p['labels']['blitter_launched']),
                           painter_calls=len(paint),
                           painter_cpu_ms=sum(s['charged_cpu_ms'] for s in paint),
                           painter_max_cpu_ms=max((s['charged_cpu_ms'] for s in paint), default=0),
                           painter_elapsed_ms=sum(s['elapsed_ms'] for s in paint))
                if row['stage'] > 1:
                    require(not any(pc in hits for pc in copies) and row['async_launches'] == 0,
                            'Unexpected surface copy in retained repaint fixture')
                    row['surface_copy_bytes'] = 0
                if row['stage'] in (10, 11) and not override.exists():
                    require(row['painter_max_cpu_ms'] <= 20, 'Long-text step exceeded 20 ms CPU')
                    services = [s['start'] for s in profile['routine_spans'] if s['kind'] == 'input_service']
                    for left, right in zip(paint, paint[1:]):
                        require(any(left['end'] < tick < right['start'] for tick in services),
                                'Retained text skipped its input boundary')
            if not override.exists():
                check_fills(report['scenes'])
        report.update(status='pass', memory_delta=dict(bank_zero=dict(fixed=0, root_kernel=0,
                      per_public_task=[0]*8, idle=0), upper_ram=0, vram=0),
                      scope='Whole scanout bytes against independent retained pixels. Fill counts are native explicit fills only; packed-equivalent bytes count two pixels per byte, not nibble-edge bus traffic. Launches include glyph/overlay lists. Painter CPU excludes native IRQ and off-Task time; settled time includes two PAL frames, not DMA duration.')
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        name = 'background-results.json' if observe else 'background-control.json'
        (out/name).write_text(json.dumps(report, indent=2)+'\n')
    print('Desktop backgrounds passed', report['checks'], flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--painter', type=Path, help='Test-only baseline painter source')
    parser.add_argument('--unobserved', action='store_true')
    args = parser.parse_args()
    run(args.output, args.replay, args.painter, not args.unobserved)
