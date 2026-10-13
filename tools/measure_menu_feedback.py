#!/usr/bin/env python3
"""Physical dropdown latency in an exact demo ZIP, sampled once per PAL frame.

Use settled reference images from the same immutable scene for whole-region
completion. Independent menu pixels and ownership are checked by the emitted
AES menu suite. This benchmark measures an idle desktop, not a drawing load.
"""
import argparse
import json
import shutil
import zipfile
from pathlib import Path

from desktop_menu_check import Menus
from desktop_mouse import schedule
from measure_desktop import distribution
from native_program import require, sha256
from sio_transaction_trace import BASE_HZ
from test_demo import run


class Feedback:
    def __init__(self, count, load_check=False, cold=False):
        self.cold = cold
        self.count = count
        self.load_check = load_check
        self.results = {}

    def exercise(self, s):
        b = s.b
        def at(module, name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_'+module+'_'+name.upper()+'_' in d['name'])
        def move(x, y):
            old = [s.number(at('DESKINPUT', n), 2) for n in ('cursorX', 'cursorY')]
            pos = schedule(b, s.p, old, (x, y))
            s.saved['pointer'] = pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                         (at('DESKINPUT', 'cursorX'), pos[0], at('DESKINPUT', 'cursorY'), pos[1]))
            s.frames(3)
        def click(x, y):
            move(x, y)
            b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(75)
        menus = Menus(s, click, move)
        menus.select('SYS:')
        move(632, 232); s.frames(100)
        # The shipped Files counter advances only after its complete redraw
        # and outer END_UPDATE. Observe it outside drawing; pixel equality
        # alone will become an earlier endpoint when saved pixels are restored.
        from gem_applications import symbols
        from colour_desktop_model import FIELDS as D
        from browser_model import FIELDS as F
        directory = s.p['output']/'bitmap-console'
        resident = json.loads((directory/'c-image.json').read_text())['symbols']
        desk = symbols(b, s.p, directory, 'desktop',
                       s.number(resident['GEMDesktopChildren'], 4))['GEMDesk']
        folder = s.number(desk+D['active'], 4)
        require(folder, 'No active folder for final repaint observation')
        menu = at('DESKMENU', 'menu')
        path = s.p['output']/'menu-feedback.bgra'
        cache_fields = ('captures','restores','misses','capturedBytes','restoredBytes',
                        'popupCaptures','popupRestores','popupMisses',
                        'popupCapturedBytes','popupRestoredBytes')
        cache_at = {name: next((d['address'] for d in s.p['image']['data']
                    if '_DESKMENUCACHE_'+name.upper()+'_' in d['name']), None)
                    for name in cache_fields}
        def cache_counts():
            return {name: s.number(address, 4) for name, address in cache_at.items()
                    if address is not None}

        popup_cache = next((d['address'] for d in s.p['image']['data']
                            if '_DESKMENUCACHE_POPUPS_' in d['name']), None)
        def discard_popups():
            if not self.cold or popup_cache is None:
                return
            from generate_layers import layout
            slot = layout()['CacheSlot']
            for index in range(2):
                address = popup_cache+index*slot['size']
                require(s.number(address+slot['fields']['pinned'], 1) == 0,
                        'Cannot make a pinned popup cold')
                b.memload(address+slot['fields']['valid'], b'\x00')

        def capture(area):
            frame = b.rawscreen(str(path)); raw = path.read_bytes()
            left, top, right, bottom = area
            return b''.join(raw[y*frame.stride+(left+16)*4:y*frame.stride+(right+16)*4]
                            for y in range(top, bottom))

        def press(key, ctrl=False, shift=False):
            start = b.eval_expr('@clk') & 0xffffffff
            if ctrl: b._cmd_ok('KEY CTRL down')
            if shift: b._cmd_ok('KEY SHIFT down')
            b._cmd_ok('KEY '+key+' down')
            s.frames(1)
            b._cmd_ok('KEY '+key+' up')
            if shift: b._cmd_ok('KEY SHIFT up')
            if ctrl: b._cmd_ok('KEY CTRL up')
            return start

        # App File/View popups and Windows share this stable area; the shell
        # caret and parked pointer are outside it. Reference state is warmed
        # before timing, with no writes to guest state or executable observers.
        area = (128, 0, 640, 208)
        for kind in ('application', 'native'):
            sequence = [('open', ('ESC', True, kind == 'application')),
                        ('highlight', ('TAB',)),
                        ('switch' if kind == 'application' else 'next_row',
                         ('ASTERISK', True) if kind == 'application' else ('TAB',)),
                        ('close', ('ESC',))]
            reference = []
            for name, keys in sequence:
                press(*keys); s.frames(100)
                require(bool(s.number(menu, 1)) == (name != 'close'), 'Reference menu state: '+name)
                reference.append(capture(area))
            require(all(reference[i] != reference[i-1] for i in range(4)),
                    'Reference interaction did not change visible pixels: '+kind)
            samples = {name: [] for name, _ in sequence}
            final_repaint = []
            transfers = {name: [] for name, _ in sequence}
            for iteration in range(self.count):
                for (name, keys), want in zip(sequence, reference):
                    if name in ('open', 'switch'):
                        discard_popups()
                    before_paint = s.number(folder+F['paints'], 4)
                    before_cache = cache_counts()
                    start = press(*keys)
                    for _ in range(100):
                        if capture(area) == want:
                            break
                        s.frames(1)
                    else:
                        raise RuntimeError('Menu did not match settled pixels: '+kind+'/'+name)
                    samples[name].append(((b.eval_expr('@clk')-start)&0xffffffff)/BASE_HZ*1000)
                    if name == 'close':
                        for _ in range(100):
                            if s.number(folder+F['paints'], 4) > before_paint and capture(area) == want:
                                break
                            s.frames(1)
                        else:
                            raise RuntimeError('No final Files repaint after '+kind+' dismissal')
                        final_repaint.append(((b.eval_expr('@clk')-start)&0xffffffff)/BASE_HZ*1000)
                    after_cache = cache_counts()
                    transfers[name].append({k: after_cache[k]-v for k,v in before_cache.items()})
                    s.frames(7+iteration % 5)
            self.results[kind] = {name: dict(samples_ms=values, **distribution(values))
                                  for name, values in samples.items()}
            self.results[kind]['final_app_repaint'] = dict(samples_ms=final_repaint,
                **distribution(final_repaint))
            self.results[kind]['transfers'] = transfers
            print(kind, json.dumps(self.results[kind]), flush=True)
            (s.p['output']/'menu-samples.json').write_text(json.dumps(self.results, indent=2)+'\n')
        if self.load_check:
            # Put Counter left of Files, so its digits stay visible under both
            # menus. Check real drawing progress while selection keeps moving.
            from gem_applications import symbols
            from colour_desktop_model import FIELDS as D
            directory = s.p['output']/'bitmap-console'
            resident = json.loads((directory/'c-image.json').read_text())['symbols']
            desk = symbols(b, s.p, directory, 'desktop',
                           s.number(resident['GEMDesktopChildren'], 4))['GEMDesk']
            click(296, 8); click(304, 88)
            for _ in range(60):
                child = s.number(desk+D['children'], 4)
                if child:
                    break
                s.frames(20)
            require(child, 'Counter did not launch: '+repr(b.memdump(desk+D['status'], 65)))
            counter = symbols(b, s.p, directory, 'counter', child)['GEMCounter']
            s.rendezvous('dw($%x)=1' % (counter+12))
            move(216, 40); b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(20)
            move(24, 168); b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(100)
            s.rendezvous('(dw($%x)=8)&(dw($%x)=176)' % (counter+38, counter+40))
            menus.select('SYS:'); move(632, 232); s.frames(75)
            # WF_WXYWH clears its caller scratch while querying. Use the
            # verified placement, and keep all six digits left of Files x=120.
            digits = (72, 184, 120, 192)
            checks = {}
            for kind in ('application', 'native'):
                press('ESC', True, kind == 'application'); s.frames(80)
                before = [s.number(counter+offset, 4) for offset in (14, 18)]
                old_pixels = capture(digits)
                for _ in range(30):
                    press('TAB'); s.frames(3)
                after = [s.number(counter+offset, 4) for offset in (14, 18)]
                require(all(a > z for a, z in zip(after, before)) and capture(digits) != old_pixels,
                        'Counter stopped painting during '+kind+' menu input: '+repr((before, after)))
                checks[kind] = dict(ticks=after[0]-before[0], paints=after[1]-before[1],
                                    visible_digits_changed=True, highlights=30)
                press('ESC'); s.frames(100)
            self.results['load_check'] = checks
            print('Counter under menu input:', checks, flush=True)
        s.save_screen(s.p['output']/'boot-smoke.png')
        menus.select('Shell')
        for char in 'EXIT': s.press(char)
        b._cmd_ok('KEY RETURN down'); b.bp_clear_all()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--load-check', action='store_true', help='Also check visible Counter progress under menu input')
    parser.add_argument('--cold', action='store_true', help='Invalidate unpinned popup images before each opening; record controlled cold misses')
    parser.add_argument('--layout-revision', help='Use recorded native ABI layouts for an older baseline executable')
    args = parser.parse_args()
    if args.layout_revision:
        import subprocess
        import generate_layers, generate_desktop, generate_aes_server
        for module, name in ((generate_layers, 'layers'), (generate_desktop, 'desktop'),
                             (generate_aes_server, 'aes-server')):
            module.ABI = json.loads(subprocess.check_output(
                ['git', 'show', args.layout_revision+':abi/'+name+'.json'], text=True))
    out = args.output.resolve()
    require(not out.exists(), 'Use a fresh measurement directory')
    require(args.count > 0, 'Positive sample count required')
    shutil.copytree(args.bundle.resolve(), out, ignore=shutil.ignore_patterns(
        'extracted', 'g4bench-extracted-*', '*.log', '*.bgra', '*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:
        archive.extractall(out/'extracted')
    probe = Feedback(args.count, args.load_check, args.cold)
    result = run(out, boot_smoke=True, distribution_root=out/'extracted/exec816-demo',
                 integration=probe, profile_commands=False)
    result.update(qualification=False, zip_sha256=sha256(out/'exec816-demo.zip'),
                  menus=probe.results, cold_popup_control=args.cold, scope='Idle desktop; keyboard submission to whole-region '
                  'scanout equality, one-frame polling. Settled reference images; independent '
                  'pixels checked separately. No sub-frame precision or loaded latency claim.')
    (out/'menu-results.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
