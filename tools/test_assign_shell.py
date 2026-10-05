#!/usr/bin/env python3
"""Physical-key ASSIGN command, DOS routing and symbolic PATH on both disks."""
import argparse
import json
import time
from pathlib import Path

from filesystem_audit import Audit
from native_program import ROOT,compiler,require,sha256
from test_shell_core import run
from test_write_commands_shell import WriteToolbox


class AssignShell(WriteToolbox):
    def exercise(self,c):
        for mount in ('WORKM','WORKS'):
            c.command(f'ASSIGN DATA: {mount}:')
            c.command('ASSIGN',f'DATA: -> {mount}:\n'.encode())
            c.command('ASSIGN DATA: SYS:STORY.TXT',error=212)
            c.command('COPY SYS:STORY.TXT DATA:ALIAS.TXT')
            c.command('CMP SYS:STORY.TXT DATA:ALIAS.TXT')
        c.command('MAKEDIR DATA:DIR')
        c.command('DELETE DATA:DIR')
        c.command('RENAME WORKM:ALIAS.TXT DATA:OTHER.TXT',error=215)
        c.command('RENAME DATA:ALIAS.TXT WORKS:ALIAS2.TXT')
        c.command('RENAME WORKS:ALIAS2.TXT DATA:ALIAS.TXT')
        c.command('ASSIGN C: SYS:')
        c.command('PATH CLEAR')
        c.command('CD WORKM:')
        c.command('HELLO',error=205)
        c.command('PATH SET C:')
        c.command('PATH',b'Current directory\nC:\n')
        c.command('HELLO',b'Hello from disk!\n')
        c.command('ASSIGN C: WORKS:')
        c.command('HELLO',error=205)
        c.command('SYS:ASSIGN C: SYS:')
        c.command('HELLO',b'Hello from disk!\n')
        c.command('CD SYS:')
        c.command('PATH RESET')
        c.command('ASSIGN C:')
        c.command('ASSIGN DATA:')
        c.command('ASSIGN')
        c.command('CAT DATA:ALIAS.TXT',error=218)
        c.command('ASSIGN ?',b'Arguments: NAME,TARGET\n')
        c.check_screen('assign')

    def persisted(self,bridge,program,out):
        time.sleep(3)
        bridge.regs()
        self.reports={}
        for drive,filesystem in ((1,'mydos'),(2,'sdfs')):
            bridge._cmd_ok(f'EJECT drive={drive}')
            media=out/(filesystem+'.atr')
            audit=Audit(media.read_bytes())
            report=getattr(audit,filesystem)()
            expected={**self.baselines[filesystem].files,
                      'ALIAS.TXT':self.files['STORY.TXT']}
            require(audit.files==expected,'ASSIGN writes differ: '+filesystem)
            require(audit.directories==self.baselines[filesystem].directories,
                    'ASSIGN left a directory: '+filesystem)
            self.reports[filesystem]=dict(audit=report,sha256=sha256(media))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    scenario=AssignShell()
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result=run(compiler(ROOT/'build/actionc'),args.output.resolve(),args.case,
               external=scenario,reuse=args.reuse,pin=pin,
               bridge_build=ROOT/'build/shell-paced-bridge')
    result.update(tier='development',commands=scenario.commands,
                  writable_media=scenario.reports,runner_sha256=sha256(Path(__file__)))
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ASSIGN shell checks passed',args.case,flush=True)
