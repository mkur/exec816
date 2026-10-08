#!/usr/bin/env python3
"""Loaded bounded COPY/DELETE patterns on RAM, MyDOS and SpartaDOS."""
import argparse
import json
import shutil
from pathlib import Path

from build_command import compile_command
from filesystem_audit import Audit
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_copy_directories_shell import CopyDirectories
from test_shell_core import run


class WildcardCommands(CopyDirectories):
    def prepare(self, toolchain, output, mode, size):
        source = output/'files'
        commands = source/'C'
        commands.mkdir(parents=True, exist_ok=True)
        self.commands = {}
        for name in ('COPY', 'DELETE', 'CMP', 'MAKEDIR', 'ASSIGN'):
            self.commands[name] = compile_command(toolchain,
                ROOT/f'examples/commands/{name.lower()}.act', commands/name,
                mode == 'opt')
            for suffix in ('options.json', 'profile.json'):
                (commands/(name+'.'+suffix)).rename(output/(name+'.'+suffix))
        self.text = b'bounded wildcard copy\n'
        (source/'ONE.TXT').write_bytes(self.text)
        (source/'TWO.TXT').write_bytes(self.text*2)
        (source/'SKIP.TXT').mkdir(exist_ok=True)
        (source/'SKIP.TXT/BIN.DAT').write_bytes(bytes(range(256)))
        (source/'MANY').mkdir(exist_ok=True)
        for index in range(9):
            (source/f'MANY/A{index}.TXT').write_bytes(bytes([index])*257)
        self.files = make(output/'volume.atr', source,
            binary_names={'C/'+name for name in self.commands} |
                         {'ONE.TXT', 'TWO.TXT', 'SKIP.TXT/BIN.DAT'} |
                         {f'MANY/A{index}.TXT' for index in range(9)})
        self.baselines = {}
        for filesystem in ('mydos', 'sdfs'):
            media = output/(filesystem+'.atr')
            shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-128.atr',
                            media)
            audit = Audit(media.read_bytes())
            getattr(audit, filesystem)()
            self.baselines[filesystem] = audit

    def exercise(self, client):
        client.command('PATH SET SYS:C')
        for mount in ('RAM', 'WORKM', 'WORKS'):
            client.command(f'COPY SYS:*.t?t {mount}:')
            client.command(f'CMP SYS:ONE.TXT {mount}:ONE.TXT')
            client.command(f'CMP SYS:TWO.TXT {mount}:TWO.TXT')
            client.command(f'MAKEDIR {mount}:DEST')
            # Same-volume mutations would invalidate an active ExNext cookie.
            client.command(f'COPY {mount}:*.TXT {mount}:DEST')
            client.command(f'CMP SYS:TWO.TXT {mount}:DEST/TWO.TXT')
            client.command(f'DELETE {mount}:DEST/*.TXT')
            client.command(f'CMP SYS:ONE.TXT {mount}:DEST/ONE.TXT', error=205)
            client.command(f'CMP SYS:TWO.TXT {mount}:DEST/TWO.TXT', error=205)
            client.command(f'COPY SYS:ONE.?XT {mount}: APPEND')
            client.command(f'CMP SYS:TWO.TXT {mount}:ONE.TXT')
            client.command(f'DELETE {mount}:*.TXT')
            client.command(f'COPY SYS:*.TXT {mount}:')
        client.command('COPY SYS:MANY/* RAM:', error=118)
        client.command('CMP SYS:ONE.TXT RAM:ONE.TXT')
        client.command('CMP SYS:MANY/A0.TXT RAM:A0.TXT', error=205)
        client.command('COPY SYS:*.TXT RAM:ONE.TXT', error=212)
        client.command('COPY SYS:*.BIN RAM:', error=205)
        client.command('COPY SYS:*/ONE.TXT RAM:', error=311)
        client.command('COPY SYS:ONE.TXT RAM:*', error=311)
        client.command('DELETE RAM:ONE.TXT RAM:*.BIN', error=205)
        client.command('CMP SYS:ONE.TXT RAM:ONE.TXT')
        client.command('CD RAM:DEST')
        client.command('COPY SYS:*.TXT .')
        client.command('DELETE *.TXT')
        client.command('CD SYS:')
        client.command('ASSIGN DATA: RAM:DEST')
        client.command('COPY SYS:*.TXT DATA:')
        client.command('DELETE DATA:*.TXT')
        client.command('ASSIGN DATA:')
        client.command('MAKEDIR RAM:DEST/ONE.TXT')
        client.command('COPY SYS:*.TXT RAM:DEST', error=212)
        # DELETE includes empty directories selected by a pattern.
        client.command('DELETE RAM:DEST/*.TXT')
        client.check_screen('wildcard-commands')

    def persisted(self, bridge, program, output):
        self.reports = {}
        expected_new = {'ONE.TXT': self.text, 'TWO.TXT': self.text*2}
        for drive, filesystem in ((1, 'mydos'), (2, 'sdfs')):
            bridge._cmd_ok(f'EJECT drive={drive}')
            media = output/(filesystem+'.atr')
            audit = Audit(media.read_bytes())
            report = getattr(audit, filesystem)()
            require(audit.files == {**self.baselines[filesystem].files, **expected_new},
                    'Wildcard persisted bytes differ: '+filesystem)
            require(audit.directories == self.baselines[filesystem].directories+1,
                    'Wildcard directory namespace differs: '+filesystem)
            self.reports[filesystem] = dict(audit=report, sha256=sha256(media))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-bin', type=Path)
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    toolchain = compiler(ROOT/'build/actionc')
    if args.compiler_bin:
        toolchain['binary'] = args.compiler_bin.resolve()
        toolchain['binary_sha256'] = sha256(toolchain['binary'])
    scenario = WildcardCommands()
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result = dict(status='running')
    try:
        result = run(toolchain, output, 'opt', external=scenario, pin=pin,
                     reuse=args.reuse,
                     bridge_build=ROOT/'build/shell-paced-bridge')
        result.update(tier='development', commands=scenario.commands,
                      writable_media=scenario.reports,
                      runner_sha256=sha256(Path(__file__)),
                      configuration_overrides=dict(accuratedisk=False),
                      bank_zero_delta=dict(fixed=0, per_task=0))
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Wildcard commands shell passed', flush=True)
