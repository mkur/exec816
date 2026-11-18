#!/usr/bin/env python3
"""Measure horizontal scrollbar arrows on a frozen MGVIEW-only demo."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from c_program import ABI
from console_turn_profile import Timeline, analyze_events
from desktop_mouse import slow_schedule
from filesystem_audit import Audit
from g4bench_trace import calls
from gem_applications import MODELS, instances
from gem_render_oracle import font_bytes
from make_data_disk import make
from measure_mgview import definition, expected
from mgview_frame_trace import geometry
from mgview_text_trace import linked_section, source_point
from native_program import read_build, require, sha256, verify_machine
from os_boundary import emulator
from sio_transaction_trace import BASE_HZ, read_events
from stack_budget import stack_usage
from test_dos_stack import execute, ownership
from test_gem_acceptance import Session, bootstrap
from test_mouse_observe import BRIDGE, PIN


def app_disk(bundle, output, demo, app_directory, fixture):
    """Stage a writable development volume from the frozen image's exact files."""
    original = Audit((bundle/demo['media']).read_bytes())
    original.sdfs()
    files = {**original.files, 'C/MGVIEW.APP': (app_directory/'program.app').read_bytes()}
    if fixture:
        long_line = (b'0123456789ABCDEFGHIJ'*15)
        files['MGVIEW.TXT'] = (b'A\0B\tNUL and tab\r\n\r\nshort\r'
                              + b'\t'*6 + b'visible after tabs\n' + long_line + b'\r\n'
                              + (b'WWMMijjW'*34 + b'\r\n')*6
                              + (b'\t'*6 + b'damage through tabs\r\n')*6 + b'unterminated')
        files['COVER.TXT'] = b'Adjacent cover\r\npreserve me\r\n'
        startup = files['S/STARTUP']
        require(startup.count(b'SYS:MGVIEW.TXT') == 1, 'Missing single-viewer startup')
        files['S/STARTUP'] = startup.replace(b'SYS:MGVIEW.TXT', b'SYS:MGVIEW.TXT SYS:COVER.TXT')
    label = original.image.sector(1)[22:30].decode('ascii').rstrip()
    image = output/'system.atr'
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        media = Path(temporary)
        for name, data in files.items():
            target = media/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        make(image, media, binary_names=files, sectors=demo['system_sectors'],
             sector_bytes=demo['sector_bytes'], label=label)


def screen(bridge, path, work, track):
    frame = bridge.rawscreen(str(path))
    raw = path.read_bytes()

    def pixels(rect, bgr=False):
        x, y, w, h = rect
        start = (x + 16) * 4
        rows = [raw[row*frame.stride+start:row*frame.stride+start+w*4]
                for row in range(y, y+h)]
        if bgr:
            return b''.join(row[i:i+3] for row in rows for i in range(0, len(row), 4))
        return hashlib.sha256(b''.join(rows)).hexdigest()

    return pixels(work, bgr=True), pixels(track)


def add_trace(report, output, markers, base):
    events = read_events(output/'emulator.log', kinds={'cpu'})
    points = markers['timeline']['points']
    while events and int(events[-1][1][4], 16) in (points['native_irq'], points['native_nmi']):
        events.pop()
    profile = analyze_events(events, markers['timeline'], include_segments=True)
    delta = base - (ABI['link_bank'] << 16)
    entries = {**markers['entries'], **markers['text']['entries'],
               **{pc+delta: name for pc, name in markers['app_entries'].items()}}
    returns = set(markers['returns']) | {pc+delta for pc in markers['app_returns']}
    exits = set(markers['exits']) | {pc+delta for pc in markers['app_exits']}
    shifts = {pc for pc, name in entries.items() if name == 'set_shift'}
    dps = {int(e[9], 16) for _, e in events if int(e[4], 16) in shifts}
    require(len(dps) == 1, 'Missing unique scrolling Task')
    dp = dps.pop()
    timeline = Timeline(profile['segments'], dp)
    spans, _ = calls(events, entries, returns, dp, exits)
    for sample in report['samples']:
        if not sample['traced']:
            continue
        start = sample['start'] + round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
        end = start + (sample['end']-sample['start']) % (1<<32)
        selected = [s for s in spans if start <= s['start'] < s['end'] <= end]
        counts = Counter(s['kind'] for s in selected)
        require(counts['set_shift'] == counts['vro_cpyfm'] == counts['_my_draw'] == 1,
                'Expected one incremental scroll')
        require(counts['DisplayEnter'] == counts['DisplayLeave'], 'Unbalanced display grants')
        count_names = ('expand_line', 'get_line', 'v_gtext', 'DisplayEnter',
                       'VbxeOwnerCopyRect', 'VbxeOwnerSubmit', 'VbxeOwnerFence', 'vr_recfl')
        sample['calls'] = {name: counts[name] for name in count_names}

        def total(rows):
            measured = [timeline.measure(s['start'], s['end']) for s in rows]
            return {key: sum(m[key] for m in measured)
                    for key in ('charged_cpu_ms', 'elapsed_ms', 'off_cpu_ms', 'interrupt_ms')}

        phase_names = ('set_shift', 'vro_cpyfm', '_my_draw', 'get_line', 'expand_line',
                       'v_gtext', 'VDI_paint', 'vr_recfl', 'window_calc_slider', 'wind_update')
        phases = {name: total(s for s in selected if s['kind'] == name) for name in phase_names}
        updates = [s for s in selected if s['kind'] == 'wind_update']
        phases['end_update'] = total(updates[-1:])
        conversion = []
        opening = None
        for tick, row in events:
            if not start <= tick <= end or int(row[9], 16) != dp:
                continue
            name = markers['text']['points'].get(int(row[4], 16))
            if name == 'convert_begin':
                require(opening is None, 'Overlapping conversion intervals')
                opening = tick
            elif name == 'convert_end':
                require(opening is not None, 'Missing conversion entry')
                conversion.append(dict(start=opening, end=tick))
                opening = None
        require(opening is None and len(conversion) >= counts['v_gtext'],
                'Missing conversion intervals')
        phases['vdi_input_conversion'] = total(conversion)
        sample['inclusive_phases'] = phases
        lengths = [s['return_a'] for s in selected if s['kind'] == 'expand_line']
        require(sum(length > 0 for length in lengths) <= counts['v_gtext'] <= len(lengths),
                'Prepared strings differ from emitted text calls')
        # Each expand result belongs to exactly one row. The draw submits its
        # NUL-terminated output directly, with or without an empty-row call.
        sample['glyphs_prepared'] = sample['glyphs_submitted'] = sum(lengths)
        draw = next(s for s in selected if s['kind'] == '_my_draw')
        sample['strip_calls'] = dict(Counter(s['kind'] for s in selected
            if draw['start'] <= s['start'] < s['end'] <= draw['end']))
        # Both driver upload routines feed one list per invocation. This
        # includes text lists that bypass the generic VbxeOwnerSubmit entry.
        uploads = [tick for tick, row in events if start <= tick <= end and
                   int(row[9], 16) == dp and int(row[4], 16) in markers['list_uploads']]
        sample['blitter_lists'] = len(uploads)
        sample['strip_blitter_lists'] = sum(draw['start'] <= t <= draw['end'] for t in uploads)


def trace_definition(cache, program, foreign, app):
    markers = definition(cache, program, foreign, app, ('get_line', 'expand_line'))
    listing = (cache/'drawing/24-vdi.lst').read_text()
    address, section = linked_section(foreign, listing, 'text')
    paint, _ = linked_section(foreign, listing, 'paint')
    markers['text'] = dict(entries={paint: 'VDI_paint'}, points={
        address+source_point(section, 'count=0;'): 'convert_begin',
        address+source_point(section, 'if (!count) break;'): 'convert_end'})
    markers['list_uploads'] = {foreign['symbols'][name] for name in ('_VbxeUpload', '_VbxeTextUpload')}
    markers['pcs'] = sorted(set(markers['pcs']) | set(markers['text']['points']) |
                            markers['list_uploads'] | {paint})
    return markers


def run(bundle, output, app_directory=None, *, trace=False, fixture=False):
    output.mkdir(parents=True, exist_ok=True)
    cache = bundle/'bitmap-console'
    if app_directory:
        cache = output/'cache'
        (cache/'apps').mkdir(parents=True, exist_ok=True)
        links = {'apps/mgview': app_directory}
        links.update({name: bundle/'bitmap-console'/name
                      for name in ('selected', 'drawing', 'c-image.json')})
        for name, target in links.items():
            link = cache/name
            if not link.is_symlink():
                link.symlink_to(target)
            require(link.resolve() == target, 'Output directory already uses a different build')
    program = read_build(bundle)
    foreign_path = cache/'c-image.json'
    foreign = json.loads(foreign_path.read_text())
    app = json.loads((cache/'apps/mgview/app.json').read_text())
    for key in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE'):
        os.environ.pop(key, None)
    if trace:
        markers = trace_definition(cache, program, foreign, app)
        os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in markers['pcs'])
    rom = bundle/'of816/altirraos-816.rom'
    demo = json.loads((bundle/'demo-manifest.json').read_text())
    atr = output/'system.atr'
    if app_directory:
        app_disk(bundle, output, demo, app_directory, fixture)
    else:
        shutil.copyfile(bundle/demo['media'], atr)
    files = Audit(atr.read_bytes())
    files.sdfs()
    content = files.files['MGVIEW.TXT']
    require(hashlib.sha256(files.files['C/MGVIEW.APP']).hexdigest() == app['sha256'],
            'Disk APP differs from the observer listings')
    report = dict(status='running', tier='development', native_sha256=sha256(program['xex']),
                  provider_sha256=foreign['provenance']['elf_sha256'], app_sha256=app['sha256'],
                  provider_manifest_sha256=sha256(foreign_path), app_minimum_stack=app['minimum_stack'],
                  document_sha256=hashlib.sha256(content).hexdigest(), samples=[],
                  sample_clock='PAL VBI, first matching completed viewport and track frames')
    font = font_bytes(cache/'selected/src/vdi/font8x8.c')
    MODELS['mgview'] = ('nwindows', 0, 0)

    def viewer(bridge):
        session = Session(bridge, program, cache, output, report)
        bridge._cmd_ok('KEY ALL up')
        bridge._cmd_ok('MOUSE ST')
        documents = 2 if fixture else 1
        for _ in range(40):
            session.frames(200)
            found = [row for row in instances(bridge, program, cache) if row['name'] == 'mgview']
            if len(found) == 1 and session.number(found[0]['symbols']['nwindows'], 2) == documents:
                break
        else:
            raise RuntimeError('MGVIEW did not open the startup document')
        symbols = found[0]['symbols']
        report['loaded_base'] = (symbols['set_shift'] - app['image']['symbols']['set_shift']
                                 + (ABI['link_bank'] << 16))
        window = session.number(symbols['windows'])
        session.frames(60)
        def rect(record, offset):
            return tuple(session.number(record+offset+i*2, 2) for i in range(4))

        work = rect(window, 268)
        report['work'] = work
        frame_objects = (0, 7, 8, 9, 10, 11, 12, 13, 14)

        def frame():
            return geometry(bridge, program, window, frame_objects)

        def gadget(objs, obj):
            root, part = objs['0'], objs[str(obj)]
            return (root['x']+part['x'], root['y']+part['y'], part['width'], part['height'])

        def move_to(rect):
            x, y, w, h = rect
            for _ in range(3):
                session.move(x+w//2, y+h//2)
                session.frames(32)
                point = [session.number(session.native('DESKINPUT', 'cursor'+axis), 2)
                         for axis in ('X', 'Y')]
                if x <= point[0] < x+w and y <= point[1] < y+h:
                    return point
            raise RuntimeError('Cursor missed scrollbar: '+str(point))

        def shift(action, arrow, hshift, vshift, traced, target=None):
            track_id = 9 if arrow in (7, 8) else 13
            before_frame = frame()
            track = gadget(before_frame['objects'], track_id)
            pointer = move_to(target or gadget(before_frame['objects'], arrow))
            path = output/'current.bgra'
            _, old_thumb = screen(bridge, path, work, track)
            tabs = session.number(window+336, 2)
            want = expected(font, work, content, vshift, column=hshift, tabs=tabs)
            bridge.bp_clear_all()
            start = bridge.eval_expr('@clk') & 0xffffffff
            bridge._cmd_ok('MOUSE AT 2000 0 0 1')
            bridge._cmd_ok('MOUSE AT 74000 0 0 0')
            polls = []
            for _ in range(22):
                session.frames(1)
                tick = bridge.eval_expr('@clk') & 0xffffffff
                actual, thumb = screen(bridge, path, work, track)
                polls.append((tick, actual == want, thumb))
            end = bridge.eval_expr('@clk') & 0xffffffff
            require(session.number(window+304) == hshift and session.number(window+280) == vshift,
                    'Wrong scroll shift for '+action)
            require(actual == want and thumb != old_thumb, 'Wrong settled viewport or thumb: '+action)
            field = 'vslide' if track_id == 9 else 'hslide'
            size = 'vsize' if track_id == 9 else 'hsize'
            after_frame = frame()
            shift_offset = 280 if track_id == 9 else 304
            maximum = session.number(window+shift_offset+6)
            offset = vshift if track_id == 9 else hshift
            require(maximum and after_frame['sliders'][field] == max(1, offset*1000//maximum)
                    and after_frame['sliders'][size] == before_frame['sliders'][size],
                    'Wrong resident slider state for '+action)

            def bracket(check):
                index = next(i for i, row in enumerate(polls) if check(row))
                ticks = [polls[index-1][0] if index else start, polls[index][0]]
                return [(tick-start) % (1<<32)*1000/BASE_HZ for tick in ticks]

            sample = dict(action=action, traced=traced, start=start, end=end, pointer=pointer,
                          shift=[hshift, vshift], viewport_ms=bracket(lambda row: row[1]),
                          thumb_ms=bracket(lambda row: row[2] == thumb),
                          pixel_sha256=hashlib.sha256(actual).hexdigest(),
                          thumb_sha256=thumb, slider=after_frame['sliders'][field])
            report['samples'].append(sample)
            print(action, 'traced' if traced else 'untraced',
                  'viewport', sample['viewport_ms'], 'thumb', sample['thumb_ms'], flush=True)

        def key(name, ctrl=False):
            if ctrl:
                bridge._cmd_ok('KEY CTRL down')
            bridge._cmd_ok('KEY '+name+' down')
            session.frames(3)
            bridge._cmd_ok('KEY '+name+' up')
            if ctrl:
                bridge._cmd_ok('KEY CTRL up')
            session.frames(60)

        def check_fixture():
            cover = session.number(symbols['windows']+4)
            require(cover and session.number(window+300) == 272, 'Fixture needs the capped document')
            path = output/'current.bgra'
            x, y, w, h = work
            want = expected(font, work, content, 0)

            for dx, dy in ((52, 25), (-24, 0)):
                cx, cy, cw, ch = rect(cover, 260)
                cover_frame = geometry(bridge, program, cover, (0, 2))
                mx, my = move_to(gadget(cover_frame['objects'], 2))
                bridge._cmd_ok('MOUSE AT 2000 0 0 1')
                session.frames(8)
                slow_schedule(bridge, program, (mx, my), (mx+dx, my+dy))
                session.frames(180)
                bridge._cmd_ok('MOUSE AT 2000 0 0 0')
                session.frames(45)
                session.move(632, 0)
                session.frames(40)
                nx, ny, nw, nh = rect(cover, 260)
                require(nx != cx and (nx-x) % 8 and (nx+nw+2-x) % 8,
                        f'Cover did not leave partial cells at both visible edges: {(nx,ny,nw,nh)}')
                actual, _ = screen(bridge, path, work, work)
                for yy in range(h):
                    for xx in range(w):
                        if nx <= x+xx < nx+nw+2 and ny <= y+yy < ny+nh+2:
                            continue
                        i = (yy*w+xx)*3
                        require(actual[i:i+3] == want[i:i+3],
                                f'Wrong visible fragment at {x+xx}, {y+yy}')
                cover_work = rect(cover, 268)
                cover_pixels, _ = screen(bridge, path, cover_work, cover_work)
                require(cover_pixels == expected(font, cover_work, files.files['COVER.TXT'], 0),
                        'Covered redraw altered the adjacent front window')
                report.setdefault('covered', []).append(dict(before=[cx,cy,cw,ch],
                    after=[nx,ny,nw,nh], viewport_sha256=hashlib.sha256(actual).hexdigest()))

            key('U', ctrl=True)
            require(session.number(symbols['nwindows'], 2) == 1, 'Cover did not close')
            actual, _ = screen(bridge, path, work, work)
            require(actual == want, 'Wrong exposure after closing the cover')
            key('0')
            require(session.number(window+336, 2) == 0, 'Literal tab mode did not engage')
            actual, _ = screen(bridge, path, work, work)
            require(actual == expected(font, work, content, 0, tabs=0), 'Wrong literal-tab pixels')
            report['literal_tabs_sha256'] = hashlib.sha256(actual).hexdigest()
            tx, ty, tw, th = gadget(frame()['objects'], 13)
            maximum = session.number(window+310)
            page = work[2]//8
            for column in range(page, maximum+page, page):
                shift('horizontal-page', 12, min(column, maximum), 0, False,
                      target=(tx+tw-8, ty, 8, th))

        print('Viewer ready', work, flush=True)
        report['stack_ready'] = stack_usage(bridge, program['build']['memory'])
        if fixture:
            check_fixture()
        else:
            if trace:
                bridge.profile_start()
            for _ in range(1 if trace else 3):
                shift('right', 12, 1, 0, trace)
                shift('left', 11, 0, 0, trace)
            if trace:
                bridge.profile_stop()
            else:
                shift('down', 8, 0, 1, False)
                shift('up', 7, 0, 0, False)
        report['stack_after'] = stack_usage(bridge, program['build']['memory'])
        bridge._cmd_ok('KEY CTRL down')
        bridge._cmd_ok('KEY Q down')
        bridge.bp_clear_all()

    try:
        with emulator(BRIDGE, rom, output, pin=PIN) as bridge:
            for key, value in demo['configuration'].items():
                bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
            bridge.mount(0, str(atr))
            report['machine'] = verify_machine(bridge, rom, PIN)
            bootstrap(bridge, program, bundle, bundle/'of816', report)
            result, _ = execute(bridge, {**program, 'output': output}, preloaded=True, before_run=viewer)
            bridge._cmd_ok('KEY ALL up')
            ownership(bridge, program, bundle)
            report['exit_status'] = result['status']
        if trace:
            add_trace(report, output, markers, report['loaded_base'])
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--app', type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--fixture', action='store_true',
                       help='check cover windows, literal tabs and page scrolls')
    modes.add_argument('--trace', action='store_true', help='observe one detailed arrow pair')
    args = parser.parse_args()
    if args.fixture and not args.app:
        parser.error('--fixture needs an APP build')
    run(args.bundle.resolve(), args.output.resolve(),
        args.app.resolve() if args.app else None, trace=args.trace, fixture=args.fixture)
