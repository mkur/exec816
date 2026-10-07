#!/usr/bin/env python3
"""Optional S: startup files through the real boot entry and physical prompt."""
import argparse
import json
import shutil
from pathlib import Path

from build_command import compile_command
from make_data_disk import make
from native_program import ROOT, compiler, require, sha256
from test_shell_core import diagnostic_text, run
from test_toolbox_shell import Toolbox

SCENARIOS = ('normal', 'legacy', 'user-only', 'system-only', 'error', 'user-error',
             'warn', 'warn-last', 'wrong-type', 'remap', 'break')


class Startup(Toolbox):
    def __init__(self, scenario, filesystem, commands):
        self.scenario = scenario
        self.filesystem = filesystem
        self.commands = commands
        self.mounts = [dict(alias='D1', unit=49, sectors=2000, sector_bytes=256,
                            profile=4, format=1 if filesystem == 'mydos' else 2),
                       dict(alias='WORK', unit=56, sectors=2880, sector_bytes=256,
                            profile=4, format=1 if filesystem == 'mydos' else 2,
                            access='readwrite')]
        self.startup_result = (0, 0)
        self.startup_tasks = (3, 4)
        self.output = b''
        self.directory = b'D1:\n'
        self.assigns = b'C: -> D1:C\nS: -> D1:S\n'
        self.user_alias = False

    def instrument(self, out):
        super().instrument(out)
        source = out/'shell_core.act'
        text = source.read_text()
        text = text.replace('INCLUDE "shell-observed.inc"',
            'INCLUDE "shell-observed.inc"\nINCLUDE "'+str(ROOT/'examples/shell/shell-boot.inc')+'"')
        text = text.replace('Check(ShellStart(shellRoot)<>0)', 'Check(ShellBootStart(shellCon)<>0)')
        text = text.replace('  Pause(1)', '''  Check(script=NULL AND shell.redirectActive=0
      AND shell.tempInput=NULL AND shell.tempOutput=NULL
      AND DOS.Input()=shell.console AND DOS.Output()=shell.console)
  Pause(1)''', 1)
        # Assignments are system-wide and intentionally outlive ShellFinish.
        # Remove these two boot mappings explicitly before the heap oracle.
        marker = '  Check(FSBOOT.Stop()<>0 AND EXEC.AvailMem(0)=before)'
        require(text.count(marker) == 1, 'Missing startup allocation oracle')
        text = text.replace(marker, '''  Check(DOS.AssignPath(BYTE POINTER(c"C"),NULL)<>0)
  Check(DOS.AssignPath(BYTE POINTER(c"S"),NULL)<>0)
'''+marker)
        source.write_text(text)
        observed = out/'shell-observed.inc'
        text = observed.read_text()
        marker = '  SHELLEDITPROBE.Capture(bytes,count)\n  NativeShellWrite(handle,bytes,count)'
        require(text.count(marker) == 1, 'Missing startup Write observer')
        text = text.replace(marker, '''  IF handle=shell.console THEN
    SHELLEDITPROBE.Capture(bytes,count)
  FI
  NativeShellWrite(handle,bytes,count)''')
        observed.write_text(text)

    def prepare(self, toolchain, out, mode, size):
        source = out/'files'
        shutil.rmtree(source, ignore_errors=True)
        (source/'C').mkdir(parents=True)
        (source/'SUB').mkdir()
        cache = out/'commands'
        cache.mkdir(exist_ok=True)
        for name, path in (
                ('HELLO', 'examples/commands/hello.act'),
                ('ASSIGN', 'examples/commands/assign.act'),
                ('GREP', 'examples/commands/grep.act'),
                ('WAIT', 'tests/programs/disk_wait.act')):
            if name not in self.commands:
                self.commands[name] = compile_command(toolchain, ROOT/path,
                    cache/name, mode == 'opt')
            shutil.copyfile(cache/name, source/'C'/name)
        (source/'INPUT.TXT').write_bytes(b'alpha\n')
        system = b''
        user = b''
        folder = source/'S'
        if self.scenario != 'legacy':
            if self.scenario == 'wrong-type':
                folder.write_text('S must be a directory.\n')
            else:
                folder.mkdir()
        if self.scenario == 'normal':
            system = b'ALIAS BOOT "ECHO system"\nBOOT\nHELLO\nCD SUB\n'
            user = b'BOOT user\nALIAS US "ECHO user"\n'
            self.output = b'system\nHello from disk!\nsystem user\n'
            self.directory = b'D1:SUB\n'
            self.startup_tasks = (4, 4)
            self.user_alias = True
        elif self.scenario == 'legacy':
            self.assigns = b'C: -> D1:C\n'
        elif self.scenario == 'user-only':
            user = b'ECHO user-only\n'
            self.output = b'user-only\n'
        elif self.scenario == 'system-only':
            system = b'ECHO system-only\n'
            self.output = b'system-only\n'
        elif self.scenario == 'error':
            system = b'ECHO started\nMISSING\nECHO forbidden\n'
            user = b'ECHO forbidden\n'
            self.output = b'started\n'+diagnostic_text(205, 'MISSING')
            self.startup_result = (10, 205)
        elif self.scenario == 'user-error':
            system = b'ECHO system\n'
            user = b'ECHO user\nMISSING\nECHO forbidden\n'
            self.output = b'system\nuser\n'+diagnostic_text(205, 'MISSING')
            self.startup_result = (10, 205)
        elif self.scenario in ('warn', 'warn-last'):
            system = b'GREP absent SYS:INPUT.TXT\n'
            if self.scenario == 'warn':
                system += b'ECHO continued\n'
                user = b'ECHO user\n'
                self.output = b'continued\nuser\n'
            else:
                self.startup_result = (5, 0)
            self.startup_tasks = (4, 4)
        elif self.scenario == 'wrong-type':
            self.assigns = b'C: -> D1:C\n'
            self.output = diagnostic_text(212, 'Shell')
            self.startup_result = (10, 212)
        elif self.scenario == 'remap':
            system = b'ASSIGN S: SYS:ALT\n'
            user = b'ECHO forbidden\n'
            (source/'ALT').mkdir()
            (source/'ALT/USER').write_text('ECHO remapped\n')
            self.assigns = b'C: -> D1:C\nS: -> D1:ALT\n'
            self.output = b'remapped\n'
            self.startup_tasks = (4, 4)
        elif self.scenario == 'break':
            system = b'WAIT\nECHO forbidden\n'
            user = b'ECHO forbidden\n'
            self.startup_result = (10, 304)
            self.startup_tasks = (4, 4)
        if system:
            (folder/'STARTUP').write_bytes(system)
        if user:
            (folder/'USER').write_bytes(user)
        self.files = make(out/'volume.atr', source,
                          binary_names={'C/'+name for name in self.commands},
                          sector_bytes=256, filesystem=self.filesystem, sectors=2000)
        workspace = out/'workspace'
        workspace.mkdir(exist_ok=True)
        (workspace/'README.TXT').write_text('Writable WORK: disk.\n')
        make(out/'work.atr', workspace, sector_bytes=256,
             filesystem=self.filesystem, sectors=2880)

    def mount_extra(self, bridge, out):
        bridge.config('diskemu', 'generic56k')
        bridge.config('accuratedisk', 'false')
        bridge.mount(7, str(out/'work.atr'))

    def before_prompt(self, bridge, program, wait, key):
        if self.scenario == 'break':
            processes = program['build']['memory']['process_storage']['BASE']
            wait(f'(db(${processes+4*128+77:x})=2)&(db(${processes+4*128+117:x})=2)')
            key('BREAK', 'down')
            wait(f'@frame>={bridge.eval_expr("@frame")+2}')
            key('BREAK', 'up')

    def startup_output(self, program):
        strings = program['build']['exec_build']['strings']
        return (strings['banner']+strings['slots']+strings['stackChecks']+
                'console.device: ready\n'+'sio.device: D1'+strings['sioReady']+
                strings['mountStart']+'SYS: -> D1: ready, read-only\n'+
                'WORK: -> D8: ready, read-write\n\n').encode()+self.output

    def exercise(self, c):
        if self.scenario == 'normal':
            filesystem = b'SDFS       ' if self.filesystem == 'sdfs' else b'MyDOS      '
            c.command('MOUNT', b'MOUNT FILESYSTEM ACCESS    STATE\n'+
                      b'D1:   '+filesystem+b'read-only mounted\n'+
                      b'WORK: '+filesystem+b'writable  mounted\n')
        c.command('ASSIGN', self.assigns)
        c.command('CD', self.directory)
        c.command('PATH', b'Current directory\nC:\n')
        if self.user_alias:
            c.command('US retained', b'user retained\n')
        c.command('ECHO recovered', b'recovered\n')
        c.check_screen('startup-'+self.scenario)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--filesystem', choices=('mydos', 'sdfs'), default='mydos')
    parser.add_argument('--scenario', choices=(*SCENARIOS, 'all'), default='normal')
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    toolchain = compiler(ROOT/'build/actionc')
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    commands = {}
    names = SCENARIOS if args.scenario == 'all' else (args.scenario,)
    records = []
    for index, name in enumerate(names):
        print('Startup scripts:', args.filesystem, name, flush=True)
        scenario = Startup(name, args.filesystem, commands)
        result = run(toolchain, output, 'opt', size=256, external=scenario,
                     reuse=args.reuse or index > 0, pin=pin,
                     bridge_build=ROOT/'build/shell-paced-bridge')
        result.update(tier='development', scenario=name, filesystem=args.filesystem,
                      commands=commands, startup_result=scenario.startup_result,
                      mounts=scenario.mounts, bank_zero_delta=dict(fixed=0, per_task=0),
                      configuration_overrides=dict(diskemu='generic56k', accuratedisk=False),
                      source_inputs={**result['source_inputs'], **{name:sha256(ROOT/name)
                          for name in ('examples/shell/shell-boot.inc',
                                       'examples/shell/shell-execute.inc',
                                       'tools/test_shell_startup_scripts.py')}})
        for artifact in ('volume.atr', 'writes.bin'):
            shutil.copyfile(output/artifact, output/(name+'-'+artifact))
        path = output/(name+'-results.json')
        path.write_text(json.dumps(result, indent=2)+'\n')
        records.append(dict(scenario=name, path=str(path), sha256=sha256(path)))
    (output/'results.json').write_text(json.dumps(dict(status='pass', tier='development',
        filesystem=args.filesystem, cases=records), indent=2)+'\n')
    print('Startup scripts passed:', args.filesystem, len(records))
