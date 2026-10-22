#!/usr/bin/env python3
"""Production QED practical desktop workload and visible-response development gates."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from desktop_menu_check import Menus
from desktop_mouse import schedule
from filesystem_audit import Audit
from make_data_disk import make
from native_program import ROOT, require, sha256
from qed_coexist_observe import ProductionEditor, emitted_offsets, heap_checkpoint
from test_demo import run

DOCUMENT = b'\n'.join(b'row %02d\tneedle %02d' % (i, i) for i in range(48)) + b'\n'
LOAD = bytes(range(256))*2048


class Coexistence:
    interrupt_marker = 'native_nmi'

    def __init__(self, production, offsets, cohort, profile=False):
        self.production, self.offsets, self.cohort = production, offsets, cohort
        self.profile = profile

    def prepare_work(self, target, item):
        directory = target.parent/'coexist-work-source'
        shutil.copytree(target.parent/'workspace-source', directory, dirs_exist_ok=True)
        (directory/'SESSION.TXT').write_bytes(DOCUMENT)
        (directory/'LOAD.BIN').write_bytes(LOAD)
        if self.cohort == 'peer':
            # EXECUTE runs in the owning shell. Its ordinary comment reads
            # leave time to return focus before the final cooperative BREAK.
            (directory/'STOP.CMD').write_bytes(b'; delay\n'*8192+b'STOPQED\n')
        make(target, directory, binary_names={'LOAD.BIN'}, filesystem='sdfs',
             sector_bytes=256, sectors=2880, label='WORK')

    def start_load(self, session, menus, click, editor, report):
        pass

    def input_sample(self, name):
        pass

    def held_form(self, editor):
        editor.frames(100)

    def expose(self, lines):
        pass

    def finish_load(self):
        pass

    def exercise(self, s):
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x, y):
            current = [s.number(at(n), 2) for n in ('cursorX', 'cursorY')]
            target = schedule(s.b, s.p, current, (x, y)); s.saved['pointer'] = target
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' % (at('cursorX'), target[0], at('cursorY'), target[1]))
        def click(x, y):
            move(x, y); s.b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(15)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(50)
        s.saved['desktop_menu'] = {}
        menus = Menus(s, click, move); menus.select('Shell')
        baseline = s.ledger()
        report = dict(cohort=self.cohort, production_app=True, timings=[], checkpoints=[])
        self.report = report
        s.command('MEM')  # Warm the normal shell's reporting/storage path.
        report['initial_heap'] = heap_checkpoint(s.rendezvous, s.far, s.p['build']['memory'])
        old = s.begin('RUN C:QED.APP WORK:SESSION.TXT'); s.ready(old); s.result()
        identity = s.number(s.at('job'))
        e = ProductionEditor(s, self.production, self.offsets, identity, s.p['output'], report, 0)
        e.reach('dw($%x)=%d' % (e.sy['source_bytes'], len(DOCUMENT)))
        e.command_idle(); menus.select('SESSION.TXT'); e.move(630, 20)
        original = DOCUMENT.split(b'\n'); lines = list(original)
        e.loaded('coexist-open', original, path=b'WORK:SESSION.TXT')
        self.start_load(s, menus, click, e, report)
        report['checkpoints'].append(e.snapshot('loaded'))
        if self.profile: s.b.profile_start('callgraph')
        try:
            for index, key in enumerate('ABCDEF'):
                lines[0] = (b'abcdef'[:index+1])+original[0]
                e.timed_key('insert-'+str(index), key, lambda: e.text_pixels('insert', lines), 500)
        finally:
            if self.profile:
                s.b.profile_stop()
                (s.p['output']/'insertion-profile.json').write_text(json.dumps(s.b.profile_dump_tree(), indent=2)+'\n')
            (s.p['output']/'coexist-progress.json').write_text(json.dumps(report, indent=2)+'\n')
        self.input_sample('typing-complete')
        e.key('Z', ctrl=True); e.selection('undo', original, None, 0, 0)
        e.key('Z', ctrl=True); e.selection('redo', lines, None, 6, 0)
        for row in range(1, 33):
            if row < 27:
                e.key('EQUALS', ctrl=True, settle=3)
                e.reach('dw($%x)=%d' % (e.text()['pointer']+e.offsets[4], row))
                if row == 26:
                    # Timed navigation starts after the untimed warm-up's
                    # completed scanout, as subsequent timed samples do.
                    e.pixels('navigation-warmup', lines, e.text())
            else:
                def navigation():
                    require(e.text()['y'] == row, 'Pending row navigation')
                    return e.text_pixels('navigation', lines)
                e.timed_key('navigate-'+str(row), 'EQUALS', navigation, 1000, ctrl=True)
        self.input_sample('navigation-complete')
        report['checkpoints'].append(e.snapshot('undo-and-viewport'))
        e.timed_key('find-open', 'F', lambda: e.form_pixels_once('find-open'), 1500, ctrl=True)
        self.held_form(e)
        for key in 'NEEDLE': e.form_key(key, settle=4)
        e.accept_find(); e.command_idle()
        e.selection('found', lines, (32, 7, 32, 13), 13, 32)
        e.key('ESC'); e.expected_range = None
        e.timed_key('find-reopen', 'F', lambda: e.form_pixels_once('find-reopen'), 1500, ctrl=True)
        def dismissed():
            require(not e.form(), 'Pending form dismissal')
            return e.text_pixels('find-dismiss', lines)
        e.timed_key('find-dismiss', 'ESC', dismissed, 1500)
        e.command_idle()
        e.key('S', ctrl=True); e.consents(); e.command_idle()
        require(not e.text()['dirty'], 'Save did not clear dirty state')
        report['first_save'] = hashlib.sha256(b'\n'.join(lines)).hexdigest()
        e.key('G'); lines[32] = lines[32][:13]+b'g'+lines[32][13:]
        e.key('S', ctrl=True); e.consents(backup=True); e.command_idle()
        e.selection('saved', lines, None, 14, 32)
        require(not e.text()['dirty'], 'Backup Save did not clear dirty state')
        report['checkpoints'].append(e.snapshot('saved'))
        self.expose(lines)
        e.choose('SESSION.TXT', 'WORK'); e.loaded('reopened', lines, path=b'WORK:SESSION.TXT')
        self.finish_load(); menus.select('SESSION.TXT'); e.move(630, 20)
        from sio_transaction_trace import BASE_HZ
        start = s.b.eval_expr('@clk') & 0xffffffff
        e.key('Q', ctrl=True, settle=0)
        s.rendezvous('db($%x)=4' % (e.owner['record']+e.fields['state']))
        elapsed = ((s.b.eval_expr('@clk')-start) & 0xffffffff)/BASE_HZ*1000
        require(elapsed <= 2000, 'Clean Quit exceeded response limit')
        report['quit_ms'] = elapsed
        menus.select('Shell'); s.command('JOBS', b'finished')
        require(s.ledger() == baseline, 'QED retained native ownership')
        s.command('MEM')
        report['final_heap'] = heap_checkpoint(s.rendezvous, s.far, s.p['build']['memory'])
        a, b = report['initial_heap'], report['final_heap']
        # Keep completion evidence even when an ownership/memory assertion fails.
        if a['free_bytes'] != b['free_bytes']:
            pieces = []
            for start, size in a['extents']:
                spans = [(start, start+size)]
                for free, count in b['extents']:
                    spans = [part for lo, hi in spans for part in
                             [(lo, min(hi, free)), (max(lo, free+count), hi)]
                             if part[0] < part[1]]
                pieces.extend(spans)
            report['newly_allocated_spans'] = [dict(address=lo, bytes=hi-lo,
                prefix=s.far(lo, min(hi-lo, 512)).hex()) for lo, hi in pieces[:12]]
        (s.p['output']/'coexist-completion.json').write_text(json.dumps(report, indent=2)+'\n')
        require((a['free_bytes'], a['largest_bytes']) == (b['free_bytes'], b['largest_bytes']),
                'Production workflow retained memory or fragmentation')
        report['normal_collection'] = True
        s.saved['integration'] = report
        s.save_screen(s.p['output']/'coexist-finished.png')
        for char in 'EXIT': s.press(char)
        s.b._cmd_ok('KEY RETURN down'); s.b.bp_clear_all()


def check(output, bundle, production, layout_from, cohort, profile=False, factory=Coexistence):
    require(not output.exists(), 'Use a fresh coexistence output directory')
    offsets = emitted_offsets(production, layout_from)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    app = json.loads((production/'app.json').read_text())
    require(manifest['qed_preview']['app_sha256'] == sha256(production/'program.app') == app['sha256'],
            'Production APP differs from the packaged APP')
    for name, digest in manifest['source_inputs'].items():
        require(sha256(ROOT/name) == digest, 'Changed native package source: '+name)
    def ignore(directory, names):
        return [n for n in names if n in {'altirra', 'extracted', 'emulator.log', 'coexist-work-source'}
                or n.endswith(('-results.json', '.bgra')) or n == 'work-walkthrough.atr']
    shutil.copytree(bundle, output, ignore=ignore)
    with zipfile.ZipFile(output/'exec816-demo.zip') as archive:
        for line in archive.read('exec816-demo/SHA256SUMS').decode().splitlines():
            digest, name = line.split('  ', 1)
            require(hashlib.sha256(archive.read('exec816-demo/'+name)).hexdigest() == digest, 'Changed ZIP file: '+name)
        archive.extractall(output/'extracted')
    observer = factory(production, offsets, cohort, profile)
    result = run(output, boot_smoke=True, distribution_root=output/'extracted/exec816-demo',
                 integration=observer, profile_commands=False)
    disk = Audit((output/'work-walkthrough.atr').read_bytes()); allocation = disk.sdfs()
    first = [b'abcdef'+DOCUMENT.split(b'\n')[0], *DOCUMENT.split(b'\n')[1:]]
    final = list(first); final[32] = final[32][:13]+b'g'+final[32][13:]
    require(disk.files['SESSION.TXT'] == b'\n'.join(final) and disk.files['SESSION.BAK'] == b'\n'.join(first),
            'Coexistence persisted document/backup bytes differ')
    result.update(scope='QED practical coexistence '+cohort, qualification=False,
                  allocation=allocation, zip_sha256=sha256(output/'exec816-demo.zip'),
                  production_app_sha256=sha256(production/'program.app'), layout_offsets=list(offsets),
                  fixture_bytes=dict(document=len(DOCUMENT), checksum_input=len(LOAD)),
                  observer_inputs={str(p.relative_to(ROOT)): sha256(p) for p in
                      [Path(__file__), ROOT/'tools/qed_coexist_observe.py', *getattr(observer, 'inputs', ())]})
    (output/'coexist-results.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--bundle', type=Path, default=ROOT/'build/qed-coexist/sync-preview')
    p.add_argument('--production', type=Path, default=ROOT/'build/qed-coexist/sync-production')
    p.add_argument('--layout-from', type=Path, default=ROOT/'build/qed-coexist/qc3-sync/app')
    p.add_argument('--cohort', choices=['baseline'], default='baseline')
    p.add_argument('--profile-insert', action='store_true', help='Collect a bounded host callgraph around measured insertion')
    a = p.parse_args()
    check(a.output.resolve(), a.bundle.resolve(), a.production.resolve(), a.layout_from.resolve(), a.cohort, a.profile_insert)
    print('QED coexistence passed:', a.cohort)
