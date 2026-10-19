#!/usr/bin/env python3
"""Emitted cooperative close and retained noncooperative session measurements."""
import argparse
import json
from pathlib import Path
from bitmap_console_performance import native_markers
from console_model import read_cells
from generate_console import constants
from generate_shell_sessions import layout as session_layout
from library_paths import read_source
from measure_read_8k import observe
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from shell_inspect import address, process_slot
from sio_transaction_trace import BASE_HZ, read_events
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_shell_core import KEYS

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out, bundle, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    control = read_source(ROOT/'examples/shell/shell-controller.inc')
    needle = '    WHILE context.shell.done=0 DO'
    require(control.count(needle)==1, 'Shell fixture entry changed')
    control = control.replace(needle, '    FixtureWork(context)\n'+needle)
    hooked = out/'controller-observed.inc';hooked.write_text(control)
    source = out/'shell_session_close_measure.act'
    source.write_text(read_source(ROOT/'tests/programs/shell_session_close_measure.act',
                                  includes={'shell-controller.inc':hooked}))
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 9216  # Fixture controls; production text remains 8192.
    memory = out/'fixture-memory.json';memory.write_text(json.dumps(profile, indent=2)+'\n')
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    p = read_build(out) if reuse else build(compiler(ROOT/'build/actionc', release=True), source, out,
        optimize=True, tasks=True, task_capacity=8, console=True, dos_mounts=manifest['mounts'],
        system_mount='D1', memory_profile=memory)
    routines = native_markers(p, [('SHELLCLOSEMEASURE_CLOSEREQUEST', 'request'),
        ('SHELLCLOSEMEASURE_SHELLSESSIONCLOSE', 'accept'), ('SHELLCLOSEMEASURE_CLOSERETIRED', 'retire')])
    require(set(routines)=={'request','accept','retire'}, 'Missing close markers')
    marks = {name:routine['entry'] for name,routine in routines.items()}
    observe(marks)
    cases = []
    c = constants()
    for variant, name in enumerate(('prompt','disk','pipeline','noncooperative')):
        print('Close case',name,flush=True)
        directory = out/name;directory.mkdir(exist_ok=True)
        observed = {}
        with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', directory, pin=PIN) as b:
            for key,value in PIN['configuration'].items():
                b.config(key, str(value).lower() if isinstance(value,bool) else value)
            b.config('diskemu','generic56k')
            b.mount(0, str(bundle/'system.atr'));b.mount(7, str(bundle/'work.atr'))
            machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
            number = lambda a,size=4:int.from_bytes(b.memdump(a,size),'little')
            at = lambda field:address(p['image'],field,'SHELLCLOSEMEASURE')
            def reach(condition):
                marker = p['labels']['native_nmi'];b.bp_clear_all()
                condition=f'(@xpc=${marker:x})&({condition})'
                b.bp_set(marker, condition=condition)
                run_to(b, marker, 18000, 240, condition)
            def frames(count=3):reach(f'@frame>={b.eval_expr("@frame")+count}')
            def press(ch):
                key,shift=KEYS[ch]
                if shift:b._cmd_ok('KEY SHIFT down')
                b._cmd_ok(f'KEY {key} down');frames(3)
                b._cmd_ok(f'KEY {key} up')
                if shift:b._cmd_ok('KEY SHIFT up')
                frames(3)
            def before(b):
                b.profile_start()
                reach(f'db(${at("phase"):x})=1')
                b.poke(at('variant'),variant)
                slots = [process_slot(b,p,i) for i in (1,2)]
                observed['shell_slots']=slots
                windows=p['build']['memory']['console_storage']['WINDOWS']
                first=windows+c['WINDOWS_ITEMS']
                instance=number(first+c['WINDOW_INSTANCE'],3)
                scope=number(first+c['WINDOW_SCOPE'],3)
                b.poke(at('go'),1)
                if variant==1:
                    field=first+c['WINDOW_SCOPE']
                    reach(f'(dw(${field:x})!={scope&65535})|(db(${field+2:x})!={scope>>16})')
                    child=number(field,3)
                    reach(f'(db(${child+21:x})=3)&(dw(dw(${child+27:x})+db(${child+29:x})*65536+22)=82)')
                elif variant==2:
                    live=p['build']['task_storage']['LIVE']
                    reach(f'(db(${scope+54:x})=1)&(db(${live:x})=8)')
                    children=[number(scope+offset,3) for offset in (48,51)]
                    reach('|'.join(f'((db(${child+21:x})=3)&'
                        f'(dw(dw(${child+27:x})+db(${child+29:x})*65536+22)=82))' for child in children))
                    require(number(live,1)==8,'Pipeline did not admit both children')
                elif variant==0:
                    reach(f'db(${instance+51:x})=2')
                observed['request_checkpoint_clock']=b.eval_expr('@clk')
                observed['live_tasks_at_request']=number(p['build']['task_storage']['LIVE'],1)
                b.poke(at('closeNow'),1)
                if variant==3:
                    close_flag=number(address(p['image'],'control',session=0),3)+session_layout()['ShellSessionControl']['fields']['closeRequested']
                    reach(f'db(${close_flag:x})=1')
                    retained=number(at('controllerLive'),1)
                    for key in ('CTRL','SHIFT','SPACE'):b._cmd_ok(f'KEY {key} down')
                    reach(f'dw(${at("selectedSession"):x})=2')
                    for key in ('SPACE','SHIFT','CTRL'):b._cmd_ok(f'KEY {key} up')
                    frames(3)
                    for ch in 'ECHO peer-progress\n':press(ch)
                    second=first+c['WINDOW_SIZE']
                    terminal=number(second+c['WINDOW_INSTANCE'],3)
                    reach(f'db(${terminal+51:x})=2')
                    require(b'peer-progress' in read_cells(b.memdump,terminal),'Peer stopped during retained close')
                    frames(50)
                    require(retained==2 and number(at('controllerLive'),1)==2,'Uncooperative shell was reclaimed')
                    require(process_slot(b,p,1)==slots[0],'Retained Process lifetime changed')
                    observed['retained_until_clock']=b.eval_expr('@clk')
                    observed['peer_progress']=True
                    b.poke(at('releaseFirst'),1)
                reach(f'db(${at("phase"):x})=3')
                observed['retired_checkpoint_clock']=b.eval_expr('@clk')
                require(number(at('controllerLive'),1)==1,'Close did not collect exactly one shell')
                b.poke(at('finish'),1);b.bp_clear_all()
            try:
                runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=25000)
                b.profile_stop()
            except Exception:
                print('close fixture',name,'phase',number(at('phase'),1),'checks',number(at('checks'),2),flush=True)
                raise
            require(data(b,p['image'],'finished')==[1], 'Close fixture incomplete')
            ownership(b,p,out)
            for slot in [0]+observed['shell_slots']:
                require(runtime['stack_observations'][slot]['untouched_above_floor']>=128,'Close stack headroom below gate')
            checks=data(b,p['image'],'checks',True)[0]
        events=read_events(directory/'emulator.log')
        stamps={name:[t for t,e in events if e[0]=='cpu' and int(e[4],16)==pc] for name,pc in marks.items()}
        require(len(stamps['request'])==1 and len(stamps['retire'])==1 and len(stamps['accept'])==2,'Incomplete close trace')
        start,accepted,retired=stamps['request'][0],stamps['accept'][0],stamps['retire'][0]
        cases.append(dict(name=name,checks=checks,**observed,request_to_accept_ms=(accepted-start)/BASE_HZ*1000,
            request_to_retire_ms=(retired-start)/BASE_HZ*1000,runtime=runtime,machine=machine,
            trace_sha256=sha256(directory/'emulator.log')))
        print(name,cases[-1]['request_to_accept_ms'],cases[-1]['request_to_retire_ms'],flush=True)
    return dict(status='pass',tier='development',build=p['build'],cases=cases,
        media_sha256=sha256(bundle/'system.atr'),runner_sha256=sha256(Path(__file__)),
        scope='Fixture entry and root orchestration only; real shell dispatcher, Process, I/O and retirement. '
        'Host flags trigger phases, never edit runtime ownership. Passive instruction clocks include preemption. '
        'Noncooperative elapsed time includes deliberate retention and physical peer input; it is not a close bound.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    result=run(args.output.resolve(),args.bundle.resolve(),args.reuse)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
