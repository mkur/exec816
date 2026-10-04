#!/usr/bin/env python3
"""Disk-loaded toolbox, pipeline results and physical pager keys on the real shell."""
import argparse
import json
import subprocess
from pathlib import Path
from build_command import compile_command
from library_paths import read_source
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_o65_shell import Commands
from test_shell_core import run, draw
from stack_budget import stack_usage


class Toolbox(Commands):
    def instrument(self,out):
        super().instrument(out)
        # Observe accepted writes below the shared helper without replacing
        # its short-transfer or cancellation logic.
        source=read_source(ROOT/'lib/dos/dosutility.act').replace('USE DOSCALLS','USE DOSCALLS\nUSE TOOLBOXOUTPUT').replace('DOSCALLS.Write(handle,buffer+SIZE(used),length-used)','TOOLBOXOUTPUT.Write(handle,buffer+SIZE(used),length-used)')
        (out/'dosutility.act').write_text(source)
        (out/'toolboxoutput.act').write_text('''MODULE TOOLBOXOUTPUT
USE DOSCALLS
USE DOSOBJECTS
USE DOSCORE
USE SHELLEDITPROBE
PUBLIC LONGINT FUNC Write(BYTE POINTER handle,buffer LONGINT length)
  LET count=DOSCALLS.Write(handle,buffer,length)
  IF count>0 THEN
    BEGIN
      LET header=DOSOBJECTS.Find(DOSCORE.Current(),handle,DOSOBJECTS.KIND_FILE)
      IF header<>NULL THEN
        IF header.backend=DOSOBJECTS.BACKEND_CON OR header.backend=DOSOBJECTS.BACKEND_RAW THEN
          SHELLEDITPROBE.Capture(buffer,CARD(count))
        FI
      FI
    END
  FI
RETURN(count)
ENDMODULE
''')

    def prepare(self,toolchain,out,mode,size):
        source=out/'files';source.mkdir(exist_ok=True)
        self.commands={};self.mode=mode
        for name in ('HELLO','CAT','WC','CMP','CKSUM','HEXDUMP','HEAD','GREP','LIST','MORE'):
            self.commands[name]=compile_command(toolchain,ROOT/f'examples/commands/{name.lower()}.act',source/name,mode=='opt')
            for suffix in ('.options.json','.profile.json'):(source/(name+suffix)).rename(out/(name+suffix))
        (source/'A.TXT').write_bytes(b'Alpha\nbeta\nGamma\n')
        (source/'B.TXT').write_bytes(b'Alpha\nbetb\nGamma\n')
        (source/'PAGE.TXT').write_bytes(b'x\n'*60)
        (source/'LONG.TXT').write_bytes(b'x\n'*2048)
        self.files=make(out/'volume.atr',source,binary_names=set(self.commands))

    def pager(self,c,key,rows):
        c.append('CAT PAGE.TXT|MORE')
        previous=c.b.peek16(c.at('commandCount'))
        c.press('\n')
        c.expected.extend(b'\n'+b'x\n'*23+b'--More--');c.line.clear()
        c.rendezvous(f'dw(${c.at("captureCount"):x})={len(c.expected)}')
        # RAW keys do not increment the cooked editor's consumed counter.
        if key not in ('Q','BREAK'):
            c.b._cmd_ok(f'KEY {key} down')
            c.expected.extend(b'\r        \r'+b'x\n'*rows+b'--More--')
            c.rendezvous(f'dw(${c.at("captureCount"):x})={len(c.expected)}')
            c.b._cmd_ok(f'KEY {key} up')
        if key=='BREAK':
            c.press('\x03')
        else:
            c.b._cmd_ok('KEY Q down')
        c.rendezvous(f'dw(${c.at("commandCount"):x})={previous+1}')
        if key!='BREAK':c.b._cmd_ok('KEY Q up')
        c.ready();c.expected.extend((b'' if key=='BREAK' else b'\r        \r')+draw(c.line))
        result=c.far(c.state['shell']+32,8)
        expected=(10).to_bytes(4,'little')+(304).to_bytes(4,'little') if key=='BREAK' else bytes(8)
        require(result==expected,'MORE control pipeline result')
        c.check_screen('pager-'+key.lower())

    def outcomes(self,c):
        c.command('GREP absent A.TXT|HEAD MISSING',error=205)
        c.command('CAT MISSING|GREP absent',error=205)
        c.command('CAT LONG.TXT|HEAD LINES -1',b'Arguments: FILE,LINES/K/N\n',error=310)
        c.check_screen('pipeline-outcomes')

    def exercise(self,c):
        if getattr(self,'outcomes_only',False):
            self.outcomes(c)
            self.stacks=stack_usage(c.b,c.p['build']['memory'])
            return
        if getattr(self,'pager_key',None):
            self.pager(c,self.pager_key,23 if self.pager_key=='SPACE' else 1)
            return
        c.command('CMP A.TXT A.TXT')
        c.command('CMP A.TXT B.TXT',b'Different at byte 9\n',status=5)
        c.command('CKSUM A.TXT',subprocess.check_output(['cksum'],input=self.files['A.TXT']))
        c.command('HEAD A.TXT LINES 2',b'Alpha\nbeta\n')
        c.command('GREP BETA A.TXT NOCASE NUMBER',b'2:beta\n')
        c.command('GREP absent A.TXT',status=5)
        c.command('HEXDUMP A.TXT LENGTH 0')
        c.command('MORE A.TXT',self.files['A.TXT'])
        c.command('MORE A.TXT >NIL:')
        c.command('HEAD A.TXT LINES -1',b'Arguments: FILE,LINES/K/N\n',error=115)
        c.command('LIST NAMES',b''.join(n.encode()+b'\n' for n in self.files))
        c.command('LIST MISSING',error=205)
        c.command('HELLO|WC',b'1 3 17\n')
        c.command('CAT LONG.TXT|HEAD LINES 1',b'x\n')
        c.command('CAT LONG.TXT|HEAD LINES 0')
        c.command('LIST NAMES|GREP .TXT',b''.join(n.encode()+b'\n' for n in self.files if '.TXT' in n))
        c.command('GREP absent A.TXT|WC',b'0 0 0\n',status=5)
        c.command('CAT MISSING|HEAD',error=205)
        self.outcomes(c)
        c.check_screen('toolbox')
        self.pager(c,'Q',0)
        self.pager(c,'SPACE',23)
        self.pager(c,'RETURN',1)
        self.pager(c,'BREAK',0)
        self.stacks=stack_usage(c.b,c.p['build']['memory'])
        c.command('HELLO',b'Hello from disk!\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--pager-key',choices=('Q','SPACE','RETURN','BREAK'))
    scope.add_argument('--outcomes-only',action='store_true')
    args=parser.parse_args();out=args.output.resolve();scenario=Toolbox();scenario.pager_key=args.pager_key
    scenario.outcomes_only=args.outcomes_only
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result=run(compiler(ROOT/'build/actionc'),out,args.case,external=scenario,reuse=args.reuse,pin=pin,bridge_build=ROOT/'build/shell-paced-bridge')
    result.update(tier='development',commands=scenario.commands,bank_zero_delta=dict(fixed=0,per_task=0),runner_sha256=sha256(Path(__file__)),stacks=getattr(scenario,'stacks',None),outcomes_only=args.outcomes_only)
    (out/('pager-'+args.pager_key.lower()+'-results.json' if args.pager_key else 'results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('Toolbox shell passed:',args.case)
