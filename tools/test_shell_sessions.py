#!/usr/bin/env python3
"""Resident shell controller lifetime, admission and session integration gates."""
import argparse
import json
from pathlib import Path

from library_paths import read_source
from native_program import ROOT, build, compiler, read_build, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def controller(out, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    source = out/'shell_controller.act'
    session = read_source(ROOT/'examples/shell/shell-session.inc')
    session = session.replace('BYTE FUNC ShellScope(ShellContext POINTER context)\n',
        'BYTE FUNC ShellScope(ShellContext POINTER context)\n  ScopeBoundary(context,1)\n')
    session = session.replace('  IF DOS.BeginForeground(context.shell.console)<>0 THEN\n',
        '  IF DOS.BeginForeground(context.shell.console)<>0 THEN\n    ScopeBoundary(context,2)\n')
    observed = out/'session-observed.inc'
    observed.write_text(session)
    source.write_text(read_source(ROOT/'tests/programs/shell_controller.act',
        includes={'shell-session.inc': observed}))
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 8192
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    program = read_build(out) if reuse else build(
        compiler(ROOT/'build/actionc', release=True), source, out,
        optimize=True, tasks=True, task_capacity=8, console=True,
        dos_mounts=[], memory_profile=memory)
    with emulator(ROOT/'build/shell-paced-bridge',
                  ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        for key, value in PIN['configuration'].items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(bridge, program, timeout=120, frame_limit=12000)
        except Exception:
            print('Controller checks', data(bridge, program['image'], 'checks', True),
                  data(bridge, program['image'], 'closeMode'), flush=True)
            raise
        require(data(bridge, program['image'], 'finished') == [1], 'Unfinished controller fixture')
        for slot in (0, 2):
            require(runtime['stack_observations'][slot]['untouched_above_floor'] >= 128,
                    'Controller/shell stack headroom below gate')
        ownership(bridge, program, out)
        checks = data(bridge, program['image'], 'checks', True)[0]
    return dict(status='pass', tier='development', group='controller', mode='opt',
                checks=checks, build=program['build'], runtime=runtime, machine=machine)


def closing_chord(out,reuse=False):
    from shell_inspect import address
    from os_boundary import run_to
    out.mkdir(parents=True,exist_ok=True)
    control=read_source(ROOT/'examples/shell/shell-controller.inc')
    control=control.replace('    WHILE context.shell.done=0 DO','    HoldClose(context)\n    WHILE context.shell.done=0 DO',1)
    observed=out/'controller-observed.inc';observed.write_text(control)
    source=out/'shell_closing_chord.act'
    source.write_text(read_source(ROOT/'tests/programs/shell_closing_chord.act',
        includes={'shell-controller.inc':observed}))
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    program=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),
        source,out,optimize=True,tasks=True,task_capacity=8,console=True,
        dos_mounts=[],memory_profile=memory)
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        phase=address(program['image'],'phase','SHELLCLOSINGCHORDTEST');selected=address(program['image'],'selectedSession')
        def reach(condition):
            b.bp_clear_all();marker=program['labels']['native_nmi']
            b.bp_set(marker,condition=condition);run_to(b,marker,3000,60,condition)
        def before(b):
            reach(f'db(${phase:x})=1')
            for key in ('CTRL','SHIFT','SPACE'):b._cmd_ok(f'KEY {key} down')
            reach(f'dw(${selected:x})=2')
            for key in ('SPACE','SHIFT','CTRL'):b._cmd_ok(f'KEY {key} up')
            reach(f'@frame>={b.eval_expr("@frame")+3}')
            b.poke(phase,2);b.bp_clear_all()
        runtime,_=execute(b,program,before_run=before,timeout=120,frame_limit=10000)
        require(data(b,program['image'],'finished')==[1],'Closing chord fixture incomplete')
        ownership(b,program,out)
        checks=data(b,program['image'],'checks',True)[0]
    return dict(status='pass',tier='development',group='closing-chord',mode='opt',
                checks=checks,build=program['build'],runtime=runtime,machine=machine)


def ownership_sessions(out, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json'
    memory.write_text(json.dumps(profile,indent=2)+'\n')
    program=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),
        ROOT/'tests/programs/shell_two_sessions.act',out,optimize=True,tasks=True,
        task_capacity=8,console=True,dos_mounts=[],memory_profile=memory)
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:
            runtime,_=execute(b,program,timeout=180,frame_limit=15000)
        except Exception:
            print('Two-session checks',data(b,program['image'],'checks',True),flush=True)
            raise
        require(data(b,program['image'],'finished')==[1],'Two-session fixture incomplete')
        for slot in (0,2,4):
            require(runtime['stack_observations'][slot]['untouched_above_floor']>=128,
                    'Two-session stack headroom below gate')
        ownership(b,program,out)
        checks=data(b,program['image'],'checks',True)[0]
    return dict(status='pass',tier='development',group='ownership',mode='opt',checks=checks,
                build=program['build'],runtime=runtime,machine=machine)


def command_close(out, bundle, reuse=False):
    # Force CLOSE after the shell's preflight check and during partial group
    # admission. Hooks rendezvous only; emitted loader/group/cleanup stay real.
    from library_paths import read_source
    from native_program import sha256
    from shell_inspect import address

    out.mkdir(parents=True, exist_ok=True)
    (out/'sessioncloseprobe.act').write_text('''MODULE SESSIONCLOSEPROBE
USE EXEC
PUBLIC BYTE phase
BYTE POINTER closing
PUBLIC PROC Bind(BYTE POINTER flag)
  closing=flag
RETURN
PUBLIC PROC Reach(BYTE value)
  phase=value
  WHILE closing^=0 DO EXEC.Yield() OD
RETURN
ENDMODULE
''')
    session=read_source(ROOT/'examples/shell/shell-session.inc').replace(
        'USE EXEC\n','USE EXEC\nUSE SESSIONCLOSEPROBE\n',1)
    marker='  LET identity=PROCESS.StartLoaded('
    require(session.count(marker)==1,'Missing foreground handoff checkpoint')
    session=session.replace(marker,'  SESSIONCLOSEPROBE.Reach(3)\n'+marker)
    (out/'session-observed.inc').write_text(session)
    pipeline=read_source(ROOT/'lib/dos/pipeline.act').replace(
        'USE DOS\n','USE DOS\nUSE SESSIONCLOSEPROBE\n',1)
    marker='      first=PROCESS.PrepareLoaded(firstImage,firstArgs,firstLength,\n          BYTE POINTER(scope))'
    require(pipeline.count(marker)==1,'Missing partial group admission checkpoint')
    pipeline=pipeline.replace(marker,marker+'\n      SESSIONCLOSEPROBE.Reach(4)')
    (out/'pipeline.act').write_text(pipeline)
    control=read_source(ROOT/'examples/shell/shell-controller.inc')
    control=control.replace('      ShellPrompt(context)','''      ShellPrompt(context)
      SESSIONCLOSEPROBE.Bind(@context.control.closeRequested)
      IF closeMode=3 THEN
        STR.strlcpy(ShellLine(context),c"HELLO",LINE_CAPACITY)
      ELSE
        STR.strlcpy(ShellLine(context),c"CAT SYS:STORY.TXT | WC",LINE_CAPACITY)
      FI
      ShellCommand(context)
      Check(context.control.closeRequested=1 AND context.shell.done=1)
      Check(context.shell.lastError=DOS.ERROR_BREAK)''',1)
    (out/'controller-observed.inc').write_text(control)
    source=out/'shell_controller.act'
    text=read_source(ROOT/'tests/programs/shell_controller.act', includes={
        'shell-session.inc':out/'session-observed.inc',
        'shell-controller.inc':out/'controller-observed.inc'})
    text=text.replace('BYTE closeMode,boundary,finished','BYTE closeMode,finished')
    text=text.replace('boundary','SESSIONCLOSEPROBE.phase')
    text=text.replace('IF closeMode=0 THEN','IF closeMode=0 OR closeMode>=3 THEN',1)
    # The producer's first wait remains on the explicit admission checkpoint.
    text=text.replace('IF closeMode=0 OR closeMode>=3 THEN','IF closeMode=0 THEN',1)
    text=text.replace('  IF closeMode=0 THEN\n    Check(',
                      '  IF closeMode=0 OR closeMode>=3 THEN\n    Check(')
    text=text.replace('FOR closeMode=0 TO 2 DO','FOR closeMode=3 TO 4 DO')
    text=text.replace('    Check(FSBOOT.Stop()<>0 AND EXEC.AvailMem(0)=baseline)','''    Check(DOS.AssignPath(BYTE POINTER(c"C"),NULL)<>0)
    Check(DOS.AssignPath(BYTE POINTER(c"S"),NULL)<>0)
    Check(DOS.ReleaseContext()<>0)
    Check(FSBOOT.Stop()<>0 AND EXEC.AvailMem(0)=baseline)''')
    text=text[:text.index('  Check(nextSession=3)')]+'  Check(nextSession=2)\n  finished=1\nRETURN\nENDMODULE\n'
    source.write_text(text)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    manifest=json.loads((bundle/'demo-manifest.json').read_text())
    program=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),
        source,out,optimize=True,tasks=True,task_capacity=8,console=True,
        dos_mounts=manifest['mounts'],system_mount='D1',memory_profile=memory)
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        b.config('diskemu','generic56k')
        b.mount(0,str(bundle/'system.atr'));b.mount(7,str(bundle/'work.atr'))
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:
            runtime,_=execute(b,program,timeout=180,frame_limit=15000)
        except Exception:
            print('Command close checks/mode',data(b,program['image'],'checks',True),
                  data(b,program['image'],'closeMode'),flush=True)
            raise
        require(data(b,program['image'],'finished')==[1],'Command close fixture incomplete')
        for slot in (0,4):
            require(runtime['stack_observations'][slot]['untouched_above_floor']>=128,
                    'Command close stack headroom below gate')
        ownership(b,program,out)
        checks=data(b,program['image'],'checks',True)[0]
    return dict(status='pass',tier='development',group='command-close',mode='opt',checks=checks,
                build=program['build'],runtime=runtime,machine=machine,
                media_sha256=sha256(bundle/'system.atr'))


def desktop(out, reuse=False):
    from build_bitmap_console import build_bitmap
    from test_mouse_observe import PIN as pin, BRIDGE, ROM
    from shell_inspect import address, process_slot
    from console_model import read_cells
    from os_boundary import run_to
    from test_shell_core import KEYS
    import adapter_state as adapter

    out.mkdir(parents=True, exist_ok=True)
    program = read_build(out/'program') if reuse else build_bitmap(
        ROOT/'examples/desktop.act', out, desktop=True, release_compiler=True, dos_mounts=[])
    observed = []
    with emulator(BRIDGE, ROM, out, pin=pin) as b:
        for key, value in pin['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, ROM, pin)
        def reach(condition):
            b.bp_clear_all()
            b.bp_set(program['labels']['native_nmi'], condition=condition)
            b.bp_set(program['labels']['done'], condition=adapter.STOPPED)
            run_to(b, program['labels']['native_nmi'], 12000, 90, condition)
            require(b.peek16(adapter.STATE) == 65535, 'Desktop shell stopped early')
        def frames(count=3):
            reach(f'@frame>={b.eval_expr("@frame")+count}')
        def ptr(at):
            return int.from_bytes(b.memdump(at, 3), 'little')
        def key(name, ctrl=False):
            if ctrl: b._cmd_ok('KEY CTRL down')
            b._cmd_ok(f'KEY {name} down');frames()
            b._cmd_ok(f'KEY {name} up')
            if ctrl: b._cmd_ok('KEY CTRL up')
            frames()
        def before(b):
            instance=program['build']['memory']['console_storage']['INSTANCE']
            reach(f'db(${instance+51:x})=2')
            observed.append(dict(shell_slot=process_slot(b,program)))
            shell=ptr(address(program['image'],'shell','SHELLAPP'))
            cooked=ptr(ptr(shell)+16)
            from generate_desktop import layout as desktop_layout
            symbol=lambda module,name: next(d['address'] for d in program['image']['data']
                if '_'+module+'_'+name+'_' in d['name'])
            service=ptr(symbol('DESKSTATE','SERVICE'))
            focus=service+desktop_layout()['Service']['fields']['focus']
            target=b.memdump(symbol('DESKBOOT','SHELLWINDOW'),4)
            for _ in range(3):
                if b.memdump(focus,4)==target: break
                key('TAB',ctrl=True)
            require(b.memdump(focus,4)==target, 'Shell focus did not settle')
            for char in 'ec': key(KEYS[char][0])
            key('TAB')
            # With no mounted C: discovery fails conservatively and keeps the draft.
            reach(f'dw(${cooked+2:x})=2')
            for char in 'ho desktop': key(KEYS[char][0])
            key('RETURN')
            reach(f'(dw(${cooked+2:x})=0)&(db(${instance+51:x})=2)')
            cells=read_cells(b.memdump,instance)
            require(b'desktop' in cells, 'Desktop shell command output missing')
            (out/'shell.cells.bin').write_bytes(cells)
            b.screenshot(str(out/'shell.png'))
            for char in 'exit': key(KEYS[char][0])
            b._cmd_ok('KEY RETURN down');b.bp_clear_all()
        runtime,_=execute(b,program,before_run=before,timeout=180,frame_limit=12000)
        b._cmd_ok('KEY ALL up')
        require(data(b,program['image'],'exitStatus',True)==[0,0], 'Desktop EXIT failed')
        for slot in (0, observed[0]['shell_slot']):
            require(runtime['stack_observations'][slot]['untouched_above_floor']>=128,
                    'Desktop controller/shell stack headroom below gate')
        ownership(b,program,program['output'])
    return dict(status='pass',tier='development',group='desktop',mode='opt',
                build=program['build'],runtime=runtime,machine=machine,observed=observed)


def startup_exit(out, bundle):
    import shutil
    from make_data_disk import make
    from native_program import sha256
    from shell_inspect import address

    out.mkdir(parents=True, exist_ok=True)
    source=out/'media'
    shutil.rmtree(source,ignore_errors=True)
    shutil.copytree(bundle/'media',source)
    (source/'S/STARTUP').write_text('ECHO before-exit\nEXIT\nECHO forbidden\n')
    (source/'S/USER').write_text('ECHO forbidden\n')
    manifest=json.loads((bundle/'demo-manifest.json').read_text())
    binaries={name for name,entry in manifest['files'].items() if 'lines' not in entry}
    make(out/'system.atr',source,binary_names=binaries,filesystem=manifest['filesystem'],
         sector_bytes=manifest['sector_bytes'],sectors=manifest['system_sectors'])
    program={**read_build(bundle),'output':out}
    saved={}
    with emulator(ROOT/'build/shell-paced-bridge',
                  ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        b.config('diskemu','generic56k')
        b.mount(0,str(out/'system.atr'));b.mount(7,str(bundle/'work.atr'))
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            saved['screen']=b.peek16(88)
            saved['cells']=b.memdump(saved['screen'],960)
        runtime,_=execute(b,program,before_run=before,timeout=180,frame_limit=12000)
        for name,size in [('exitStatus',4),('controllerLive',1),('selectedSession',4),('shell',3)]:
            require(b.memdump(address(program['image'],name),size)==bytes(size),
                    'Startup EXIT did not retire '+name)
        require(runtime['created']==4,'Startup EXIT launched a prime or command')
        require(b.memdump(saved['screen'],960)==saved['cells'],'Startup EXIT did not restore display')
        ownership(b,program,bundle)
    return dict(status='pass',tier='development',group='startup-exit',mode='opt',
        build=program['build'],runtime=runtime,machine=machine,
        xex_sha256=sha256(bundle/'program.xex'),media_sha256=sha256(out/'system.atr'))


def physical_text(out, bundle, probe=None):
    from shell_session_walkthrough import Sessions,DiskSwitch,Inherited
    from test_demo import run
    import zipfile

    out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        archive.extractall(bundle/'extracted')
    scenario={'disk-switch':DiskSwitch,'inherited':Inherited}.get(probe,Sessions)(out,bundle)
    record=run(bundle,boot_smoke=True,integration=scenario,
               distribution_root=bundle/'extracted/exec816-demo')
    if probe is None:
        from filesystem_audit import Audit
        from native_program import sha256
        media=bundle/record['work_media'][0]['name']
        audit=Audit(media.read_bytes())
        getattr(audit,json.loads((bundle/'demo-manifest.json').read_text())['filesystem'])()
        expected={'SHARED.TXT':b'shared\n',
                  'SESS.TXT':b'  SESSION STATE\n  1 ready\n* 2 ready\n',
                  'SCRIPT':b'NEWSHELL >WORK:BAD\n'}
        require(all(audit.files[name]==payload for name,payload in expected.items())
                and 'BAD' not in audit.files,'Persisted session files differ')
        record['shared_files']=dict(media_sha256=sha256(media),
                                   files={name:payload.hex() for name,payload in expected.items()})
    record.update(group=probe or ('physical-bitmap' if scenario.bitmap else 'physical-text'),commands=scenario.commands,
                  session_screens=scenario.screens,measured_peaks=scenario.peaks)
    return record


def packaged_pipeline(out, bundle):
    from test_demo import run

    class Pipeline:
        def exercise(self, s):
            baseline=s.ledger()
            previous=s.begin('CAT SYS:LONG.TXT | WC')
            scope=s.saved['scope']
            live=s.p['build']['task_storage']['LIVE']
            s.rendezvous(f'(db(${live:x})=8)&(db(${scope+54:x})=1)')
            self.peak=s.number(live,1)
            s.frames(30)
            s.press('\x03');s.ready(previous);s.result(304)
            require(s.ledger()==baseline,'Eight-slot pipeline cancellation leaked ownership')
            s.command('HELLO',b'Hello from disk!')
            s.save_screen(bundle/'boot-smoke.png')
            for char in 'EXIT':s.press(char)
            s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()

    probe=Pipeline()
    record=run(bundle,boot_smoke=True,integration=probe,
        distribution_root=bundle/'extracted/exec816-demo')
    record.update(group='packaged-pipeline',measured_peak=probe.peak,
                  scope='Extracted OF816: eight live Tasks with prime and an active two-command pipeline, physical BREAK, exact ownership recovery, HELLO and EXIT')
    out.mkdir(parents=True,exist_ok=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('inherited','closing-chord','disk-switch','allocation','physical-bitmap','physical-text','ownership','controller','desktop','startup-exit','command-close','packaged-pipeline'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    if args.group=='closing-chord':
        result=closing_chord(args.output.resolve(),args.reuse)
    elif args.group=='allocation':
        from shell_session_faults import run
        result=run(args.output.resolve(),args.reuse)
    elif args.group in ('inherited','disk-switch','physical-text','physical-bitmap'):
        if args.bundle is None: parser.error('physical-text requires --bundle')
        result=physical_text(args.output.resolve(),args.bundle.resolve(),
                             args.group if args.group in ('inherited','disk-switch') else None)
    elif args.group=='ownership':
        result=ownership_sessions(args.output.resolve(),args.reuse)
    elif args.group=='packaged-pipeline':
        if args.bundle is None: parser.error('packaged-pipeline requires --bundle')
        result=packaged_pipeline(args.output.resolve(),args.bundle.resolve())
    elif args.group=='command-close':
        if args.bundle is None: parser.error('command-close requires --bundle')
        result=command_close(args.output.resolve(),args.bundle.resolve(),args.reuse)
    elif args.group=='startup-exit':
        if args.bundle is None: parser.error('startup-exit requires --bundle')
        result=startup_exit(args.output.resolve(),args.bundle.resolve())
    else:
        result = globals()[args.group](args.output.resolve(), args.reuse)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Shell session checks passed', args.group, flush=True)
