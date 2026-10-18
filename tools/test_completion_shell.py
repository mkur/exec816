#!/usr/bin/env python3
"""Physical TAB completion with exact echo, retained cells and caret checks."""
import argparse
import json
from pathlib import Path

from make_shell_disk import make
from native_program import ROOT,compiler,require,sha256
from test_alias_shell import AliasShell
from test_shell_core import run


class CompletionShell(AliasShell):
    def instrument(self,out):
        super().instrument(out)
        profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
        profile['image_data_bytes']=8192
        self.memory_profile=out/'memory-profile.json'
        self.memory_profile.write_text(json.dumps(profile,indent=2)+'\n')

    def prepare(self,toolchain,out,mode,size):
        source=out/'files'
        (source/'TOOLS/SUB').mkdir(parents=True,exist_ok=True)
        for path in ('README.TXT','READER.TXT','TOOLS/UNIQUE','TOOLS/SUB/NOTE.TXT'):
            (source/path).write_text('completion fixture\n')
        # HE is deliberately unique among builtins and this media's files.
        make(out/'volume.atr',source,sector_bytes=size)
        self.measurements=[]

    def exercise(self,c):
        def complete(text,wanted,label,execute=None):
            c.append(text)
            previous=c.b.peek16(c.at('commandCount'))
            old=bytes(c.line)
            start=c.b.eval_expr('@frame')
            c.press('\t')
            c.ready()
            if old!=wanted:
                drawn=1+min(36,len(old)) if old else 0
                tail=wanted[-36:]
                painted=(b'<' if len(wanted)>36 else b' ')+tail
                extra=max(0,drawn-len(painted))
                c.expected.extend(b'\b'*drawn+painted+b' '*extra+b'\b'*extra)
                c.line[:]=wanted
            require(c.b.peek16(c.at('commandCount'))==previous,'TAB executed a command')
            cooked=c.state['cooked']
            # Session length is checked through the live generated layout below.
            from generate_dos import ABI
            fields={field[0]:field[2] for field in ABI['cooked']['session']['fields']}
            length=int.from_bytes(c.far(cooked+fields['length'],2),'little')
            require(c.far(cooked+fields['line'],length)==wanted,'Wrong completed snapshot: '+label)
            c.check_screen(label)
            self.measurements.append(dict(case=label,frames=c.b.eval_expr('@frame')-start,
                scope='physical TAB key-down through resumed input and visible redraw; includes host checkpoints'))
            if execute is None:c.cancel()
            else:c.submit(execute)
        # Missing C: is deliberately avoided in this direct ShellStart fixture.
        c.command('PATH SET D1:TOOLS')
        complete('HE',b'HELP ','builtin')
        complete('he',b'heLP ','folded-builtin')
        complete('E',b'E','ambiguous')
        complete('MK',b'MKDIR ','default-alias')
        c.command('ALIAS HI "ECHO hello"')
        complete('HI',b'HI ','live-alias',b'hello\n')
        c.command('UNALIAS HI')
        complete('HI',b'HI','removed-alias')
        complete('UN',b'UN','builtin-path-ambiguity')
        complete('UNI',b'UNIQUE ','path-file')
        complete('TYPE REA',b'TYPE READ','file-common-prefix')
        complete('TYPE READM',b'TYPE README.TXT ','file-unique',b'completion fixture\n')
        complete('TYPE D1:TO',b'TYPE D1:TOOLS/','explicit-directory')
        complete('TYPE D1:TOOLS/SU',b'TYPE D1:TOOLS/SUB/','nested-directory')
        complete('TYPE D1:TOOLS/SUB/NO',b'TYPE D1:TOOLS/SUB/NOTE.TXT ','nested-file',b'completion fixture\n')
        complete('TYPE MISSING/NO',b'TYPE MISSING/NO','missing-parent')
        complete('TYPE RE*',b'TYPE RE*','wildcard-noop')
        complete('TYPE "REA',b'TYPE "REA','quoted-noop')
        complete('RUN UNI',b'RUN UNI','run-command-noop')
        complete('ECHO x | UNI',b'ECHO x | UNI','pipe-command-noop')
        complete('TYPE ',b'TYPE ','empty-noop')
        complete('TYPE <READM',b'TYPE <README.TXT ','input-redirection')
        c.command('CD TOOLS/SUB')
        complete('TYPE NO',b'TYPE NOTE.TXT ','changed-directory')
        c.command('CD D1:')
        c.check_screen('completion-recovery')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    scenario=CompletionShell()
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result=run(compiler(ROOT/'build/actionc',release=True),args.output.resolve(),'opt',
               external=scenario,pin=pin,bridge_build=ROOT/'build/shell-paced-bridge',reuse=args.reuse)
    result.update(tier='development',completion=scenario.measurements,runner_sha256=sha256(Path(__file__)))
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Physical completion passed',flush=True)
