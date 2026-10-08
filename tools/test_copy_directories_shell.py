#!/usr/bin/env python3
"""Loaded COPY directory targets on RAM, MyDOS and SpartaDOS through real keys."""
import argparse
import json
import shutil
from pathlib import Path

from build_command import compile_command
from filesystem_audit import Audit
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_filesystem_write_shell import WritableCommands
from test_shell_core import run


class CopyDirectories(WritableCommands):
    mounts = [{**mount, 'profile': 4} for mount in WritableCommands.mounts] + [
        dict(alias='RAM', format=3)]

    def mount_extra(self, bridge, output):
        super().mount_extra(bridge, output)
        bridge.config('diskemu', 'generic56k')

    def prepare(self, toolchain, output, mode, size):
        source = output/'files'
        commands = source/'C'
        commands.mkdir(parents=True, exist_ok=True)
        self.commands = {}
        for name in ('COPY', 'CMP', 'MAKEDIR', 'ASSIGN'):
            self.commands[name] = compile_command(toolchain,
                ROOT/f'examples/commands/{name.lower()}.act', commands/name,
                mode == 'opt')
            for suffix in ('options.json', 'profile.json'):
                (commands/(name+'.'+suffix)).rename(output/(name+'.'+suffix))
        self.text = b'copy to a directory\n'
        self.binary = bytes(range(256))*3
        (source/'ONE.TXT').write_bytes(self.text)
        (source/'TWO.TXT').write_bytes(self.text*2)
        (source/'NEST').mkdir(exist_ok=True)
        (source/'NEST/BIN.DAT').write_bytes(self.binary)
        self.files = make(output/'volume.atr', source,
            binary_names={'C/'+name for name in self.commands} |
                         {'ONE.TXT', 'TWO.TXT', 'NEST/BIN.DAT'})
        self.baselines = {}
        for filesystem in ('mydos', 'sdfs'):
            media = output/(filesystem+'.atr')
            shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-128.atr',
                            media)
            audit = Audit(media.read_bytes())
            getattr(audit, filesystem)()
            self.baselines[filesystem] = audit

    def exercise(self, client):
        # This resident shell fixture starts without the demo's C: assignment.
        client.command('PATH SET SYS:C')
        for mount in ('RAM', 'WORKM', 'WORKS'):
            client.command(f'COPY SYS:ONE.TXT {mount}:')
            client.command(f'CMP SYS:ONE.TXT {mount}:ONE.TXT')
            client.command(f'COPY SYS:ONE.TXT {mount}: APPEND')
            client.command(f'CMP SYS:TWO.TXT {mount}:ONE.TXT')
            client.command(f'COPY SYS:ONE.TXT {mount}:')
            client.command(f'MAKEDIR {mount}:DEST')
            client.command(f'COPY SYS:NEST/BIN.DAT {mount}:DEST')
            client.command(f'CMP SYS:NEST/BIN.DAT {mount}:DEST/BIN.DAT')
            client.command(f'CD {mount}:')
            client.command('COPY SYS:NEST/BIN.DAT DEST')
            client.command('CD DEST')
            client.command('COPY SYS:ONE.TXT .')
            client.command('CMP SYS:ONE.TXT ONE.TXT')
            client.command('COPY ONE.TXT .', error=202)
            client.command(f'COPY {mount}:ONE.TXT {mount}:', error=202)
            client.command(f'COPY SYS:MISSING {mount}:', error=205)
            client.command(f'COPY SYS:ONE.TXT {mount}:NOFILE')
            client.command(f'ASSIGN DATA: {mount}:DEST')
            client.command('COPY SYS:NEST/BIN.DAT DATA:')
            client.command(f'COPY DATA:BIN.DAT {mount}:DEST', error=202)
            client.command('CMP SYS:NEST/BIN.DAT DATA:BIN.DAT')
            client.command('ASSIGN DATA:')
            client.command('CD SYS:')
        client.command('CP SYS:ONE.TXT RAM:')
        client.command('COPY SYS:ONE.TXT NIL:')
        client.command('COPY NIL: RAM:', error=210)
        client.command('COPY RAM:ONE.TXT SYS:', error=214)
        client.command('CMP SYS:ONE.TXT RAM:ONE.TXT')
        client.check_screen('copy-directory-targets')

    def persisted(self, bridge, program, output):
        self.reports = {}
        expected_new = {'ONE.TXT': self.text, 'NOFILE': self.text,
                        'DEST/ONE.TXT': self.text, 'DEST/BIN.DAT': self.binary}
        for drive, filesystem in ((1, 'mydos'), (2, 'sdfs')):
            bridge._cmd_ok(f'EJECT drive={drive}')
            media = output/(filesystem+'.atr')
            audit = Audit(media.read_bytes())
            report = getattr(audit, filesystem)()
            require(audit.files == {**self.baselines[filesystem].files, **expected_new},
                    'COPY directory persisted bytes differ: '+filesystem)
            require(audit.directories == self.baselines[filesystem].directories+1,
                    'COPY directory namespace differs: '+filesystem)
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
    scenario = CopyDirectories()
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result = dict(status='running')
    try:
        result = run(toolchain, output, 'opt', external=scenario, pin=pin,
                     reuse=args.reuse,
                     bridge_build=ROOT/'build/shell-paced-bridge')
        result.update(commands=scenario.commands, writable_media=scenario.reports,
                      runner_sha256=sha256(Path(__file__)),
                      configuration_overrides=dict(accuratedisk=False),
                      bank_zero_delta=dict(fixed=0, per_task=0))
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('COPY directory targets shell passed', flush=True)
