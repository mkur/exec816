#!/usr/bin/env python3
"""Physical shell keys, loaded commands and late Close errors on both formats."""
import argparse
import json
import shutil
import time
from pathlib import Path

from build_command import compile_command
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_o65_shell import Commands
from test_shell_core import run
from test_filesystem_write_lifetime import instrument
from filesystem_audit import Audit


class WritableCommands(Commands):
    mounts = [dict(alias='D1', unit=49, sectors=720, sector_bytes=128, profile=1),
              dict(alias='WORKM', unit=50, sectors=720, sector_bytes=128, profile=1,
                   format=1, access='readwrite'),
              dict(alias='WORKS', unit=51, sectors=720, sector_bytes=128, profile=1,
                   format=2, access='readwrite')]

    def instrument(self, out):
        super().instrument(out)
        self.observers = instrument(out)
        observed = out/'shell-observed.inc'
        source = observed.read_text()
        old = '  SHELLEDITPROBE.Capture(bytes,count)\n  NativeShellWrite(handle,bytes,count)'
        require(source.count(old) == 1, 'Stale shell output observer')
        source = source.replace(old, '''  LET header=DOSOBJECTS.Find(DOSCORE.Current(),BYTE POINTER(handle),DOSOBJECTS.KIND_FILE)
  IF header<>NULL THEN
    IF header.backend=DOSOBJECTS.BACKEND_CON THEN
      SHELLEDITPROBE.Capture(bytes,count)
    FI
  FI
  NativeShellWrite(handle,bytes,count)''')
        observed.write_text(source)
        profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
        profile['image_data_bytes'] = 4096
        self.memory_profile = out/'shell-memory.json'
        self.memory_profile.write_text(json.dumps(profile, indent=2) + '\n')

    def prepare(self, toolchain, out, mode, size):
        source = out/'files'
        source.mkdir(exist_ok=True)
        self.commands = {}
        for name in ('HELLO', 'CAT', 'WC', 'CMP'):
            self.commands[name] = compile_command(toolchain, ROOT/f'examples/commands/{name.lower()}.act', source/name, mode == 'opt')
            for suffix in ('options.json', 'profile.json'):
                (source/(name+'.'+suffix)).rename(out/(name+'.'+suffix))
        shutil.copyfile(ROOT/'examples/demo-disk/STORY.TXT', source/'STORY.TXT')
        self.files = make(out/'volume.atr', source, binary_names=set(self.commands))
        self.baselines = {}
        for filesystem in ('mydos', 'sdfs'):
            media = out/(filesystem+'.atr')
            shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-128.atr', media)
            audit = Audit(media.read_bytes())
            getattr(audit, filesystem)()
            self.baselines[filesystem] = audit

    def mount_extra(self, bridge, out):
        bridge.mount(1, str(out/'mydos.atr'))
        bridge.mount(2, str(out/'sdfs.atr'))
        bridge.config('accuratedisk', 'false')

    def arm_close(self, c):
        for name, value, size in (('mode', 2, 1), ('fired', 0, 1), ('count', 0, 2),
                                  ('action', 1007, 2), ('ordinal', 1, 2)):
            address = next(d['address'] for d in c.p['image']['data'] if '_FSWRITEPROBE_'+name.upper()+'_' in d['name'])
            c.b.memload(address, value.to_bytes(size, 'little'))

    def exercise(self, c):
        for mount in ('WORKM', 'WORKS'):
            c.command(f'ECHO saved >{mount}:OUT.TXT')
            c.command(f'CAT {mount}:OUT.TXT', b'saved\n')
            c.command(f'CAT SYS:STORY.TXT >{mount}:COPY.TXT')
            c.command(f'CMP SYS:STORY.TXT {mount}:COPY.TXT')
            c.command(f'HELLO | WC >{mount}:PIPE.TXT')
            c.command(f'CAT {mount}:PIPE.TXT', b'1 3 17\n')
            c.command(f'MISSING >{mount}:OUT.TXT', error=205)
            c.command(f'CAT {mount}:OUT.TXT')
        c.check_screen('writable-files')
        self.arm_close(c)
        c.command('ECHO late >WORKM:LATE.TXT', error=6, status=20)
        c.command('HELLO', b'Hello from disk!\n')
        self.arm_close(c)
        c.command('HELLO | WC >WORKS:LATE.TXT', error=6, status=20)
        c.command('HELLO', b'Hello from disk!\n')
        c.check_screen('late-close-recovery')

    def persisted(self, bridge, program, out):
        time.sleep(3)
        bridge.regs()
        self.reports = {}
        for drive, filesystem in ((1, 'mydos'), (2, 'sdfs')):
            bridge._cmd_ok(f'EJECT drive={drive}')
            media = out/(filesystem+'.atr')
            audit = Audit(media.read_bytes())
            report = getattr(audit, filesystem)()
            expected = {**self.baselines[filesystem].files, 'OUT.TXT': b'',
                        'COPY.TXT': self.files['STORY.TXT'], 'PIPE.TXT': b'1 3 17\n',
                        'LATE.TXT': b'late\n' if filesystem == 'mydos' else b'1 3 17\n'}
            require(audit.files == expected, 'Unexpected shell output on ' + filesystem)
            self.reports[filesystem] = dict(audit=report, sha256=sha256(media))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    scenario = WritableCommands()
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result = dict(status='running')
    try:
        result = run(compiler(ROOT/'build/actionc'), output, args.case, external=scenario,
                     reuse=args.reuse, pin=pin, bridge_build=ROOT/'build/shell-paced-bridge')
        result.update(commands=scenario.commands, writable_media=scenario.reports,
                      write_observers=scenario.observers, configuration_overrides=dict(accuratedisk=False),
                      bank_zero_delta=dict(fixed=0, per_task=0))
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Writable shell passed', args.case)
