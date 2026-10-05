#!/usr/bin/env python3
"""Loaded writable commands on both disk formats, with persisted byte audits."""
import argparse
import json
import shutil
import time
from pathlib import Path
from build_command import compile_command
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_filesystem_write_shell import WritableCommands
from test_toolbox_shell import Toolbox
from test_shell_core import run
from filesystem_audit import Audit


class WriteToolbox(WritableCommands, Toolbox):
    # Cooperative instrumentation observes both filesystem finalization and
    # console writes made through the resident WriteAll helper.
    def prepare(self,toolchain,out,mode,size):
        source=out/'files'
        source.mkdir(exist_ok=True)
        self.commands={}
        for name in ('HELLO','CAT','WC','CMP','COPY','TEE','DELETE','RENAME','MAKEDIR'):
            self.commands[name]=compile_command(toolchain,ROOT/f'examples/commands/{name.lower()}.act',source/name,mode=='opt')
            for suffix in ('options.json','profile.json'):
                (source/(name+'.'+suffix)).rename(out/(name+'.'+suffix))
        binary=bytes(range(256))*3
        for name,value in {'BINARY.BIN':binary,'DOUBLE.BIN':binary*2,'EMPTY':b'',
                           'STORY.TXT':(ROOT/'examples/demo-disk/STORY.TXT').read_bytes(),
                           'HELLO2.TXT':b'Hello from disk!\n'*2}.items():
            (source/name).write_bytes(value)
        self.files=make(out/'volume.atr',source,binary_names={*self.commands,'BINARY.BIN','DOUBLE.BIN'})
        self.baselines={}
        for filesystem in ('mydos','sdfs'):
            media=out/(filesystem+'.atr')
            shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-128.atr',media)
            audit=Audit(media.read_bytes());getattr(audit,filesystem)()
            self.baselines[filesystem]=audit

    def exercise(self,c):
        for mount in ('WORKM','WORKS'):
            c.command(f'COPY SYS:BINARY.BIN {mount}:COPY.BIN')
            c.command(f'CMP SYS:BINARY.BIN {mount}:COPY.BIN')
            c.command(f'COPY SYS:BINARY.BIN {mount}:COPY.BIN APPEND')
            c.command(f'COPY MISSING {mount}:COPY.BIN',error=205)
            c.command(f'CD {mount}:')
            c.command(f'COPY COPY.BIN {mount}:copy.bin',error=202)
            c.command(f'CMP SYS:DOUBLE.BIN {mount}:COPY.BIN')
            c.command('CD SYS:')
            c.command(f'COPY SYS:EMPTY {mount}:EMPTY')
            c.command(f'MAKEDIR {mount}:NEW')
            c.command(f'MAKEDIR {mount}:NEW',error=203)
            c.command(f'COPY SYS:STORY.TXT {mount}:NEW',error=212)
            c.command(f'COPY SYS:STORY.TXT {mount}:NEW/ONE')
            c.command(f'DELETE {mount}:NEW',error=216)
            c.command(f'RENAME {mount}:NEW/ONE {mount}:NEW/TWO')
            c.command(f'RENAME {mount}:NEW/TWO {mount}:MOVED',error=209)
            c.command(f'RENAME {mount}:NEW {mount}:RENAMED')
            c.command(f'CMP SYS:STORY.TXT {mount}:RENAMED/TWO')
            c.command(f'DELETE {mount}:RENAMED/TWO')
            c.command(f'DELETE {mount}:RENAMED')
            c.command(f'TEE {mount}:SAVE.BIN <SYS:BINARY.BIN >NIL:')
            c.command(f'CMP SYS:BINARY.BIN {mount}:SAVE.BIN')
            c.command(f'HELLO | TEE {mount}:PIPE.TXT',b'Hello from disk!\n')
            c.command(f'HELLO | TEE {mount}:PIPE.TXT APPEND',b'Hello from disk!\n')
            c.command(f'CMP SYS:HELLO2.TXT {mount}:PIPE.TXT')
            c.command(f'TEE {mount}:TEE.TXT <SYS:STORY.TXT | WC',b'24 133 746\n')
        c.command('RENAME WORKM:COPY.BIN WORKS:OTHER.BIN',error=215)
        c.command('RENAME WORKS:SAVE.BIN WORKS:COPY.BIN',error=203)
        c.command('DELETE WORKS:MISSING',error=205)
        for command in ('COPY WORKM:COPY.BIN SYS:BAD','TEE SYS:BAD <NIL:',
                        'DELETE SYS:STORY.TXT','RENAME SYS:STORY.TXT SYS:BAD','MAKEDIR SYS:BAD'):
            c.command(command,error=214)
        from test_write_commands import TEMPLATES
        for name,template in TEMPLATES.items():
            c.command(name.upper()+' ?',('Arguments: '+template+'\n').encode())
        c.check_screen('write-commands')
        self.arm_close(c)
        c.command('COPY SYS:STORY.TXT WORKM:LATE.TXT',error=6,status=10)
        c.command('HELLO',b'Hello from disk!\n')
        self.arm_close(c)
        c.command('TEE WORKS:LATE.TXT <SYS:STORY.TXT >NIL:',error=6,status=10)
        c.command('HELLO',b'Hello from disk!\n')
        c.check_screen('write-command-close-errors')

    def persisted(self,bridge,program,out):
        time.sleep(3);bridge.regs();self.reports={}
        for drive,filesystem in ((1,'mydos'),(2,'sdfs')):
            bridge._cmd_ok(f'EJECT drive={drive}')
            media=out/(filesystem+'.atr');audit=Audit(media.read_bytes())
            report=getattr(audit,filesystem)()
            expected={**self.baselines[filesystem].files,'COPY.BIN':self.files['DOUBLE.BIN'],
                      'EMPTY':b'','SAVE.BIN':self.files['BINARY.BIN'],'PIPE.TXT':self.files['HELLO2.TXT'],
                      'TEE.TXT':self.files['STORY.TXT'],'LATE.TXT':self.files['STORY.TXT']}
            require(audit.files==expected,'Persisted writable command contents differ: '+filesystem)
            require(audit.directories==self.baselines[filesystem].directories,'Directory allocation retained')
            self.reports[filesystem]=dict(audit=report,sha256=sha256(media))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    scenario=WriteToolbox();result=dict(status='running')
    try:
        pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
        result=run(compiler(ROOT/'build/actionc'),out,'opt',external=scenario,reuse=args.reuse,
                   pin=pin,bridge_build=ROOT/'build/shell-paced-bridge')
        result.update(commands=scenario.commands,writable_media=scenario.reports,
                      write_observers=scenario.observers,runner_sha256=sha256(Path(__file__)),
                      configuration_overrides=dict(accuratedisk=False),bank_zero_delta=dict(fixed=0,per_task=0))
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Writable command shell passed')
