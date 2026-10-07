#!/usr/bin/env python3
"""Loaded TAIL/FIND commands through physical keys and public filesystem APIs."""
import argparse
import json
import shutil
from pathlib import Path

from build_command import compile_command
from filesystem_audit import Audit
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_toolbox_shell import Toolbox
from test_shell_core import run


class TextSearch(Toolbox):
    mounts = [dict(alias='D1', unit=49, sectors=720, sector_bytes=128, profile=4)]

    def __init__(self, phase):
        self.phase = phase
        self.mounts = list(type(self).mounts)
        if phase != 'tail':
            for alias, unit, filesystem, format_id in (
                    ('MYDOS', 50, 'mydos', 1), ('SDFS', 51, 'sdfs', 2)):
                image = Audit((ROOT/f'tests/fixtures/filesystem-write/{filesystem}-256.atr').read_bytes()).image
                self.mounts.append(dict(alias=alias, unit=unit, sectors=image.count,
                    sector_bytes=256, profile=4, format=format_id))

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
        if self.phase != 'tail':
            for name in ('TREE/A.TXT', 'TREE/SUB/B.TXT',
                         'TREE/SUB/NEST/C.TXT', 'TREE/Z.TXT'):
                target = source/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'tree\n')
            for directory, depth in (('LIMIT', 7), ('TOODEEP', 8)):
                leaf = source/directory
                for number in range(1, depth+1):
                    leaf /= f'D{number}'
                leaf.mkdir(parents=True)
                (leaf/'END.TXT').write_bytes(b'end\n')
            (source/'EMPTY').mkdir()
            for filesystem in ('mydos', 'sdfs'):
                shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-256.atr',
                                out/(filesystem+'.atr'))
        self.files = make(out/'volume.atr', source,
                          binary_names={'C/'+name for name in names}|{'MIX.TXT'})

    def mount_extra(self, bridge, out):
        bridge.config('diskemu', 'generic56k')
        bridge.config('accuratedisk', 'false')
        if self.phase != 'tail':
            bridge.mount(1, str(out/'mydos.atr'))
            bridge.mount(2, str(out/'sdfs.atr'))

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
        if self.phase != 'tail':
            expected = b''.join((b'SYS:TREE/'+name+b'\n') for name in
                (b'A.TXT', b'SUB/', b'SUB/B.TXT', b'SUB/NEST/',
                 b'SUB/NEST/C.TXT', b'Z.TXT'))
            c.command('FIND SYS:TREE', expected)
            c.command('FIND SYS:TREE PATTERN *.txt',
                b'SYS:TREE/A.TXT\nSYS:TREE/SUB/B.TXT\n'
                b'SYS:TREE/SUB/NEST/C.TXT\nSYS:TREE/Z.TXT\n')
            c.command('FIND SYS:TREE PATTERN z.*', b'SYS:TREE/Z.TXT\n')
            c.command('FIND SYS:TREE/', error=210)
            c.command('FIND SYS:TREE PATTERN none*', status=5)
            c.command('FIND SYS:EMPTY', status=5)
            c.command('FIND SYS:A.TXT', error=212)
            c.command('FIND SYS:MISSING', error=205)
            c.command('FIND SYS:TREE PATTERN X/Y', error=311)
            c.command('FIND SYS:LIMIT PATTERN *.TXT',
                b'SYS:LIMIT/D1/D2/D3/D4/D5/D6/D7/END.TXT\n')
            c.command('FIND SYS:TOODEEP PATTERN *.TXT', error=217)
            c.command('FIND SYS:TOODEEP/D1 PATTERN *.TXT',
                b'SYS:TOODEEP/D1/D2/D3/D4/D5/D6/D7/D8/END.TXT\n')
            c.command('CD SYS:TREE')
            c.command('FIND PATTERN "A.?XT"', b'A.TXT\n')
            c.command('CD SYS:')
            c.command('FIND SYS:TREE PATTERN *.TXT | WC', b'4 4 73\n')
            for alias in ('MYDOS', 'SDFS'):
                c.command(f'FIND {alias}: PATTERN CHILD.*',
                          f'{alias}:SUB/CHILD.BIN\n'.encode('ascii'))
            c.command('FIND ? >NIL:', b'Arguments: DIR,PATTERN/K\n')
            c.check_screen('find')
        c.command('HELLO', b'Hello from disk!\n')

    def persisted(self, bridge, program, out):
        if self.phase != 'tail':
            for drive, filesystem in ((1, 'mydos'), (2, 'sdfs')):
                bridge._cmd_ok(f'EJECT drive={drive}')
                require(sha256(out/(filesystem+'.atr'))==sha256(
                    ROOT/f'tests/fixtures/filesystem-write/{filesystem}-256.atr'),
                    'FIND changed read-only '+filesystem+' media')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('tail', 'find', 'all'), default='all')
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
