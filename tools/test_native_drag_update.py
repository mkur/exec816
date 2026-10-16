#!/usr/bin/env python3
"""Physical native drags across Counter's timer UPDATE; no guest patches."""
import argparse
import json
import os
from pathlib import Path
import zipfile

from browser_model import FIELDS as F
from colour_desktop_model import FIELDS as D
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from gem_render_oracle import DESKTOP_PALETTE, PENS
from generate_aes_server import ABI, expected_layout, layout
from generate_desktop import layout as desktop_layout
from native_program import ROOT, require
from test_demo import run


class NativeDragUpdate:
    def __init__(self):
        self.report = dict(observations=[], pixel_checks=[])

    def exercise(self, s):
        b = s.b
        out = s.p['output']
        directory = out / 'bitmap-console'
        resident = json.loads((directory / 'c-image.json').read_text())['symbols']
        request = layout()['Request']['fields']
        colors = {hw: bytes((v & 254) + (v >> 7)
                            for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1]
                  for pen, hw in enumerate(PENS)}

        def at(module, name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_' + module + '_' + name.upper() + '_' in d['name'])

        def read(module, name, size=1):
            return s.number(at(module, name), size)

        def rectangle(address):
            return [s.number(address + i*2, 2) for i in range(4)]

        def move(x, y):
            start = [read('DESKINPUT', n, 2) for n in ('cursorX', 'cursorY')]
            point = schedule(b, s.p, start, (x, y))
            s.saved['pointer'] = point
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                         (at('DESKINPUT', 'cursorX'), point[0],
                          at('DESKINPUT', 'cursorY'), point[1]))
            s.frames(3)

        def edge(down, frames=8):
            b._cmd_ok('MOUSE AT 2000 0 0 ' + str(down))
            s.frames(frames)

        def click(x, y):
            move(x, y)
            edge(1, 25)
            edge(0, 60)

        def scan():
            frame = b.rawscreen(str(out / 'drag-scanout.bgra'))
            return (out / 'drag-scanout.bgra').read_bytes(), frame.stride

        def pixels(baseline, bounds, visible, name):
            # Compare the XOR border against the pre-press scene, independently
            # of the native/C outline flags. Exclude both pointer footprints.
            raw, stride = scan()
            old, old_stride, old_pointer = baseline
            pointer = [read('DESKINPUT', n, 2) for n in ('cursorX', 'cursorY')]
            left, top, right, bottom = bounds
            points = [(x, y) for y in (top, bottom-1) for x in range(left, right)]
            points += [(x, y) for x in (left, right-1) for y in range(top+1, bottom-1)]
            checked = 0
            for x, y in points:
                if any(px-2 <= x < px+18 and py-2 <= y < py+18
                       for px, py in (old_pointer, pointer)):
                    continue
                before = old[y*old_stride+(x+16)*4:y*old_stride+(x+16)*4+3]
                expected = {colors[hw ^ 15] for hw, rgb in colors.items() if rgb == before}
                if not visible:
                    expected = {before}
                actual = raw[y*stride+(x+16)*4:y*stride+(x+16)*4+3]
                require(actual in expected, name + ': wrong outline pixel at ' + str((x, y)))
                checked += 1
            require(checked > 300, name + ': insufficient independent border coverage')
            self.report['pixel_checks'].append(dict(name=name, visible=visible, pixels=checked))

        def baseline(x, y):
            move(x, y)
            raw, stride = scan()
            return raw, stride, list(s.saved['pointer'])

        app = context = 0

        def observe(name):
            row = dict(name=name, phase=read('DESKDRAG', 'phase'),
                       dirty=read('DESKDRAG', 'dirty'),
                       outline=read('DESKSTATE', 'outlineVisible'),
                       c_outline=s.number(resident['outlineDrawn'], 2),
                       cursor=[read('DESKINPUT', n, 2) for n in ('cursorX', 'cursorY')],
                       target=rectangle(at('DESKDRAG', 'target')),
                       buttons=read('DESKINPUT', 'buttons', 2))
            if app:
                row.update(count=s.number(app+14, 4), paints=s.number(app+18, 4),
                           status=s.number(context+request['status'], 2),
                           update=s.number(context+request['intin'], 2))
                views = context + dict(expected_layout())['C context views']
                view = next(s.number(views+i*4, 4) for i in range(ABI['constants']['WINDOWS'])
                            if s.number(views+i*4, 4))
                row['updates'] = s.number(view+layout()['WindowView']['fields']['updates'], 2)
            self.report['observations'].append(row)
            (out / 'native-drag-update-observations.json').write_text(
                json.dumps(self.report, indent=2) + '\n')
            b.screenshot(str(out / (name + '.png')))
            print(json.dumps(row), flush=True)
            return row

        def outlined(row):
            require(row['phase'] == 1 and row['outline'] == row['c_outline'] == 1,
                    row['name'] + ': captured native outline disappeared')

        def wait_update(start, name):
            # Physical travel can itself span the timer deadline. Wait for the
            # pending BEGIN, including one already queued during that travel.
            code = ABI['constants']['BEG_UPDATE'] | ABI['constants']['UPDATE_WINDOW']
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                         (context+request['status'], ABI['constants']['PENDING'],
                          context+request['intin'], code))
            s.frames(12)
            row = observe(name)
            require(row['status'] == ABI['constants']['PENDING']
                    and row['update'] == (ABI['constants']['BEG_UPDATE'] | ABI['constants']['UPDATE_WINDOW'])
                    and row['updates'] == 0 and row['paints'] == start['paints'],
                    name + ': UPDATE did not wait without repainting')
            outlined(row)
            return row

        def cancel():
            b._cmd_ok('KEY ESC down')
            s.frames(3)
            b._cmd_ok('KEY ESC up')
            s.frames(8)
            require(read('DESKDRAG', 'phase') == 0, 'Escape retained the native gesture')
            require(read('DESKSTATE', 'outlineVisible') == 0
                    and s.number(resident['outlineDrawn'], 2) == 0,
                    'Escape retained outline pixels')

        menus = Menus(s, click, move)
        menus.select('SYS:')
        desk = next(a for a in instances(b, s.p, directory)
                    if a['name'] == 'desktop')['symbols']['GEMDesk']
        folder = s.number(desk+D['folders'], 4)
        folder_work = lambda: rectangle(folder+F['work'])
        fx, fy, _, _ = folder_work()
        saved = baseline(fx+120, fy-6)
        edge(1)
        move(fx+136, fy-6)
        outlined(observe('files-start'))
        s.frames(130)
        held = observe('files-held')
        outlined(held)
        pixels(saved, held['target'], True, 'files-held')
        move(fx+152, fy-6)
        motion = observe('files-motion')
        require(motion['target'] != held['target'], 'Files stopped tracking')
        pixels(saved, motion['target'], True, 'files-motion')
        cancel()
        pixels(saved, motion['target'], False, 'files-cancelled')
        edge(0, 100)

        click(296, 8)
        click(304, 72)  # Desk > Counter.
        found = []
        for _ in range(60):
            found = [a for a in instances(b, s.p, directory) if a['name'] == 'counter']
            if found:
                break
            s.frames(20)
        require(found, 'Counter did not launch')
        app = found[0]['symbols']['GEMCounter']
        s.rendezvous('dw($%x)=1' % (app+12))
        s.frames(100)
        contexts = [s.number(resident['contexts']+i*4, 4)
                    for i in range(ABI['constants']['CONTEXTS'])]
        context = next(c for c in contexts if c and
                       s.number(c+request['owner'], 3) == found[0]['task'])
        work = lambda: rectangle(app+38)
        original = work()
        x, y, _, _ = original
        saved = baseline(x+64, y-6)
        edge(1, 4)
        move(x-64, y-6)
        started = observe('counter-start')
        outlined(started)
        waiting = wait_update(started, 'counter-waiting')
        pixels(saved, waiting['target'], True, 'counter-waiting')

        # A stationary capture must let the presenter sleep despite the waiter.
        tasks = json.loads((ROOT / 'abi/tasks.json').read_text())
        state = next(f[2] for f in tasks['task']['fields'] if f[0] == 'tc_State')
        service = read('DESKSTATE', 'service', 3)
        owner = s.number(service+desktop_layout()['Service']['fields']['owner'], 3)
        s.rendezvous('db($%x)=%d' % (owner+state, tasks['states']['WAIT']))
        self.report['stationary_presenter_waits'] = True

        move(x-48, y-6)
        motion = observe('counter-motion')
        outlined(motion)
        require(motion['target'] != waiting['target'], 'Queued UPDATE froze Counter motion')
        pixels(saved, motion['target'], True, 'counter-motion')
        edge(0, 150)
        released = observe('counter-released')
        require(released['phase'] == released['outline'] == released['c_outline'] == 0
                and released['paints'] > started['paints'], 'Release did not settle repaint')
        require(work() == [motion['target'][0]+8, motion['target'][1]+11,
                           original[2], original[3]], 'Counter committed the wrong geometry')

        original = work()
        x, y, _, _ = original
        saved = baseline(x+64, y-6)
        edge(1, 4)
        move(x+80, y-6)
        started = observe('escape-start')
        waiting = wait_update(started, 'escape-waiting')
        cancel()
        cancelled = observe('escape-cancelled')
        require(work() == original and cancelled['status'] == ABI['constants']['PENDING']
                and cancelled['buttons'] == 1, 'Escape changed geometry or granted UPDATE')
        pixels(saved, waiting['target'], False, 'escape-restored')
        edge(0, 150)
        require(s.number(app+18, 4) > started['paints'], 'Escape/release did not resume repaint')

        # A different application's queued UPDATE must not suspend Files either.
        fx, fy, _, _ = folder_work()
        click(fx+120, fy-6)
        original = folder_work()
        saved = baseline(fx+120, fy-6)
        edge(1, 4)
        move(fx+136, fy-6)
        started = observe('files-counter-start')
        waiting = wait_update(started, 'files-counter-waiting')
        pixels(saved, waiting['target'], True, 'files-counter-waiting')
        move(fx+152, fy-6)
        motion = observe('files-counter-motion')
        outlined(motion)
        require(motion['target'] != waiting['target'], 'Another client froze Files motion')
        pixels(saved, motion['target'], True, 'files-counter-motion')
        edge(0, 150)
        released = observe('files-counter-released')
        require(released['phase'] == released['outline'] == released['c_outline'] == 0
                and released['paints'] > started['paints'], 'Files release did not settle')
        require(folder_work() == [motion['target'][0]+8, motion['target'][1]+11,
                                  original[2], original[3]], 'Files committed the wrong geometry')

        # Counter's left title remains exposed; use physical gadgets to clean up.
        x, y, _, _ = work()
        click(x+16, y-6)
        click(x, y-8)
        for _ in range(60):
            if not any(a['name'] == 'counter' for a in instances(b, s.p, directory)):
                break
            s.frames(20)
        require(not any(a['name'] == 'counter' for a in instances(b, s.p, directory)),
                'Counter retained its Process after close')
        self.report['closed'] = True
        click(80, 34)  # Exposed Shell title.
        s.save_screen(out / 'boot-smoke.png')
        s.saved['integration'] = self.report
        for char in 'EXIT':
            s.press(char)
        b._cmd_ok('KEY RETURN down')
        b.bp_clear_all()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    out = parser.parse_args().bundle.resolve()
    for name in ('EXEC816_LATENCY_TRACE', 'EXEC816_MASK_TRACE', 'EXEC816_MOUSE_TRACE'):
        os.environ.pop(name, None)
    with zipfile.ZipFile(out / 'exec816-demo.zip') as archive:
        archive.extractall(out / 'extracted')
    probe = NativeDragUpdate()
    result = run(out, boot_smoke=True, distribution_root=out / 'extracted/exec816-demo',
                 integration=probe, profile_commands=False)
    result.update(tier='development', qualification=False, native_drag_update=probe.report)
    (out / 'native-drag-update-results.json').write_text(json.dumps(result, indent=2) + '\n')
