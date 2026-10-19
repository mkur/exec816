#!/usr/bin/env python3
"""Physical session-switch observations on an extracted OF816 package."""
import argparse
import hashlib
import json
import math
import os
import shutil
import statistics
import tempfile
import zipfile
from pathlib import Path

from bitmap_console_performance import native_markers
from measure_read_8k import observe
from measure_spartados_listing import spans, in_clock_window
from native_program import read_build, require, sha256
from shell_inspect import address, process_slot
from shell_session_walkthrough import Sessions
from sio_transaction_trace import BASE_HZ, read_events
from stack_budget import stack_usage
import test_demo


RUNNER_SHA256 = sha256(Path(__file__))


class Switches(Sessions):
    interrupt_marker = 'native_nmi'

    def __init__(self, out, bundle, samples):
        super().__init__(out, bundle)
        self.samples = samples
        self.rows, self.inventories = [], []

    def prepare_work(self, target, item):
        # An ordinary script sustains output throughout the measured interval.
        # Interleaved NIL reports leave observable scanout fences while the
        # producer continues executing commands; there is no guest pause hook.
        from sdfs_reference import extract, make
        with tempfile.TemporaryDirectory(prefix='exec816-switch-') as temp:
            root = Path(temp)
            extract(target, root)
            workload = b''.join((f'ECHO hidden-{i:05d}\n'.encode()+
                                b'ECHO working >NIL:\n'*8) for i in range(2000))
            (root/'OUTPUT').write_bytes(workload)
            make(target, root, item['sectors'], item['sector_bytes'])
        self.workload = dict(bytes=len(workload), sha256=hashlib.sha256(workload).hexdigest(),
                             media_sha256=sha256(target), visible_reports=2000,
                             nil_reports_per_visible=8)

    def screen(self, label):
        # test_demo independently composes the whole selected desktop, including
        # other applications, tabs, clipping and the mouse pointer.
        if self.s.manifest.get('desktop'):
            from generate_desktop import layout
            from generate_layers import layout as layers_layout
            s,c=self.s,self.c
            service=s.number(address(s.p['image'],'service','DESKSTATE'),3)
            damage=service+layout()['Service']['fields']['scene']+layers_layout()['Scene']['fields']['visibleDamage']
            view=s.saved['topView']
            # Observe the final scene and focused caret before the expensive
            # independent raster readback. This is a read-only checkpoint;
            # ordinary guest output and painting continue until it is met.
            s.rendezvous(f'(dw(${damage:x})=0)&'
                f'(db(${view+c["PRESENTATION_VISIBLE"]:x})=1)&'
                f'(db(${view+c["PRESENTATION_FOCUSED"]:x})=1)&'
                f'(db(${view+c["PRESENTATION_CURSORON"]:x})=1)')
            return s.cells(label)
        return super().screen(label)

    def settled_draft(self, text, cursor):
        s=self.s
        cooked=s.number(s.number(s.saved['shell'],3)+16,3)
        s.rendezvous(f'(dw(${cooked+2:x})={len(text)})&(dw(${cooked+402:x})={cursor})')
        s.ready()
        draft=self.draft()
        require(draft==(text.encode(),cursor),'Queued editing changed the intended draft')
        return draft

    def viewport(self):
        s=self.s
        cooked=s.number(s.number(s.saved['shell'],3)+16,3)
        return s.number(cooked+404,2),s.number(cooked+14,1)

    def inventory(self, label):
        s, c = self.s, self.c
        views = []
        for i in range(4):
            e = self.windows+c['WINDOWS_ITEMS']+i*c['WINDOW_SIZE']
            if s.number(e+c['WINDOW_STATE'], 1):
                instance = s.number(e+c['WINDOW_INSTANCE'], 3)
                views.append(dict(unit=s.number(e+c['WINDOW_UNIT']),
                    generation=s.number(instance+c['INSTANCE_GENERATION']),
                    instance=instance, view=s.number(e+c['WINDOW_VIEW'], 3)))
        stacks=stack_usage(s.b, s.p['build']['memory'])
        lifetimes=[]
        for index in range(2):
            control=s.number(address(s.p['image'],'control',session=index),3)
            if control and s.number(address(s.p['image'],'shell',session=index),3):
                identity=s.number(control)
                slot=process_slot(s.b,s.p,identity)
                lifetimes.append(dict(identity=identity,slot=slot,stack=stacks[str(slot)]))
                require(stacks[str(slot)]['remaining_above_floor']>=128,'Shell stack headroom below gate')
        require(stacks['0']['remaining_above_floor']>=128,'Controller stack headroom below gate')
        # The CPU is stopped at a recorded interrupt checkpoint. Read complete
        # reserved region headers without invoking or modifying the allocator.
        heap=s.p['build']['memory']['heap_storage'];regions=[]
        for index in range(heap['CAPACITY']):
            raw=s.far(heap['HEADERS']+32*index,28)
            low=int.from_bytes(raw[17:20],'little');high=int.from_bytes(raw[20:24],'little')
            if low and high:
                free=int.from_bytes(raw[24:28],'little')
                regions.append(dict(lower=low,upper=high,free=free,allocated=high-low-free))
        self.inventories.append(dict(label=label, clock=s.b.eval_expr('@clk'),
            ledger=s.ledger(), consoles=views, stacks=stacks,lifetimes=lifetimes,heap=regions))

    def switch(self, target, kind):
        s = self.s
        source = self.identity
        start = s.b.eval_expr('@clk')
        for key in ('CTRL', 'SHIFT', 'SPACE'):
            s.b._cmd_ok(f'KEY {key} down')
        self.wait_selected(target)
        commit = s.b.eval_expr('@clk')
        for key in ('SPACE', 'SHIFT', 'CTRL'):
            s.b._cmd_ok(f'KEY {key} up')
        self.bind(target)
        self.screen(f'{kind}-{source}-{target}-{len(self.rows)}')
        visible = s.b.eval_expr('@clk')
        # The next chord must have a fresh press after the release is sampled.
        s.frames(3)
        row = dict(kind=kind, source=source, target=target, input_clock=start,
                   commit_clock=commit, visible_clock=visible,
                   focus_ms=((commit-start)&0xffffffff)/BASE_HZ*1000,
                   pixels_ms=((visible-start)&0xffffffff)/BASE_HZ*1000)
        self.rows.append(row)
        print('switch', kind, source, target, row['focus_ms'], row['pixels_ms'], flush=True)

    def exercise(self, s):
        self.prepare(s)
        self.inventory('one-shell')
        if s.manifest.get('desktop'):
            from desktop_menu_check import Menus
            from desktop_mouse import schedule
            from generate_desktop import layout
            from generate_layers import layout as layers_layout,ABI as layers_abi
            def move(x, y):
                pos = schedule(s.b, s.p, s.saved['pointer'], (x, y))
                s.saved['pointer'] = pos
                s.frames(20)
            def click(x, y):
                move(x, y)
                s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
                s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(40)
            self.menus = Menus(s, click, move)
            self.menus.select('Shell')
            types=layout();service=self.menus.service
            window=service+types['Service']['fields']['windows']
            layers=layers_layout();scene=service+types['Service']['fields']['scene']
            owner=s.number(window+types['Window']['fields']['layer'])
            layer=next(scene+layers['Scene']['fields']['items']+i*layers['Layer']['size']
                for i in range(layers_abi['constants']['MAX_LAYERS'])
                if s.number(scene+layers['Scene']['fields']['items']+i*layers['Layer']['size'])==owner)
            bounds=layer+layers['Layer']['fields']['bounds']
            left,top=s.number(bounds,2),s.number(bounds+2,2)
            self.tab_click=lambda x:click(left+8+x,top+19)
            self.tab_click(496)
        else:
            s.begin('NEWSHELL')
        self.wait_selected(2);self.bind(2);s.ready()
        self.screen('second-ready')
        self.inventory('two-shells')
        for char in 'NEW':s.press(char)
        s.press('\t');s.ready()
        require(self.draft()[0]==b'NEWSHELL ','Packaged second-shell completion failed')
        s.press('\x15')
        long_line='ECHO '+('viewport-'*10)
        for char in long_line:s.press(char)
        for _ in range(7):s.press('\x02')
        second = self.settled_draft(long_line,len(long_line)-7)
        second_view=self.viewport()
        require(second_view[0]>0,'Long line did not exercise a horizontal viewport')
        s.b.profile_start('basicblock')
        self.switch(1, 'cold')
        for char in 'ECHO first draft':s.press(char)
        for _ in range(4):s.press('\x02')
        first = self.settled_draft('ECHO first draft',len('ECHO first draft')-4)
        first_view=self.viewport()
        for _ in range(self.samples):
            self.switch(2, 'idle');require(self.draft()==second, 'Long draft/caret changed')
            require(self.viewport()==second_view,'Hidden horizontal viewport changed')
            self.switch(1, 'idle');require(self.draft()==first, 'Midline draft/caret changed')
            require(self.viewport()==first_view,'Hidden short viewport changed')
        s.press('\x15')
        self.command('ECHO first-progress', b'first-progress')
        self.switch(2, 'setup-output');s.press('\x15')
        route = s.begin('EXECUTE WORK:OUTPUT')
        script = address(s.p['image'], 'script', session=1)
        s.rendezvous(f'(dw(${script:x})!=0)|(db(${script+2:x})!=0)')
        self.inventory('output-start')
        for _ in range(self.samples):
            self.switch(1, 'output')
            # Local edits prove that the idle peer accepts input while output
            # continues on the hidden model. They are outside timing windows.
            s.press('x');s.press('\x15')
            self.settled_draft('',0)
            self.switch(2, 'output')
            require(s.number(script, 3)!=0, 'Producer ended before the last sample')
        self.inventory('output-end')
        before, after = self.inventories[-2:]
        first_generation = next(v['generation'] for v in before['consoles'] if v['unit']==self.unit)
        last_generation = next(v['generation'] for v in after['consoles'] if v['unit']==self.unit)
        require(last_generation>first_generation, 'Output producer did not progress')
        # Script commands replace their foreground generation. A physical
        # BREAK captured just before that replacement may correctly expire.
        # Teardown retries the physical key, recording that distinction from
        # the separately measured durable CLOSE and stable-child disk cancel.
        self.output_break_attempts = 0
        for attempt in range(12):
            if not s.number(script,3):
                break
            s.press('\x03')
            self.output_break_attempts += 1
            s.frames(10)
        require(not s.number(script,3),'Output script ignored bounded BREAK attempts')
        self.bind(2);s.ready();s.result(304)
        self.command('ECHO second-progress', b'second-progress')
        self.inventory('output-retired')
        route = s.begin('CAT SYS:LONG.TXT >NIL:')
        self.wait_disk()
        self.switch(1, 'disk');self.command('ECHO disk-peer', b'disk-peer')
        self.switch(2, 'disk')
        s.press('\x03');s.ready(route);s.result(304)
        self.inventory('disk-retired')
        require(self.inventories[1]['ledger']==self.inventories[-1]['ledger'],
                'Output/disk retirement retained Task, Process or DOS ownership')
        if s.manifest.get('desktop'):
            require(s.ledger()['live']==7,'Packaged desktop two-shell Task census differs')
            before=s.ledger()
            self.command('CAT SYS:STORY.TXT | WC',error=103)
            require(s.ledger()==before,'Rejected desktop pipeline retained resources')
            self.tab_click(472)
        else:
            s.begin('EXIT')
        self.wait_selected(1);self.bind(1);s.ready()
        s.rendezvous(f'db(${self.live:x})=1')
        if s.manifest.get('desktop'):
            require(s.ledger()['live']==6,'Desktop close did not recover a Task slot')
            self.command('CAT SYS:STORY.TXT | WC')
            require(s.ledger()['live']==6,'Desktop pipeline did not retire its children')
        self.command('ECHO survivor', b'survivor')
        self.inventory('one-survivor')
        self.report = dict(rows=self.rows, inventories=self.inventories, workload=self.workload,output_break_attempts=self.output_break_attempts,
            drafts=[dict(session=1,text=first[0].decode(),cursor=first[1],viewport=first_view),
                    dict(session=2,text=second[0].decode(),cursor=second[1],viewport=second_view)])
        s.b.profile_stop()
        s.save_screen(self.bundle/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


def run(bundle, out, samples):
    out.mkdir(parents=True, exist_ok=True)
    copied = out/'bundle'
    require(not copied.exists(), 'Choose a fresh measurement output')
    shutil.copytree(bundle, copied, symlinks=True,
        ignore=shutil.ignore_patterns('emulator.log', 'distribution', 'pixels-*'))
    with zipfile.ZipFile(copied/'exec816-demo.zip') as archive:
        archive.extractall(out/'distribution')
    distribution = out/'distribution/exec816-demo'
    for line in (distribution/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(sha256(distribution/name)==digest, 'Extracted checksum differs: '+name)
    p = read_build(copied)
    routines = native_markers(p, [('DESKCONSOLE_BIND', 'bind'),
        ('DESKPAINT_FRAMESTEP', 'frame'), ('CONSOLEDISPLAY_PRESENT', 'present'),
        ('CONSOLEBITMAP_COPYSTART', 'copy')])
    marks = {}
    for name, routine in routines.items():
        marks[name+'_entry'] = routine['entry']
        for i, pc in enumerate(routine['returns']):marks[name+'_return_'+str(i)] = pc
    observe(marks)
    # Only selected PC spans are needed; POKEY byte/timer traces add no
    # evidence to this observer's physical input and retained-I/O checks.
    os.environ.pop('EXEC816_LATENCY_TRACE',None)
    exercise = Switches(out, copied, samples)
    record = test_demo.run(copied, boot_smoke=True, measurement_commands=[],
        profile_commands=False, distribution_root=distribution, integration=exercise)
    slots={0}|{life['slot'] for row in exercise.inventories for life in row['lifetimes']}
    for slot in slots:
        require(record['runtime']['stack_observations'][slot]['untouched_above_floor']>=128,
                'Final controller/shell stack headroom below gate')
    (out/'run.json').write_text(json.dumps(record, indent=2)+'\n')
    work = spans(read_events(copied/'emulator.log'), routines)
    for row in exercise.rows:
        row['presenter_work'] = {name:dict(calls=len(calls), elapsed_ms=sum(x['ms'] for x in calls))
            for name in routines
            if (calls:=[x for x in work if x['kind']==name and
                in_clock_window(x, row['input_clock'], row['visible_clock'])])}
    summaries = []
    for kind in ('idle', 'output'):
        for target in (1, 2):
            rows = [r for r in exercise.rows if r['kind']==kind and r['target']==target]
            require(len(rows)==samples, 'Incomplete switch cohort')
            summary = dict(kind=kind, target=target, count=len(rows))
            for name in ('focus_ms', 'pixels_ms'):
                values = sorted(r[name] for r in rows)
                summary[name] = dict(median=statistics.median(values), p95=values[math.ceil(.95*len(values))-1])
            summaries.append(summary)
    return dict(status='pass', tier='development', **exercise.report, summaries=summaries,
        runtime=record['runtime'], machine=record['machine'], autoboot_frames=record['autoboot_frames'],
        package_sha256=sha256(bundle/'exec816-demo.zip'), runner_sha256=RUNNER_SHA256,
        trace_sha256=sha256(copied/'emulator.log'),
        observation='Physical chord to first bank-zero interrupt checkpoint after controller selection commit; '
        'then independently correct selected model/pixels/caret. PAL frame sampling and two scanout frames '
        'are included; elapsed times include preemption and observer checkpoints, not pure CPU time. '
        'Work counts cover complete marked routines within the interval, not partial calls or all DMA work.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=20)
    args = parser.parse_args()
    result = run(args.bundle.resolve(), args.output.resolve(), args.samples)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['summaries'], indent=2), flush=True)
