#!/usr/bin/env python3
"""Physical command search, template help and diagnostics on the pinned shell."""
import argparse
import json
from pathlib import Path

from build_command import compile_command
from make_shell_disk import make
from native_program import ROOT, compiler, sha256
from stack_budget import stack_usage
from test_shell_core import run
from test_toolbox import TEMPLATES
from test_toolbox_shell import Toolbox


class Usability(Toolbox):
    def prepare(self, toolchain, out, mode, size):
        super().prepare(toolchain,out,mode,size)
        files=out/'files'
        self.commands['ASSIGN']=compile_command(toolchain,ROOT/'examples/commands/assign.act',files/'ASSIGN',mode=='opt')
        for suffix in ('.options.json','.profile.json'):
            (files/('ASSIGN'+suffix)).rename(out/('ASSIGN'+suffix))
        for name in ('WORK','ONE','TWO','TOOLS'):(files/name).mkdir(exist_ok=True)
        (files/'WORK/HELLO').write_bytes((files/'HELLO').read_bytes()[:-1])
        (files/'TOOLS/HELLO').write_bytes((files/'HELLO').read_bytes())
        for directory,greeting in [('ONE','First'),('TWO','Second')]:
            source=out/(directory.lower()+'.act')
            source.write_text((ROOT/'examples/commands/hello.act').read_text().replace('Hello from disk!',greeting))
            target=files/directory/'WHO'
            compile_command(toolchain,source,target,mode=='opt')
            for suffix in ('.options.json','.profile.json'):
                target.with_suffix(suffix).rename(out/(directory+suffix))
        self.files=make(out/'volume.atr',files,binary_names=set(self.commands)|
                        {'WORK/HELLO','TOOLS/HELLO','ONE/WHO','TWO/WHO'})

    def exercise(self,c):
        if self.phase in ('all','path'):
            c.command('PATH',b'Current directory\nC:\n')
            # This lookup fixture deliberately assigns C: to its root binaries.
            c.command('ASSIGN C: SYS:')
            c.command('CD WORK')
            c.command('HEAD SYS:A.TXT LINES 1',b'Alpha\n')
            c.command('HELLO',error=306)
            c.command('SYS:HELLO',b'Hello from disk!\n')
            c.command('/TOOLS/HELLO',b'Hello from disk!\n')
            c.command('PATH CLEAR')
            c.command('HEAD',error=205)
            c.command('PATH SET SYS:ONE')
            c.command('PATH ADD /TWO')
            c.command('PATH ADD d1:one')
            c.command('PATH',b'Current directory\nD1:ONE\nD1:TWO\n')
            c.command('WHO',b'First\n')
            c.command('PATH SET /TWO')
            c.command('PATH ADD /ONE')
            c.command('WHO',b'Second\n')
            c.check_screen('path-order')
            c.command('PATH ADD /TOOLS')
            c.command('PATH ADD SYS:')
            c.command('PATH ADD SYS:WORK',error=303)
            c.command('PATH ADD MISSING',error=205)
            c.command('PATH SET SYS:A.TXT',error=212)
            c.command('PATH',b'Current directory\nD1:TWO\nD1:ONE\nD1:TOOLS\nSYS:\n')
            c.command('WHO',b'Second\n')
            c.command('PATH CLEAR extra',error=311)
            c.command('PATH RESET')
            c.command('PATH',b'Current directory\nC:\n')
            c.command('HEAD SYS:A.TXT|WC',b'3 3 17\n')
            c.command('HEAD SYS:A.TXT|MISSING',error=205,diagnostic='MISSING')
            c.command('CD SYS:')
            c.command('ASSIGN C:')
            c.check_screen('path-recovery')
        if self.phase in ('all','help'):
            for name,template in TEMPLATES.items():
                c.command(name.upper()+' ?',('Arguments: '+(template or '(none)')+'\n').encode())
            c.command('HEAD ? <A.TXT >NIL:',b'Arguments: FILE,LINES/K/N\n')
            c.command('HEAD MISSING',error=205)
            c.command('HEAD MISSING >NIL:',error=205)
            c.command('HEAD A.TXT LINES -1',b'Arguments: FILE,LINES/K/N\n',error=115)
            c.command('HEAD ?|WC',b'Arguments: FILE,LINES/K/N\n0 0 0\n')
            c.command('CAT LONG.TXT|HEAD ?',b'Arguments: FILE,LINES/K/N\n')
            c.command('GREP absent A.TXT|HEAD MISSING',error=205,diagnostic='HEAD')
            c.command('GREP absent A.TXT',status=5)
            c.command('CAT LONG.TXT|HEAD LINES 1',b'x\n')
            c.command('ECHO recovered',b'recovered\n')
            c.check_screen('help-diagnostics')
            # A rejected input line belongs to the shell, not the last command.
            from test_shell_core import draw, diagnostic_text
            c.append('ECHO '+'a'*250)
            c.press('b');c.expected.extend(draw(b'',bytes(c.line)))
            c.press('\n');c.ready()
            c.expected.extend(b'\n'+diagnostic_text(120,'Shell'))
            c.line.clear();c.expected.extend(draw(c.line))
            c.check_screen('input-error-header')
        self.stacks=stack_usage(c.b,c.p['build']['memory'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=('all','path','help'),default='all')
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args();scenario=Usability();scenario.phase=args.phase
    out=args.output.resolve()
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result=run(compiler(ROOT/'build/actionc'),out,args.case,external=scenario,
               reuse=args.reuse,pin=pin,bridge_build=ROOT/'build/shell-paced-bridge')
    result.update(tier='development',phase=args.phase,commands=scenario.commands,
                  stacks=scenario.stacks,runner_sha256=sha256(Path(__file__)))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Command usability shell passed:',args.case,flush=True)
