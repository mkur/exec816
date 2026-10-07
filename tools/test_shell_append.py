#!/usr/bin/env python3
"""Append through real shell keys, persisted files and verified-write faults."""
import argparse
import json
import shutil
import time
from pathlib import Path

from build_command import compile_command
from filesystem_audit import Audit
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_filesystem_write_shell import WritableCommands
from test_shell_core import run


class AppendCommands(WritableCommands):
    def __init__(self, size):
        self.size = size
        self.mounts = [dict(alias='D1', unit=49, sectors=720,
                            sector_bytes=128, profile=4)]
        for alias, unit, filesystem, format_id in (
                ('WORKM', 50, 'mydos', 1), ('WORKS', 51, 'sdfs', 2)):
            audit = Audit((ROOT/f'tests/fixtures/filesystem-write/{filesystem}-{size}.atr').read_bytes())
            self.mounts.append(dict(alias=alias, unit=unit, sectors=audit.image.count,
                                    sector_bytes=size, profile=4, format=format_id,
                                    access='readwrite'))

    def instrument(self, out):
        super().instrument(out)
        observed = out/'shell-observed.inc'
        source = observed.read_text().replace('USE EXEC\n',
            'USE EXEC\nUSE DOSBREAK\nUSE FSWRITEPROBE\nUSE HEAPCORE\n', 1)
        marker = '  NativeShellWrite(handle,bytes,count)'
        require(source.count(marker) == 1, 'Stale append write observer')
        source = source.replace(marker,
            '  FSWRITEPROBE.target=DOSBREAK.Current()\n' + marker)
        marker = '      ShellCommand()\n      commandCount==+1'
        require(source.count(marker) == 1, 'Stale append cleanup observer')
        source = source.replace(marker, '''      ShellCommand()
      IF DOS.Input()<>shell.console OR DOS.Output()<>shell.console
          OR shell.tempInput<>NULL OR shell.tempOutput<>NULL
          OR shell.oldInput<>NULL OR shell.oldOutput<>NULL
          OR shell.redirectActive<>0 OR shell.restoreFailure<>0 THEN
        HEAPCORE.Abort($e5f2)
      FI
      commandCount==+1''')
        observed.write_text(source)

    def prepare(self, toolchain, out, mode, size):
        source = out/'files'
        source.mkdir(exist_ok=True)
        command_dir = source/'C'
        command_dir.mkdir(exist_ok=True)
        self.commands = {}
        for name in ('HELLO', 'CAT', 'WC'):
            self.commands[name] = compile_command(toolchain,
                ROOT/f'examples/commands/{name.lower()}.act', source/name,
                mode == 'opt')
            for suffix in ('options.json', 'profile.json'):
                (source/(name+'.'+suffix)).rename(out/(name+'.'+suffix))
            (source/name).rename(command_dir/name)
        self.payload = b'0123456789'*200
        (source/'BIG.TXT').write_bytes(self.payload)
        self.files = make(out/'volume.atr', source,
                          binary_names={'C/'+name for name in self.commands})
        self.baselines = {}
        self.expected_files = {}
        for filesystem in ('mydos', 'sdfs'):
            media = out/(filesystem+'.atr')
            shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-{self.size}.atr', media)
            audit = Audit(media.read_bytes())
            getattr(audit, filesystem)()
            self.baselines[filesystem] = audit
            self.expected_files[filesystem] = dict(audit.files)

    def mount_extra(self, bridge, out):
        super().mount_extra(bridge, out)
        bridge.config('diskemu', 'generic56k')

    def arm_break(self, c):
        for name, value, size in (('mode', 3, 1), ('fired', 0, 1), ('count', 0, 2),
                                  ('action', 87, 2), ('ordinal', 1, 2)):
            address = next(d['address'] for d in c.p['image']['data']
                           if '_FSWRITEPROBE_'+name.upper()+'_' in d['name'])
            c.b.memload(address, value.to_bytes(size, 'little'))

    def fired(self, c):
        address = next(d['address'] for d in c.p['image']['data']
                       if '_FSWRITEPROBE_FIRED_' in d['name'])
        require(c.far(address, 1) == b'\x01', 'Write fault did not fire')

    def exercise(self, c):
        # ShellStart fixtures skip boot-time ASSIGN; retain command-directory
        # lookup without adding an assignment lifetime to this focused case.
        c.command('PATH SET SYS:C')
        c.command('ALIAS HI "HELLO"')
        for mount, filesystem in (('WORKM', 'mydos'), ('WORKS', 'sdfs')):
            print('Append shell', filesystem, flush=True)
            expected = self.expected_files[filesystem]
            c.command(f'ECHO first >>{mount}:LOG.TXT')
            c.command(f'ECHO second >> "{mount}:LOG.TXT" <NIL:')
            c.command(f'HI >>{mount}:LOG.TXT')
            c.command(f'CAT <SYS:BIG.TXT >>{mount}:LOG.TXT')
            c.command(f'HELLO | WC >>{mount}:LOG.TXT')
            log = b'first\nsecond\nHello from disk!\n'+self.payload+b'1 3 17\n'
            c.command(f'MISSING >>{mount}:LOG.TXT', error=205)
            c.command(f'CAT {mount}:LOG.TXT', log)
            c.command(f'ECHO replaced >{mount}:LOG.TXT')
            c.command(f'CAT {mount}:LOG.TXT', b'replaced\n')
            expected['LOG.TXT'] = b'replaced\n'
            c.command(f'CAT SYS:BIG.TXT >>{mount}:APPEND.BIN')
            expected['APPEND.BIN'] += self.payload
            c.command(f'ECHO bad <NIL: >>{mount}:MISSING/X', error=205,
                      diagnostic='Shell')
            c.command(f'ECHO bad >>{mount}:LOG.TXT >NIL:', error=115,
                      diagnostic='Shell')
            c.command(f'ECHO bad >>>{mount}:LOG.TXT', error=115,
                      diagnostic='Shell')
            c.command(f'ECHO seed >{mount}:BREAK.TXT')
            self.arm_break(c)
            c.command(f'TYPE <SYS:BIG.TXT >>{mount}:BREAK.TXT', error=304)
            self.fired(c)
            # BREAK arrives after the first tail-sector write. Its remaining
            # payload is confirmed; neither format accepts the next sector.
            prefix = self.size-(3 if filesystem == 'mydos' else 0)-len(b'seed\n')
            partial = b'seed\n'+self.payload[:prefix]
            # Keep console output newline-terminated: the shared key observer
            # models a full-width prompt, not a prompt after partial text.
            c.command(f'CAT {mount}:BREAK.TXT | WC',
                      f'1 2 {len(partial)}\n'.encode('ascii'))
            c.command(f'ECHO continued >>{mount}:BREAK.TXT')
            expected['BREAK.TXT'] = partial+b'continued\n'
        c.command('ECHO bad <SYS:BIG.TXT >>NIL:', error=219, diagnostic='Shell')
        c.command('ECHO bad >>SYS:BIG.TXT', error=214, diagnostic='Shell')
        c.command('ECHO restored', b'restored\n')
        c.check_screen('append-and-break')
        for mount, filesystem in (('WORKM', 'mydos'), ('WORKS', 'sdfs')):
            c.command(f'ECHO seed >{mount}:CLOSE.TXT')
            self.arm_close(c)
            c.command(f'ECHO late >>{mount}:CLOSE.TXT', error=6, status=20)
            self.fired(c)
            self.expected_files[filesystem]['CLOSE.TXT'] = b'seed\nlate\n'
            c.command('HELLO', b'Hello from disk!\n')
        c.check_screen('append-close-recovery')

    def persisted(self, bridge, program, out):
        time.sleep(3)
        bridge.regs()
        self.reports = {}
        for drive, filesystem in ((1, 'mydos'), (2, 'sdfs')):
            bridge._cmd_ok(f'EJECT drive={drive}')
            media = out/(filesystem+'.atr')
            audit = Audit(media.read_bytes())
            report = getattr(audit, filesystem)()
            require(audit.files == self.expected_files[filesystem],
                    'Unexpected appended files on ' + filesystem)
            self.reports[filesystem] = dict(audit=report, sha256=sha256(media))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--sector-size', type=int, choices=(128, 256), default=256)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    scenario = AppendCommands(args.sector_size)
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result = dict(status='running')
    try:
        result = run(compiler(ROOT/'build/actionc'), output, args.case,
                     size=args.sector_size, external=scenario, reuse=args.reuse,
                     pin=pin, bridge_build=ROOT/'build/shell-paced-bridge')
        result.update(commands=scenario.commands, writable_media=scenario.reports,
                      write_observers=scenario.observers, mounts=scenario.mounts,
                      configuration_overrides=dict(accuratedisk=False, diskemu='generic56k'),
                      bank_zero_delta=dict(fixed=0, per_task=0),
                      source_inputs={**result['source_inputs'], **{name:sha256(ROOT/name)
                          for name in ('tools/test_shell_append.py',
                                       'examples/shell/shell-redirection.inc')}})
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Shell append passed', args.case, args.sector_size)
