#!/usr/bin/env python3
"""Loaded TAIL/FIND commands through physical keys and public filesystem APIs."""
import argparse
import json
import shutil
from pathlib import Path

from build_command import compile_command
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_toolbox_shell import Toolbox
from test_shell_core import run


class TextSearch(Toolbox):
    mounts = [dict(alias='D1', unit=49, sectors=720, sector_bytes=128, profile=4)]

    def __init__(self, phase):
        self.phase = phase

    def prepare(self, toolchain, out, mode, size):
        source = out/'files'
        shutil.rmtree(source, ignore_errors=True)
        command_dir = source/'C'
        command_dir.mkdir(parents=True)
        names = ['HELLO', 'CAT', 'WC', 'TAIL']
        if self.phase != 'tail':
            names.append('FIND')
        self.commands = {}
        for name in names:
            self.commands[name] = compile_command(toolchain,
                ROOT/f'examples/commands/{name.lower()}.act', command_dir/name,
                mode == 'opt')
            for suffix in ('options.json', 'profile.json'):
                (command_dir/(name+'.'+suffix)).rename(out/(name+'.'+suffix))
        self.text = b''.join(f'line{i}\n'.encode() for i in range(20))
        (source/'A.TXT').write_bytes(self.text)
        (source/'MIX.TXT').write_bytes(b'one\r\ntwo\rthree\nfour\x9blast\n')
        (source/'LONG.TXT').write_bytes(b'x\n'*2048)
        self.files = make(out/'volume.atr', source,
                          binary_names={'C/'+name for name in names}|{'MIX.TXT'})

    def mount_extra(self, bridge, out):
        bridge.config('diskemu', 'generic56k')
        bridge.config('accuratedisk', 'false')

    def exercise(self, c):
        c.command('PATH SET SYS:C')
        if self.phase != 'find':
            c.command('TAIL A.TXT', b''.join(f'line{i}\n'.encode() for i in range(10,20)))
            c.command('TAIL A.TXT LINES 1', b'line19\n')
            c.command('TAIL A.TXT LINES 0')
            c.command('CAT A.TXT | TAIL LINES 2', b'line18\nline19\n')
            c.command('TAIL <MIX.TXT LINES 3', b'three\nfour\nlast\n')
            c.command('TAIL A.TXT | WC', b'10 10 70\n')
            c.command('CAT LONG.TXT | TAIL LINES 0')
            c.command('TAIL A.TXT LINES 17', error=115)
            c.command('TAIL MISSING', error=205)
            c.command('TAIL ? <A.TXT >NIL:', b'Arguments: FILE,LINES/K/N\n')
            c.check_screen('tail')
        c.command('HELLO', b'Hello from disk!\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('tail',), default='tail')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    scenario = TextSearch(args.phase)
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result = run(compiler(ROOT/'build/actionc'), output, 'opt', external=scenario,
                 reuse=args.reuse, pin=pin, bridge_build=ROOT/'build/shell-paced-bridge')
    result.update(tier='development', phase=args.phase, commands=scenario.commands,
                  bank_zero_delta=dict(fixed=0, per_task=0),
                  configuration_overrides=dict(diskemu='generic56k', accuratedisk=False),
                  source_inputs={**result['source_inputs'],
                      'tools/test_tail_find_shell.py':sha256(Path(__file__))})
    (output/(args.phase+'-results.json')).write_text(json.dumps(result, indent=2)+'\n')
    print('TAIL/FIND shell passed:', args.phase)
