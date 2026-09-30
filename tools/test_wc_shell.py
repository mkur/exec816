#!/usr/bin/env python3
"""Small physical-shell smoke test of the serialized WC command."""
import argparse
import json
import shutil
from pathlib import Path

from build_command import compile_command
from make_shell_disk import make
from native_program import ROOT, compiler, read_build, require, sha256
from test_o65_shell import Commands
from test_shell_core import run


class WordCount(Commands):
    def prepare(self, toolchain, out, mode, size):
        require(size == 128, 'WC smoke geometry')
        source = out/'files'
        source.mkdir(exist_ok=True)
        self.command = compile_command(toolchain, ROOT/'examples/commands/wc.act', source/'WC', mode=='opt')
        (source/'WC.options.json').rename(out/'WC.options.json')
        (source/'WC.profile.json').rename(out/'WC.profile.json')
        (source/'WORDS.TXT').write_bytes(b'one two\r\nthree\x9bfour\nfive')
        make(out/'volume.atr', source, binary_names={'WC', 'WORDS.TXT'})

    def exercise(self, c):
        c.command('WC <NIL:', b'0 0 0\n')
        c.command('WC <WORDS.TXT', b'3 5 24\n')
        c.command('WC extra <NIL:', error=115)
        c.check_screen('wc')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kernel-build', type=Path, help='Reuse an unchanged test_o65_shell build; compile only WC')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.kernel_build:
        base = args.kernel_build.resolve()
        require(base != out, 'Preserve the original shell evidence')
        p = read_build(base)
        require(p['build']['optimize'] == (args.case == 'opt'), 'Wrong shell mode')
        for field in ('platform_inputs', 'task_inputs', 'console_inputs', 'banked_inputs'):
            for name, digest in p['build'].get(field, {}).items():
                require(sha256(ROOT/name) == digest, 'Stale shell input: '+name)
        for source in base.iterdir():
            if source.is_file() and source.suffix not in ('.log', '.atr') and source.name != 'results.json':
                shutil.copyfile(source, out/source.name)
        shutil.copytree(base/'task-kernel', out/'task-kernel', dirs_exist_ok=True)
        frozen = {name:sha256(out/name) for name in ('shell-observed.inc', 'doscooked.act', 'programapi.act', 'shelleditprobe.act')}
        # Verify that the currently selected observers reproduce the build's
        # saved sources before reusing its emitted machine code.
        from test_shell_core import instrument
        instrument(out)
        WordCount().instrument(out)
        require(all(sha256(out/name) == digest for name, digest in frozen.items()), 'Changed shell observers')
    scenario = WordCount()
    result = run(compiler(ROOT/'build/actionc'), out, args.case, external=scenario, reuse=bool(args.kernel_build))
    result.update(command=scenario.command, runner_sha256=sha256(Path(__file__)), bank_zero_delta=dict(fixed=0, per_task=0))
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('WC physical shell smoke passed:', args.case)
