#!/usr/bin/env python3
"""Serialized disk commands through the production shell and physical keyboard."""
import argparse
import json
from pathlib import Path
from build_command import compile_command
from library_paths import read_source
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from o65_fixtures import inspect
from test_shell_core import run, draw


class Commands:
    def instrument(self, out):
        source = read_source(ROOT/'lib/dos/programapi.act').replace('USE PROCESS','USE PROCESS\nUSE DOSOBJECTS\nUSE DOSCORE\nUSE SHELLEDITPROBE')
        require(source.count('RETURN(DOSCALLS.Write(handle,buffer,length))') == 1, 'Stale command Write observer')
        source = source.replace('RETURN(DOSCALLS.Write(handle,buffer,length))', """  DOSOBJECTS.Header POINTER header
  LONGINT count
  count=DOSCALLS.Write(handle,buffer,length)
  IF count>0 THEN
    header=DOSOBJECTS.Find(DOSCORE.Current(),handle,DOSOBJECTS.KIND_FILE)
    IF header<>DOSOBJECTS.Header POINTER(0) THEN
      IF header.backend=DOSOBJECTS.BACKEND_CON THEN SHELLEDITPROBE.Capture(buffer,CARD(count)) FI
    FI
  FI
RETURN(count)""")
        (out/'programapi.act').write_text(source)

    def prepare(self, toolchain, out, mode, size):
        require(size == 128, 'L3 media geometry')
        self.mode = mode
        source = out/'files'
        (source/'TOOLS').mkdir(parents=True, exist_ok=True)
        self.commands = {}
        for name, path in [('HELLO','examples/commands/hello.act'),
                           ('ECHOARGS','examples/commands/echoargs.act'),
                           ('CAT','examples/commands/cat.act'),
                           ('WC','examples/commands/wc.act'),
                           ('READ','tests/programs/disk_read.act'),
                           ('WAIT','tests/programs/disk_wait.act'),
                           ('STATUS','tests/programs/disk_status.act')]:
            self.commands[name] = compile_command(toolchain,ROOT/path,source/name,mode=='opt')
            # Build metadata stays outside the DOS volume.
            (source/(name+'.options.json')).rename(out/(name+'.options.json'))
            (source/(name+'.profile.json')).rename(out/(name+'.profile.json'))
        hello = (source/'HELLO').read_bytes()
        (source/'TOOLS'/'HELLO').write_bytes(hello)
        (source/'BAD').write_bytes(hello[:-1])
        bad = bytearray(hello)
        info = inspect(bad)
        ordinary = 1
        bad[info['positions'][f'import{ordinary}.signature']] ^= 1
        (source/'IMPORT').write_bytes(bad)
        (source/'TEXT.TXT').write_text('selected input\n')
        (source/'STORY.TXT').write_text((ROOT/'examples/demo-disk/STORY.TXT').read_text())
        binary = {*self.commands, 'TOOLS/HELLO', 'BAD', 'IMPORT'}
        self.files = make(out/'volume.atr',source,binary_names=binary)

    def exercise(self, c):
        c.command('help',b'HELP ECHO CLS CD DIR TYPE MEM TASKS VER MOUNT DEVICES PATH ALIAS UNALIAS RUN JOBS BREAK EXECUTE EXIT\nEdit: Ctrl-A/E home/end, B/F left/right\nCtrl-U clear, K cut end, W cut word\nCtrl-L clear screen\nHistory: Ctrl-P/N or Atari up/down\nAtari left/right move the cursor\n')
        c.command('HELLO',b'Hello from disk!\n')
        c.command('ECHOARGS "two words" "" x',b'"two words" "" x\n')
        c.command('D1:HELLO',b'Hello from disk!\n')
        c.command('cd tools')
        c.command('HELLO',b'Hello from disk!\n')
        c.command('D1:ECHOARGS "a**b*"c"',b'"a**b*"c"\n')
        c.command('cd /')
        c.command('MISSING',error=205)
        c.command('BAD',error=306)
        c.command('IMPORT',error=309)
        c.command('HELLO >NIL:')
        c.command('READ <TEXT.TXT',b'selected input\n')
        c.command('READ <NIL:')
        c.command('HELLO >TEXT.TXT',error=214,diagnostic='Shell')
        c.command('STATUS',status=20)
        # The raw resident kernel plus the 80 KiB console observer leaves too
        # little heap for two bank-aligned Images. Keep raw serial coverage;
        # exercise concurrent loaded commands in the optimized shell.
        if self.mode == 'opt':
            story=self.files['STORY.TXT']
            lines=story.count(b'\n')
            counts=f'{lines} {len(story.split())} {len(story)}\n'.encode('ascii')
            c.command('CAT STORY.TXT|WC',counts)
        c.command('HELLO',b'Hello from disk!\n')
        for _ in range(3):c.command('ECHOARGS again',b'again\n')
        c.check_screen('disk-commands')
        # Wait until the loaded child, rather than its parent, owns foreground.
        c.append('WAIT')
        previous=c.b.peek16(c.at('commandCount'))
        c.press('\n')
        processes=c.p['build']['memory']['process_storage']['BASE']
        # RUNNING is published before the child adopts its foreground scope.
        # Wait for the actual handoff, so the key targets this command.
        c.rendezvous(f'(db(${processes+4*128+77:x})=2)&(db(${processes+4*128+117:x})=2)')
        c.press('\x03')
        c.rendezvous(f'dw(${c.at("commandCount"):x})={previous+1}')
        c.ready()
        c.expected.extend(b'\n');c.line.clear();c.expected.extend(draw(c.line))
        result=c.far(c.state['shell']+32,8)
        require(tuple(int.from_bytes(result[i:i+4],'little',signed=True) for i in (0,4))==(10,304), 'Loaded foreground break result')
        c.command('HELLO',b'Hello from disk!\n')
        c.check_screen('disk-break-recovery')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true',help='Replay the recorded native build; never rebuild it implicitly')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    commands=Commands()
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result=run(compiler(ROOT/'build/actionc'),out,args.case,external=commands,reuse=args.reuse,
               pin=pin,bridge_build=ROOT/'build/shell-paced-bridge')
    result.update(pipeline_checked=args.case=='opt',commands=commands.commands,files={name:len(value) for name,value in commands.files.items()},
        source_inputs={**result['source_inputs'], **{str(p.relative_to(ROOT)):sha256(p) for p in [ROOT/'lib/dos/programfile.act',ROOT/'tools/test_o65_shell.py']}},
        overrides={name:sha256(out/name) for name in ('programapi.act','doscooked.act','shelleditprobe.act')})
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Disk shell passed',args.case,flush=True)
