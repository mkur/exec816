#!/usr/bin/env python3
"""Passive stack observations on a copied, exact OF816 desktop package."""
import argparse
from collections import defaultdict, deque
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

from gem_applications import instances
from native_program import read_build, require, sha256
from stack_budget import stack_usage
from test_demo import run


def markers(program, directory):
    image = json.loads((directory/'c-image.json').read_text())
    executable = [(s['address'], s['address']+len(s['bytes']))
                  for s in image['segments'] if s['executable']]
    points = {address: name for name, address in image['symbols'].items()
              if not name.startswith('?') and
              any(lo <= address < hi for lo, hi in executable)}
    # Public C frame reservations complement entry observations: a function
    # may reserve unwritten local space before calling another observed entry.
    for listing in (directory/'drawing').glob('*.lst'):
        text = listing.read_text()
        public = set(re.findall(r'\.public (\w+)', text))
        name = None
        for line in text.splitlines():
            if '.section ' in line:
                name = None
            label = re.search(r'\\ ([0-9a-f]{6})\s+(\w+):', line)
            if label and label[2] in public:
                name = label[2] if label[2] in image['symbols'] else None
                if name:
                    base = image['symbols'][name]-int(label[1], 16)
            at = re.search(r'\\ ([0-9a-f]{6}) 1b\s+tcs', line)
            if at and name:
                points[base+int(at[1], 16)+1] = name+':after-tcs'
    for routine in program['image']['routines']:
        if routine['name'].startswith(('M_DISPLAY_', 'M_VBXENOTIFY_', 'M_DOSCLIENT_',
                                       'M_DOSCALLS_', 'M_DOSDIRECTORY_')):
            points[routine['address']] = routine['name']
    for name in ('native_irq', 'native_nmi', 'cop_handler', 'context_restore'):
        if name in program['labels']:
            points[program['labels'][name]] = name
    return points


def summarize(path, points, memory):
    """Stream potentially large logs; retain only minima and nearby markers."""
    rows = {}; recent = defaultdict(lambda: deque(maxlen=24)); chains = defaultdict(list)
    pools = list(enumerate(memory['task_pools']))
    low, high = memory['regions']['kernel-stack']
    pools.append(('kernel', dict(stack_base=low+16, stack_bytes=high-low-32)))
    with path.open() as source:
        for line in source:
            match = re.search(r'\[(?:SIOPOC|SIOTXN)\] cpu (.*)', line)
            if not match:
                continue
            fields = match[1].split()
            pc, s, dp = (int(fields[i], 16) for i in (3, 7, 8))
            owner = next(((slot, pool) for slot, pool in pools
                          if pool['stack_base'] <= s < pool['stack_base']+pool['stack_bytes']), None)
            if owner is None:
                continue
            slot, pool = owner
            name = points.get(pc, f'${pc:06x}')
            event = dict(clock=int(fields[0]), pc=pc, name=name, s=s, dp=dp)
            # IRQ entry already includes the hardware interrupt frame. Keep
            # it distinct from ordinary C/native points, not as a call frame.
            kind = ('interrupt-entry' if name in ('native_irq', 'native_nmi') else
                    'context-restore' if name == 'context_restore' else 'selected-code')
            if kind == 'selected-code':
                recent[slot].append(event)
                if not name.endswith(':after-tcs'):
                    while chains[slot] and chains[slot][-1]['s'] <= s:
                        chains[slot].pop()
                    chains[slot].append(event)
            key = f'{slot}:{kind}'
            if key not in rows or s < rows[key]['minimum_s']:
                rows[key] = dict(slot=slot, kind=kind, minimum_s=s,
                                 remaining_above_floor=s+1-pool['stack_base']-256,
                                 event=event, recent=list(recent[slot]),
                                 entry_candidates=list(chains[slot]))
    require(rows, 'No selected stack observations')
    return rows


class Observed:
    def __init__(self, integration, output):
        self.integration, self.output, self.snapshots = integration, output, []

    def snapshot(self, s, label):
        apps = instances(s.b, s.p, s.p['output']/'bitmap-console')
        storage = s.p['build']['task_storage']; tasks = []
        for slot, pool in enumerate(s.p['build']['memory']['task_pools']):
            raw = s.b.memdump(storage['BASE']+slot*storage['SIZE'], storage['SIZE'])
            number = lambda offset, size: int.from_bytes(raw[offset:offset+size], 'little')
            task = number(storage['TCB_ITEM'], 3)
            app = next((a for a in apps if a['task'] == task), None)
            tasks.append(dict(slot=slot, task=task, state=number(storage['TCB_STATE'], 1),
                              incarnation=number(storage['TCB_INCARNATION'], 4),
                              app={k: app[k] for k in ('name', 'identity', 'base')} if app else None))
        self.snapshots.append(dict(label=label, clock=s.b.eval_expr('@clk') & 0xffffffff,
                                   tasks=tasks, stacks=stack_usage(s.b, s.p['build']['memory'])))
        (self.output/'stack-checkpoints.json').write_text(json.dumps(self.snapshots, indent=2)+'\n')

    def exercise(self, s):
        self.snapshot(s, 'desktop-ready')
        s.stack_checkpoint = lambda label: self.snapshot(s, label)
        cells = s.cells
        def observed_cells(label, *args, **kwargs):
            self.snapshot(s, label)
            return cells(label, *args, **kwargs)
        s.cells = observed_cells
        s.b.profile_start('basicblock')
        try:
            self.integration.exercise(s)
            self.snapshot(s, 'integration-end')
        finally:
            s.b.profile_stop()


class EditProbe:
    """A bounded attribution run; the full walkthroughs remain separate."""
    def exercise(self, s):
        from desktop_mouse import schedule
        from desktop_menu_check import Menus
        from browser_model import FIELDS
        app = next(a for a in instances(s.b, s.p, s.p['output']/'bitmap-console')
                   if a['name'] == 'files')
        base = app['symbols']['GEMBrowser']; position = [320, 120]
        def move(x, y):
            nonlocal position
            at = lambda name: next(d['address'] for d in s.p['image']['data']
                                   if '_DESKINPUT_'+name.upper()+'_' in d['name'])
            position = [s.number(at(name), 2) for name in ('cursorX', 'cursorY')]
            position = schedule(s.b, s.p, position, (x, y))
            s.saved['pointer'] = position
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                         (at('cursorX'), position[0], at('cursorY'), position[1]))
            s.frames(3)
        def click(x, y):
            move(x, y)
            s.b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(35)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(60)
        menus = Menus(s, click, move)
        menus.select('Files'); menus.key('P')
        require(s.number(base+FIELDS['dialog'], 2) == 1, 'Path dialog did not open')
        s.stack_checkpoint('path-open')
        menus.key('A'); menus.key('BACKSPACE')
        menus.select('Shell'); menus.select('Files')
        s.stack_checkpoint('edit-and-exposure')
        s.cells('stack-edit-exposed')
        menus.key('ESC')
        require(s.number(base+FIELDS['dialog'], 2) == 0, 'Path dialog did not cancel')
        menus.select('Shell')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for char in 'EXIT': s.press(char)
        s.b._cmd_ok('KEY RETURN down'); s.b.bp_clear_all()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--walkthrough', choices=('edit', 'files', 'calculator'), default='edit')
    args = parser.parse_args()
    out = args.output.resolve()
    require(not out.exists(), 'Use a fresh observation directory')
    shutil.copytree(args.bundle.resolve(), out,
                    ignore=shutil.ignore_patterns('extracted', 'emulator.log', '*.png'))
    p = read_build(out); points = markers(p, out/'bitmap-console')
    prefixes = ('objc_', 'App_', 'ExecAESDrawEdit', 'GemDrawingBorrow', 'GemWidget',
                'vbxe_', 'blit_', 'glyph_record', 'scr_row', '_DOSCall', 'rsrc_',
                'Display', '_DisplayCall', 'M_', 'native_', 'context_restore')
    points = {pc: name for pc, name in points.items() if name.startswith(prefixes)}
    (out/'stack-markers.json').write_text(json.dumps(points, indent=2)+'\n')
    if args.walkthrough == 'edit':
        integration = EditProbe()
    elif args.walkthrough == 'files':
        from test_gem_desktop_boot import DesktopBoot
        integration = DesktopBoot(files_only=True)
    else:
        from test_calculator_desktop import CalculatorDesktop
        integration = CalculatorDesktop()
    observer = Observed(integration, out)
    saved = {k: os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS')}
    os.environ.update(EXEC816_LATENCY_TRACE='1',
                      EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in points))
    report = dict(status='running', tier='development', qualification=False,
                  package_sha256=sha256(out/'exec816-demo.zip'), walkthrough=args.walkthrough,
                  harness_sha256=sha256(Path(__file__)),
                  scope='Selected resident C/native instructions and IRQ/NMI entry; not an exhaustive S trace. Entry candidates require source/listing confirmation: selected entries cannot unwind unobserved returns.')
    try:
        with zipfile.ZipFile(out/'exec816-demo.zip') as archive:
            archive.extractall(out/'extracted')
        report['runtime'] = run(out, boot_smoke=True, distribution_root=out/'extracted/exec816-demo',
                                integration=observer, profile_commands=False)
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='fail', error=type(error).__name__+': '+str(error))
        raise
    finally:
        for key, value in saved.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        if report['status'] == 'pass':
            report['minima'] = summarize(out/'emulator.log', points, p['build']['memory'])
        (out/'stack-results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Stack observations:', {key: value['remaining_above_floor'] for key, value in report['minima'].items()})


if __name__ == '__main__':
    main()
