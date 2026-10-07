#!/usr/bin/env python3
"""EXECUTE through physical shell keys, loaded commands and owned source faults."""
import argparse
import json
import shutil
from pathlib import Path

from build_command import compile_command
from filesystem_audit import Audit
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from stack_budget import stack_usage
from test_filesystem_write_shell import WritableCommands
from test_shell_core import draw, run


class Scripts(WritableCommands):
    exit_command = 'EXECUTE EXIT >WORKM:EXIT.TXT'

    def __init__(self):
        self.mounts = [dict(alias='D1', unit=49, sectors=1440,
                            sector_bytes=128, profile=4)]
        for alias, unit, filesystem, format_id in (
                ('WORKM', 50, 'mydos', 1), ('WORKS', 51, 'sdfs', 2)):
            image = Audit((ROOT/f'tests/fixtures/filesystem-write/{filesystem}-256.atr').read_bytes()).image
            self.mounts.append(dict(alias=alias, unit=unit, sectors=image.count,
                                    sector_bytes=256, profile=4, format=format_id,
                                    access='readwrite'))

    def instrument(self, out):
        super().instrument(out)
        observed = out/'shell-observed.inc'
        source = observed.read_text().replace('USE EXEC\n',
            'USE EXEC\nUSE EXECUTEPROBE\nUSE HEAPCORE\n', 1)
        source = source.replace(str(ROOT/'examples/shell/shell-execute.inc'),
                                str(out/'shell-execute.inc'))
        marker = '      ShellCommand()\n      commandCount==+1'
        require(source.count(marker) == 1, 'Stale EXECUTE cleanup checkpoint')
        source = source.replace(marker, '''      ShellCommand()
      IF script<>NULL OR DOS.Input()<>shell.console
          OR DOS.Output()<>shell.console OR shell.tempInput<>NULL
          OR shell.tempOutput<>NULL OR shell.oldInput<>NULL
          OR shell.oldOutput<>NULL OR shell.redirectActive<>0
          OR shell.restoreFailure<>0 THEN
        HEAPCORE.Abort($e5f2)
      FI
      commandCount==+1''')
        observed.write_text(source)
        script = (ROOT/'examples/shell/shell-execute.inc').read_text()
        script = script.replace('EXEC.AllocMem(SIZEOF(ShellScript),', 'EXECUTEPROBE.Allocate(SIZEOF(ShellScript),')
        script = script.replace('DOS.Read(script.source,', 'EXECUTEPROBE.Read(script.source,')
        # The proxy consumes the real wrapper before losing its completion;
        # production ShellCloseTemporary must discover it is terminal.
        script = script.replace('    IF ShellCloseTemporary(script.source)=0 THEN', '''    EXECUTEPROBE.source=script.source
    IF ShellCloseTemporary(script.source)=0 THEN''')
        (out/'shell-execute.inc').write_text(script)
        redirect = (ROOT/'examples/shell/shell-redirection.inc').read_text()
        redirect = redirect.replace('DOS.Close(handle)', 'EXECUTEPROBE.Close(handle)')
        observed.write_text(observed.read_text().replace(
            str(ROOT/'examples/shell/shell-redirection.inc'), str(out/'shell-redirection.inc')))
        (out/'shell-redirection.inc').write_text(redirect)
        (out/'executeprobe.act').write_text('''MODULE EXECUTEPROBE
USE DOS
USE EXEC
PUBLIC DOS.FileHandle POINTER source
PUBLIC BYTE readMode,closeMode,fired,failAllocate,waiting
PUBLIC CARD reads

PUBLIC BYTE POINTER FUNC Allocate(LONGCARD amount,flags)

  IF failAllocate<>0 THEN
    failAllocate=0
    fired=1
    RETURN(NULL)
  FI

RETURN(EXEC.AllocMem(amount,flags))

PUBLIC LONGINT FUNC Read(DOS.FileHandle POINTER file BYTE POINTER bytes
    LONGINT length)

  reads==+1
  IF readMode=3 THEN
    waiting=1
    WHILE DOS.BreakPending()=0 DO
      EXEC.Yield()
    OD

    waiting=0
    readMode=0
  FI

  IF readMode=1 AND reads=2 THEN
    fired=1
    readMode=0
    DOS.SetIoErr(6)
    RETURN(-1)
  FI

  IF readMode=2 THEN
    length=1
  FI

RETURN(DOS.Read(file,bytes,length))

PUBLIC LONGINT FUNC Close(DOS.FileHandle POINTER file)

  LET result=DOS.Close(file)
  IF file=source THEN
    source=NULL
    IF closeMode<>0 AND result<>0 THEN
      closeMode=0
      fired=1
      DOS.SetIoErr(6)
      RETURN(0)
    FI
  FI

RETURN(result)
ENDMODULE
''')

    def prepare(self, toolchain, out, mode, size):
        source = out/'files'
        shutil.rmtree(source, ignore_errors=True)
        command_dir = source/'C'
        command_dir.mkdir(parents=True)
        self.commands = {}
        for name, path in (
                ('HELLO', 'examples/commands/hello.act'),
                ('CAT', 'examples/commands/cat.act'),
                ('WC', 'examples/commands/wc.act'),
                ('GREP', 'examples/commands/grep.act'),
                ('WAIT', 'tests/programs/disk_wait.act'),
                ('STATUS', 'tests/programs/disk_status.act')):
            self.commands[name] = compile_command(toolchain, ROOT/path,
                command_dir/name, mode == 'opt')
            for suffix in ('options.json', 'profile.json'):
                (command_dir/(name+'.'+suffix)).rename(out/(name+'.'+suffix))
        scripts = {
            'BASIC': b'; comment\r\n \t\r\nECHO first\r\nALIAS SAY "ECHO scripted"\r'
                     b'SAY words\nHELLO | WC\x9bCD SUB\nECHO last',
            'EMPTY': b'',
            'COMMENTS': b'\n \t\n; ignored\r\n \t; indented\x9b',
            'INPUT': b'CAT\nECHO after\n',
            'OVERRIDE': b'CAT <SYS:OTHER.TXT\nCAT\nECHO after\n',
            'WARN': b'GREP absent SYS:INPUT.TXT\nECHO continued\n',
            'WARNLAST': b'GREP absent SYS:INPUT.TXT\n; keep WARN\n',
            'ERROR': b'ECHO before\nMISSING\nECHO forbidden\n',
            'FAIL': b'ECHO before\nSTATUS\nECHO forbidden\n',
            'SYNTAX': b'ECHO before\nECHO "broken\nECHO forbidden\n',
            'NEST': b'EXECUTE SYS:BASIC >WORKM:NEST.TXT\nECHO forbidden\n',
            'LIMIT': b'ECHO '+b'x'*250+b'\n',
            'OVER': b'ECHO '+b'x'*251+b'\nECHO forbidden\n',
            'NUL': b'ECHO forbidden\0 suffix\nECHO forbidden\n',
            'SPLIT': b';'+b'x'*62+b'\r\nECHO split\r\nECHO final',
            'READERR': b'ECHO before\n;'+b'x'*70+b'\nECHO forbidden\n',
            'CLOSE': b'ECHO completed\n',
            'BREAK': b'WAIT\nECHO forbidden\n',
            'EXIT': b'ECHO goodbye\nEXIT\nECHO forbidden\n',
        }
        for mount in ('WORKM', 'WORKS'):
            scripts[mount] = (f'ECHO outer1\nECHO inner >{mount}:INNER.TXT\n'
                              'ECHO outer2\n').encode('ascii')
        (source/'SUB').mkdir()
        (source/'INPUT.TXT').write_bytes(b'selected input\n')
        (source/'OTHER.TXT').write_bytes(b'override input\n')
        for name, payload in scripts.items():
            (source/name).write_bytes(payload)
        self.files = make(out/'volume.atr', source, sectors=1440,
                          binary_names={'C/'+name for name in self.commands}|set(scripts))
        self.expected_files = {}
        for filesystem in ('mydos', 'sdfs'):
            media = out/(filesystem+'.atr')
            shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-256.atr', media)
            audit = Audit(media.read_bytes())
            getattr(audit, filesystem)()
            self.expected_files[filesystem] = dict(audit.files)

    def mount_extra(self, bridge, out):
        super().mount_extra(bridge, out)
        bridge.config('diskemu', 'generic56k')

    def probe(self, c, name, value, size=1):
        address = next(d['address'] for d in c.p['image']['data']
                       if '_EXECUTEPROBE_'+name.upper()+'_' in d['name'])
        c.b.memload(address, value.to_bytes(size, 'little'))
        return address

    def exercise(self, c):
        c.command('PATH SET SYS:C')
        c.command('EXECUTE "SYS:BASIC"', b'first\nscripted words\n1 3 17\nlast\n')
        c.command('CD', b'D1:SUB\n')
        c.command('CD SYS:')
        c.command('SAY retained', b'scripted retained\n')
        c.command('ALIAS DO "EXECUTE"')
        c.command('DO COMMENTS')
        c.command('EXECUTE EMPTY')
        c.command('EXECUTE INPUT <SYS:INPUT.TXT', b'selected input\nafter\n')
        c.command('EXECUTE OVERRIDE <SYS:INPUT.TXT',
                  b'override input\nselected input\nafter\n')
        c.command('EXECUTE WARN', b'continued\n')
        c.command('EXECUTE WARNLAST', status=5)
        c.command('EXECUTE ERROR', b'before\n', error=205, diagnostic='MISSING')
        c.command('EXECUTE FAIL', b'before\n', status=20, diagnostic='STATUS')
        c.command('EXECUTE SYNTAX', b'before\n', error=115, diagnostic='Shell')
        c.command('EXECUTE NEST', error=209)
        c.command('EXECUTE LIMIT', b'x'*250+b'\n')
        c.command('EXECUTE OVER', error=120)
        c.command('EXECUTE NUL', error=115)
        c.command('EXECUTE SPLIT', b'split\nfinal\n')
        self.probe(c, 'readMode', 2)
        c.command('EXECUTE SPLIT', b'split\nfinal\n')
        self.probe(c, 'readMode', 0)
        c.command('EXECUTE MISSING', error=205)
        self.probe(c, 'failAllocate', 1)
        c.command('EXECUTE CLOSE', error=103)
        c.command('EXECUTE CON:', error=212)
        c.command('EXECUTE', error=115, diagnostic='Shell')
        c.command('EXECUTE ""', error=115, diagnostic='Shell')
        c.command('EXECUTE BASIC extra', error=115, diagnostic='Shell')
        c.command('EXECUTE BASIC | WC', error=115, diagnostic='Shell')
        for mount, filesystem in (('WORKM', 'mydos'), ('WORKS', 'sdfs')):
            c.command(f'EXECUTE {mount} >{mount}:OUT.TXT')
            c.command(f'EXECUTE CLOSE >>{mount}:OUT.TXT')
            c.command(f'CAT {mount}:OUT.TXT', b'outer1\nouter2\ncompleted\n')
            c.command(f'CAT {mount}:INNER.TXT', b'inner\n')
            self.expected_files[filesystem].update(
                {'OUT.TXT': b'outer1\nouter2\ncompleted\n', 'INNER.TXT': b'inner\n'})
        c.check_screen('script-functional')
        self.probe(c, 'reads', 0, 2)
        self.probe(c, 'readMode', 1)
        fired = self.probe(c, 'fired', 0)
        c.command('EXECUTE READERR', b'before\n', error=6)
        require(c.far(fired, 1) == b'\x01', 'Script read failure did not fire')
        self.probe(c, 'closeMode', 1)
        self.probe(c, 'fired', 0)
        c.command('EXECUTE CLOSE', b'completed\n', error=6, status=20)
        require(c.far(fired, 1) == b'\x01', 'Script Close failure did not fire')
        self.probe(c, 'closeMode', 1)
        self.probe(c, 'fired', 0)
        c.command('EXECUTE ERROR', b'before\n', error=205, diagnostic='MISSING')
        require(c.far(fired, 1) == b'\x01', 'Causal Close failure did not fire')
        c.command('HELLO', b'Hello from disk!\n')
        c.check_screen('script-fault-recovery')
        c.append('EXECUTE BREAK')
        previous = c.b.peek16(c.at('commandCount'))
        c.press('\n')
        processes = c.p['build']['memory']['process_storage']['BASE']
        c.rendezvous(f'(db(${processes+4*128+77:x})=2)&(db(${processes+4*128+117:x})=2)')
        c.press('\x03')
        c.rendezvous(f'dw(${c.at("commandCount"):x})={previous+1}')
        c.ready()
        c.expected.extend(b'\n')
        c.line.clear()
        c.expected.extend(draw(c.line))
        require(c.far(c.state['shell']+32, 8) ==
                (10).to_bytes(4, 'little')+(304).to_bytes(4, 'little'),
                'Script BREAK did not stop the following command')
        # A physical BREAK while the parent is reading script text also
        # unwinds inherited streams; no command from the returned block runs.
        waiting = self.probe(c, 'waiting', 0)
        self.probe(c, 'readMode', 3)
        c.append('EXECUTE CLOSE <NIL: >WORKM:READBRK.TXT')
        previous = c.b.peek16(c.at('commandCount'))
        c.press('\n')
        c.rendezvous(f'db(${waiting:x})=1')
        c.press('\x03')
        c.rendezvous(f'dw(${c.at("commandCount"):x})={previous+1}')
        c.ready()
        c.expected.extend(b'\n')
        c.line.clear()
        c.expected.extend(draw(c.line))
        require(c.far(c.state['shell']+32, 8) ==
                (10).to_bytes(4, 'little')+(304).to_bytes(4, 'little'),
                'Script source BREAK did not stop dispatch')
        self.expected_files['mydos']['READBRK.TXT'] = b''
        self.stacks = stack_usage(c.b, c.p['build']['memory'])
        c.command('HELLO', b'Hello from disk!\n')
        c.check_screen('script-break-recovery')
        self.expected_files['mydos']['EXIT.TXT'] = b'goodbye\n'

    def persisted(self, bridge, program, out):
        self.reports = {}
        for drive, filesystem in ((1, 'mydos'), (2, 'sdfs')):
            bridge._cmd_ok(f'EJECT drive={drive}')
            media = out/(filesystem+'.atr')
            audit = Audit(media.read_bytes())
            report = getattr(audit, filesystem)()
            require(audit.files == self.expected_files[filesystem],
                    'Unexpected script files on '+filesystem)
            self.reports[filesystem] = dict(audit=report, sha256=sha256(media))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    scenario = Scripts()
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    result = run(compiler(ROOT/'build/actionc'), output, 'opt', external=scenario,
                 reuse=args.reuse, pin=pin, bridge_build=ROOT/'build/shell-paced-bridge')
    result.update(tier='development', commands=scenario.commands,
                  writable_media=scenario.reports, mounts=scenario.mounts,
                  stacks=scenario.stacks, bank_zero_delta=dict(fixed=0, per_task=0),
                  configuration_overrides=dict(diskemu='generic56k', accuratedisk=False),
                  source_inputs={**result['source_inputs'], **{name:sha256(ROOT/name)
                      for name in ('examples/shell/shell-execute.inc',
                                   'examples/shell/shell-redirection.inc',
                                   'tools/test_shell_execute.py')}})
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('EXECUTE shell passed')
