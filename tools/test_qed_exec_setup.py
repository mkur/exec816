#!/usr/bin/env python3
"""Cold boot the exact delivery ZIP and run production QED from the normal shell."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from desktop_menu_check import Menus
from desktop_mouse import schedule
from filesystem_audit import Audit
from native_program import ROOT, require, sha256
from qed_demo import SAMPLE
from prime_observer import process_record
from test_demo import run


class QedPreview:
    def exercise(self, s):
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_' + name.upper() + '_' in d['name'])
        def move(x, y):
            current = [s.number(at(n), 2) for n in ('cursorX', 'cursorY')]
            target = schedule(s.b, s.p, current, (x, y)); s.saved['pointer'] = target
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' % (at('cursorX'), target[0], at('cursorY'), target[1]))
        def click(x, y):
            move(x, y); s.b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(15)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(50)
        s.saved['desktop_menu'] = {}
        menus = Menus(s, click, move)
        menus.select('Shell'); baseline = s.ledger()
        shared = json.loads((s.p['output'] / 'bitmap-console/c-image.json').read_text())['symbols']
        from generate_aes_server import layout, expected_layout
        owner_offset = layout()['Request']['fields']['owner']
        form_offset = dict(expected_layout())['C context form']
        fields = {r[0]: r[2] for r in json.loads((ROOT / 'abi/process.json').read_text())['record']}
        job = s.at('job')
        def launch():
            print('QED preview: normal RUN', flush=True)
            old = s.begin('RUN C:QED.APP WORK:SAMPLE.TXT'); s.ready(old); s.result()
            identity = s.number(job)
            row = process_record(s.far, s.p, identity)
            s.frames(100)
            for _ in range(100):
                if any('SAMPLE.TXT' in w['title'] for w in menus.windows()): break
                s.frames(50)
            else: raise RuntimeError('Production QED did not open its document window')
            task = row + fields['task']
            def context():
                return next(c for i in range(4) if (c := s.number(shared['contexts'] + 4*i))
                            and s.number(c + owner_offset, 3) == task)
            return row, context
        def form(context):
            c = context()
            s.rendezvous('(dw($%x)!=0)|(dw($%x)!=0)' % (c+form_offset, c+form_offset+2))
            s.frames(30)
        def saved(context, backups):
            menus.key('S', ctrl=True)
            for _ in range(1 + int(backups)):
                form(context); menus.key('SPACE')
            for _ in range(100):
                if any('SAMPLE.TXT' in w['title'] and '*' not in w['title'] for w in menus.windows()):break
                s.frames(50)
            else: raise RuntimeError('Save did not commit the clean title')
            s.frames(60)
            print('QED preview: saved' + (' with backup rotation' if backups else ''), flush=True)
        def retire(row):
            menus.key('Q', ctrl=True)
            s.rendezvous('db($%x)=4' % (row+fields['state'])); s.frames(80)
            menus.select('Shell')
            s.command('JOBS', b'finished')
            require(s.ledger() == baseline, 'Production QED retained native ownership')
            print('QED preview: retired and collected', flush=True)
        row, context = launch(); menus.select('SAMPLE.TXT')
        menus.key('A'); saved(context, False)
        menus.key('B'); saved(context, True)
        s.save_screen(s.p['output'] / 'qed-running.png')
        retire(row)
        row, context = launch(); menus.select('SAMPLE.TXT')
        menus.key('C'); saved(context, True); retire(row)
        s.saved['integration'] = dict(production_app=True, normal_shell_launch=True,
            lifetimes=2, saves=3, backup_rotation=True, reopen=True, native_ownership_return=True)
        s.save_screen(s.p['output'] / 'boot-smoke.png')
        for char in 'EXIT': s.press(char)
        s.b._cmd_ok('KEY RETURN down'); s.b.bp_clear_all()


def check(bundle):
    with zipfile.ZipFile(bundle / 'exec816-demo.zip') as archive:
        sums = archive.read('exec816-demo/SHA256SUMS').decode().splitlines()
        require(set(archive.namelist()) == {'exec816-demo/SHA256SUMS'} |
                {'exec816-demo/' + line.split('  ', 1)[1] for line in sums}, 'Unlisted ZIP entry')
        for line in sums:
            digest, name = line.split('  ', 1)
            require(hashlib.sha256(archive.read('exec816-demo/' + name)).hexdigest() == digest, 'ZIP checksum: ' + name)
        archive.extractall(bundle / 'extracted')
    result = run(bundle, boot_smoke=True, distribution_root=bundle / 'extracted/exec816-demo',
                 integration=QedPreview(), profile_commands=False)
    disk = Audit((bundle / 'work-walkthrough.atr').read_bytes()); allocation = disk.sdfs()
    require(disk.files['SAMPLE.TXT'] == b'cab' + SAMPLE and disk.files['SAMPLE.BAK'] == b'ab' + SAMPLE,
            'Production save/reopen/backup bytes differ')
    result.update(qualification=False, scope='Exact OF816 ZIP: production QED, normal RUN, two launches, three saves, reopen, backup rotation, ownership and EXIT',
                  zip_sha256=sha256(bundle / 'exec816-demo.zip'), allocation=allocation,
                  saved_sha256=hashlib.sha256(disk.files['SAMPLE.TXT']).hexdigest())
    (bundle / 'qed-setup-results.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args(); check(args.bundle.resolve())
    print('Packaged production QED setup passed')
