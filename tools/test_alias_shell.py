#!/usr/bin/env python3
"""Physical-key shell aliases, argument pass-through and pipeline stages."""
import argparse
import json
from pathlib import Path

from build_command import compile_command
from make_shell_disk import make
from native_program import ROOT,compiler,require,sha256
from test_o65_shell import Commands
from test_shell_core import run


class AliasShell(Commands):
    def instrument(self,out):
        super().instrument(out)
        observed=out/'shell-observed.inc'
        source=observed.read_text()
        old='  SHELLEDITPROBE.Capture(bytes,count)\n  NativeShellWrite(handle,bytes,count)'
        require(source.count(old)==1,'Stale shell output observer')
        source=source.replace(old,'''  LET header=DOSOBJECTS.Find(DOSCORE.Current(),BYTE POINTER(handle),DOSOBJECTS.KIND_FILE)
  IF header<>NULL THEN
    IF header.backend=DOSOBJECTS.BACKEND_CON THEN
      SHELLEDITPROBE.Capture(bytes,count)
    FI
  FI
  NativeShellWrite(handle,bytes,count)''')
        observed.write_text(source)

    def prepare(self,toolchain,out,mode,size):
        source=out/'files'
        source.mkdir(exist_ok=True)
        (source/'TOOLS/SUB').mkdir(parents=True,exist_ok=True)
        (source/'TOOLS/SUB/NOTE.TXT').write_text('parent path check\n')
        for name in ('HELLO','WC'):
            compile_command(toolchain,ROOT/f'examples/commands/{name.lower()}.act',
                            source/name,mode=='opt')
            for suffix in ('options.json','profile.json'):
                (source/(name+'.'+suffix)).rename(out/(name+'.'+suffix))
        make(out/'volume.atr',source,binary_names={'HELLO','WC'},sector_bytes=size)

    def exercise(self,c):
        # ShellStart skips the boot-time C: assignment; this fixture keeps
        # its command binaries at D1: rather than SYS:C.
        c.command('PATH SET D1:')
        defaults=b'MKDIR -> MAKEDIR\nLS -> LIST\nCP -> COPY\n'
        c.command('ALIAS',defaults)
        c.command('CLS',b'\x0c')
        c.check_screen('clear-screen')
        c.command('CLS >NIL:')
        c.check_screen('redirected-clear')
        c.command('CLS extra',error=115,diagnostic='Shell')
        c.command('CD TOOLS/SUB')
        c.command('CD ..')
        c.command('CD',b'D1:TOOLS\n')
        c.command('CD ..')
        c.command('CD',b'D1:\n')
        c.command('CD ..')
        c.command('CD',b'D1:\n')
        c.command('ALIAS HI "ECHO hello"')
        c.command('ALIAS',defaults+b'HI -> ECHO hello\n')
        c.command('ALIAS HI',b'HI -> ECHO hello\n')
        c.command('hi world',b'hello world\n')
        c.command('HI world >NIL:')
        c.command('ALIAS HI "ECHO bye"')
        c.command('HI world',b'bye world\n')
        c.command('ALIAS H HELLO')
        c.command('ALIAS COUNT WC')
        c.command('H | COUNT',b'1 3 17\n')
        c.command('HELLO | COUNT',b'1 3 17\n')
        c.command('ALIAS 1BAD ECHO',error=311)
        c.command('ALIAS HELP ECHO',error=311)
        c.command('ALIAS CLS ECHO',error=311)
        c.command('ALIAS X "ECHO hi|WC"',error=311)
        c.command('UNALIAS HI')
        c.command('ALIAS HI',error=205)
        c.command('UNALIAS HI',error=205)
        c.command('HI',error=205)
        c.command('ALIAS',defaults+b'H -> HELLO\nCOUNT -> WC\n')
        c.check_screen('aliases')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    scenario=AliasShell()
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result=run(compiler(ROOT/'build/actionc'),args.output.resolve(),args.case,
               external=scenario,pin=pin,bridge_build=ROOT/'build/shell-paced-bridge',
               reuse=args.reuse)
    result.update(tier='development',runner_sha256=sha256(Path(__file__)))
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Alias shell checks passed',args.case,flush=True)
