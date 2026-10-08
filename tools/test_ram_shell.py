#!/usr/bin/env python3
"""Loaded commands, redirection and RAM scripts through the physical shell."""
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


class RamCommands(WritableCommands):
    def __init__(self):
        fixture = ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr'
        self.baseline = Audit(fixture.read_bytes())
        self.baseline.sdfs()
        self.mounts = [dict(alias='D1', unit=49, sectors=2880, sector_bytes=256,
                            profile=4),
                       dict(alias='WORKS', unit=56, sectors=self.baseline.image.count,
                            sector_bytes=256, profile=4, format=2, access='readwrite'),
                       dict(alias='RAM', format=3)]

    def prepare(self, toolchain, output, mode, size):
        source = output/'files'
        command_dir = source/'C'
        command_dir.mkdir(parents=True, exist_ok=True)
        self.commands = {}
        for name in ('CAT', 'CMP', 'COPY', 'WC', 'HELLO', 'MAKEDIR', 'DELETE', 'RENAME'):
            self.commands[name] = compile_command(toolchain,
                ROOT/f'examples/commands/{name.lower()}.act', command_dir/name,
                mode == 'opt')
            for suffix in ('options.json', 'profile.json'):
                (command_dir/(name+'.'+suffix)).rename(output/(name+'.'+suffix))
        self.payload = bytes((i & 255) ^ 0x6d for i in range(70001))
        (source/'BIG.BIN').write_bytes(self.payload)
        (source/'RUNME').write_bytes(b'ECHO from RAM\nECHO appended >>RAM:LOG.TXT\n')
        self.files = make(output/'volume.atr', source, sectors=2880, sector_bytes=256,
                          binary_names={'C/'+name for name in self.commands}|{'BIG.BIN', 'RUNME'})
        shutil.copyfile(ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr',
                        output/'work.atr')

    def mount_extra(self, bridge, output):
        bridge.mount(7, str(output/'work.atr'))
        bridge.config('diskemu', 'generic56k')
        bridge.config('accuratedisk', 'false')

    def exercise(self, client):
        client.command('PATH SET SYS:C')
        client.command('ECHO first >RAM:LOG.TXT')
        client.command('ECHO second >>RAM:LOG.TXT')
        client.command('CAT RAM:LOG.TXT', b'first\nsecond\n')
        client.command('HELLO | WC >RAM:PIPE.TXT')
        client.command('CAT RAM:PIPE.TXT', b'1 3 17\n')
        client.command('COPY SYS:BIG.BIN RAM:BIG.BIN')
        client.command('CMP SYS:BIG.BIN RAM:BIG.BIN')
        client.command('COPY RAM:BIG.BIN WORKS:BIG.BIN')
        client.command('CMP RAM:BIG.BIN WORKS:BIG.BIN')
        client.command('COPY SYS:RUNME RAM:RUNME')
        client.command('EXECUTE RAM:RUNME', b'from RAM\n')
        client.command('CAT RAM:LOG.TXT', b'first\nsecond\nappended\n')
        client.command('MAKEDIR RAM:SUB')
        client.command('CD RAM:SUB')
        client.command('ECHO local >HERE.TXT')
        client.command('CAT HERE.TXT', b'local\n')
        client.command('CD ..')
        client.command('DIR SUB', b'HERE.TXT 6\n')
        client.command('RENAME SUB/HERE.TXT SUB/RENAMED.TXT')
        client.command('DELETE SUB/RENAMED.TXT')
        client.command('DELETE SUB')
        client.command('MOUNT', b'MOUNT FILESYSTEM ACCESS    STATE\n'
                       b'D1:   MyDOS      read-only mounted\n'
                       b'WORKS: SDFS       writable  mounted\n'
                       b'RAM:  RAM        writable  mounted\n')
        client.check_screen('RAM-commands-and-script')

    def persisted(self, bridge, program, output):
        bridge._cmd_ok('EJECT drive=7')
        audit = Audit((output/'work.atr').read_bytes())
        report = audit.sdfs()
        require(audit.files == {**self.baseline.files, 'BIG.BIN': self.payload},
                'RAM-to-disk copy differs from independent binary oracle')
        self.disk_report = dict(audit=report, sha256=sha256(output/'work.atr'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-bin', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    toolchain = compiler(ROOT/'build/actionc')
    if args.compiler_bin:
        toolchain['binary'] = args.compiler_bin.resolve()
        toolchain['binary_sha256'] = sha256(toolchain['binary'])
    scenario = RamCommands()
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result = run(toolchain, output, 'opt', size=256, external=scenario,
                 pin=pin, bridge_build=ROOT/'build/shell-paced-bridge')
    result['ram_disk_copy'] = scenario.disk_report
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('RAM shell passed', flush=True)
