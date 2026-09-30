#!/usr/bin/env python3
"""Short physical-shell smoke of a CAT command loaded from MyDOS."""
import argparse
import json
from pathlib import Path

from build_command import compile_command
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_o65_shell import Commands
from test_shell_core import run


class CopyCommand(Commands):
    def prepare(self, toolchain, out, mode, size):
        require(size == 128, 'CAT smoke geometry')
        source = out/'files'
        source.mkdir(exist_ok=True)
        self.command = compile_command(toolchain, ROOT/'examples/commands/cat.act', source/'CAT', mode=='opt')
        (source/'CAT.options.json').rename(out/'CAT.options.json')
        (source/'CAT.profile.json').rename(out/'CAT.profile.json')
        (source/'WORDS.TXT').write_bytes(b'one two\nthree\n')
        make(out/'volume.atr', source, binary_names={'CAT'})

    def exercise(self, c):
        c.command('CAT WORDS.TXT', b'one two\nthree\n')
        c.command('CAT <WORDS.TXT', b'one two\nthree\n')
        c.command('CAT <NIL:')
        c.command('CAT MISSING', error=205)
        c.command('CAT one two', error=115)
        c.check_screen('cat')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    scenario = CopyCommand()
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    frozen={name:sha256(out/name) for name in ('shell-observed.inc','doscooked.act','programapi.act','shelleditprobe.act')} if args.reuse else {}
    result = run(compiler(ROOT/'build/actionc'), out, 'opt', external=scenario, reuse=args.reuse,
                 pin=pin, bridge_build=ROOT/'build/shell-paced-bridge')
    require(all(sha256(out/name)==digest for name,digest in frozen.items()), 'Changed shell observers')
    result.update(command=scenario.command, runner_sha256=sha256(Path(__file__)),
                  bank_zero_delta=dict(fixed=0, per_task=0))
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('CAT physical shell smoke passed')
