#!/usr/bin/env python3
"""Profile Files scans; use trace_directory_batch_ui.py for UI completion."""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import shutil
import zipfile

from bitmap_console_performance import native_markers
from browser_model import FIELDS as F, listing, select, wait_listing
from colour_desktop_model import FIELDS as D
from console_turn_profile import analyze_events, Timeline
from desktop_menu_check import Menus
from desktop_mouse import schedule
from g4bench_trace import calls, listing_returns, native_calls
from gem_applications import instances
from native_program import read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events
from test_demo import run
import window_response_trace as response

APPLICATION = 'refresh_path FileScanBegin FileScanNext FileScanEnd redraw layout sort_entries'.split()
RESIDENT = 'Lock UnLock Examine ExNext ExNextBatch IoErr AllocMem FreeMem'.split()


def setup(out,app_bank=None):
    p = read_build(out)
    d = response.setup(out)
    names = [r['name'].rsplit('_', 1)[0][2:] for r in p['image']['routines']
             if r['name'].rsplit('_',1)[0][2:] in (
                 'DOSCLIENT_CALL','DOSCLIENT_ENSURESLOT','DOSCALLS_LOCK',
                 'FSDIRECTORY_SELECT','FSDIRECTORY_BATCH','FSPACKET_REPLY','FSPACKET_IDENTITY')]
    extra = native_markers(p, [(n, n) for n in names])
    d['timeline']['spans'].update(extra)
    for name, mark in extra.items():
        d['points'][mark['entry']] = name
        d['points'].update({pc: name+'_return' for pc in mark['returns']})
    foreign = json.loads((out/'bitmap-console/c-image.json').read_text())
    d['entries']={foreign['symbols'][n]: n for n in RESIDENT if n in foreign['symbols']}
    # DOS wrappers return to the application; observing every JSL successor in
    # the shared renderer adds unrelated glyph/painting traffic to scan traces.
    d['returns']=[]
    checked=foreign['provenance']['checked_layout']
    d['browser_fields']={key.removeprefix('Browser '):value for key,value in checked.items()
                         if key.startswith('Browser ') and key!='Browser size'}
    d['scan_error']=checked.get('FileScan error',16) # Archived single-entry layout.
    d['batch']= 'ExNextBatch' in foreign['symbols']
    d['points'].update(d['entries'])
    app = json.loads((out/'bitmap-console/apps/desktop/app.json').read_text())
    d['app_entries'] = {app['image']['symbols'][n]: 'app.'+n for n in APPLICATION
                        if n in app['image']['symbols']}
    d['app_exits'] = listing_returns(app['image'], out/'bitmap-console/apps/desktop', exits=True)
    d['app_returns'] = listing_returns(app['image'], out/'bitmap-console/apps/desktop')
    d['link_base'] = app['abi']['link_bank'] << 16
    d['gateway_entries'] = {p['labels'][n]: n for n in
        ('dos_current', 'tasks_find_task', 'tasks_forbid', 'tasks_permit',
         'ports_put_msg', 'ports_get_msg', 'ports_reply_msg')}
    d['points'].update(d['gateway_entries'])
    points = set(response.pcs(d))
    d['app_bank']=app_bank
    for bank in ([app_bank] if app_bank else app['verified_banks']):
        delta = (bank << 16)-d['link_base']
        points.update(pc+delta for pc in set(d['app_entries']) | set(d['app_exits']) | set(d['app_returns']))
    return d, sorted(points)


class Enumeration:
    def __init__(self,capacity=8,bundle=None):
        self.capacity,self.bundle=capacity,bundle

    def prepare_work(self,target,item):
        if not self.bundle:return
        from make_data_disk import make
        source=target.parent/'comparison-work';source.mkdir(exist_ok=True)
        for name,path in [('LIST',self.bundle/'media/C/LIST'),
                          ('FILES.APP',self.bundle/'bitmap-console/apps/files/program.app'),
                          ('TEXT.APP',self.bundle/'bitmap-console/apps/text/program.app')]:
            (source/name).write_bytes(path.read_bytes())
        make(target,source,filesystem='sdfs',sector_bytes=256,sectors=2880,
             binary_names={'LIST','FILES.APP','TEXT.APP'})

    def exercise(self, s):
        b, out = s.b, s.p['output']
        definition=json.loads((out/'enumeration-definition.json').read_text())
        F.update(definition['browser_fields'])
        live = next(a for a in instances(b, s.p, out/'bitmap-console') if a['name']=='desktop')
        require(not definition.get('app_bank') or live['base']==definition['app_bank']<<16,
                'Desktop placement differs from requested passive markers')
        (out/'enumeration-app.json').write_text(json.dumps(live, indent=2)+'\n')
        desk = live['symbols']['GEMDesk']
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x, y):
            old = [s.number(at(n), 2) for n in ('cursorX', 'cursorY')]
            pos = schedule(b, s.p, old, (x, y)); s.saved['pointer'] = pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' % (at('cursorX'), pos[0], at('cursorY'), pos[1]))
            s.frames(3)
        def click(x, y):
            move(x, y); b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(80)
        menus = Menus(s, click, move)
        b.profile_start()
        menus.select('SYS:'); move(632, 232); s.frames(80)
        base = s.number(desk+D['active'], 4)
        require(base, 'Missing active folder')
        samples = []
        def text(field):
            return b.memdump(base+F[field], 128).split(b'\0')[0].decode('ascii')
        def sample(name, action, path):
            start = b.eval_expr('@clk') & 0xffffffff
            action(); wait_listing(s, base, limit=200)
            require(text('path')==path, 'Wrong measured directory: '+text('path'))
            require(not s.number(base+F['scan']+definition['scan_error'], 4), 'Directory scan failed')
            row = dict(name=name, path=path, start=start, end=b.eval_expr('@clk') & 0xffffffff,
                       names=listing(s, base), paints=s.number(base+F['paints'], 4))
            samples.append(row)
            (out/'enumeration-samples.json').write_text(json.dumps(samples, indent=2)+'\n')
            print(name, len(row['names']), 'entries', flush=True)
        for i in range(3):
            sample('root refresh '+str(i+1), lambda: menus.key('L', ctrl=True), 'SYS:')
        select(s, base, 'C', click, stable_snapshot=True)
        sample('C first visit', lambda: menus.key('RETURN'), 'SYS:C')
        for i in range(3):
            sample('C refresh '+str(i+1), lambda: menus.key('L', ctrl=True), 'SYS:C')
        # Navigate with the ordinary editable path dialog; typing is outside
        # the measured scan. RAM is a different backend, not a matched disk case.
        menus.key('P')
        require(s.number(base+F['dialog'], 2)==1, 'Path dialog did not open')
        for _ in text('editText'): menus.key('BACKSPACE')
        from test_colour_desktop import KEYS
        for char in 'RAM:':
            key, shift = KEYS[char]; menus.key(key, shift=shift)
        sample('RAM first visit', lambda: menus.key('RETURN'), 'RAM:')
        for i in range(3):
            sample('RAM refresh '+str(i+1), lambda: menus.key('L', ctrl=True), 'RAM:')
        s.save_screen(out/'boot-smoke.png')
        menus.select('Shell')
        b.profile_stop()
        for char in 'EXIT': s.press(char)
        b._cmd_ok('KEY RETURN down'); b.bp_clear_all()


def exclusive(timeline, spans, start, end):
    """Charge each CPU interval to its innermost observed routine once."""
    edges = defaultdict(list); edges[start]; edges[end]
    for i, span in enumerate(spans):
        left, right = max(start, span['start']), min(end, span['end'])
        if left < right:
            edges[left].append((i, True)); edges[right].append((i, False))
    active = set(); totals = defaultdict(float); previous = start
    for tick in sorted(edges):
        if tick > previous:
            inner = max(active, key=lambda i: (spans[i]['start'], -spans[i]['end']), default=None)
            name = spans[inner]['kind'] if inner is not None else 'unattributed'
            totals[name] += timeline.measure(previous, tick)['charged_cpu_ms']
        for i, opening in edges[tick]:
            if opening: active.add(i)
            else: active.remove(i)
        previous = tick
    require(abs(sum(totals.values())-timeline.measure(start, end)['charged_cpu_ms'])<1e-6,
            'Exclusive CPU accounting does not reconcile')
    return dict(sorted(totals.items(), key=lambda pair: -pair[1]))


def queue_probes(events, definition, timelines, app_dp, fs_dp, start, end):
    """Bound empty queue calls through the following caller branch.

    Every filesystem GetMsg here runs under Forbid. A claimed packet reaches
    Identity; an empty probe reaches Permit instead. The bounds include the
    branch, exclude surrounding Forbid/Permit, and are not isolated syscall
    timings. Current-to-Ensure likewise includes caller setup instructions.
    """
    wanted = {'ports_get_msg', 'tasks_permit', 'FSPACKET_IDENTITY',
              'dos_current', 'DOSCLIENT_ENSURESLOT'}
    marks = {int(pc): name for pc, name in definition['points'].items() if name in wanted}
    opened = current = None
    result = dict(calls=0, empty=0, nonempty=0, empty_get_through_branch_cpu_ms=0,
                  context_through_ensure_calls=0, context_through_ensure_cpu_ms=0)
    for tick, e in events:
        if not start<=tick<end: continue
        name, dp = marks.get(int(e[4], 16)), int(e[9], 16)
        if dp==fs_dp:
            if name=='ports_get_msg':
                require(opened is None, 'Overlapping filesystem queue probes')
                opened = tick
            elif name in ('tasks_permit', 'FSPACKET_IDENTITY') and opened is not None:
                result['calls'] += 1
                empty = name=='tasks_permit'
                result['empty' if empty else 'nonempty'] += 1
                if empty:
                    result['empty_get_through_branch_cpu_ms'] += timelines[fs_dp].measure(opened, tick)['charged_cpu_ms']
                opened = None
        if dp==app_dp:
            if name=='dos_current': current = tick
            elif name=='DOSCLIENT_ENSURESLOT' and current is not None:
                result['context_through_ensure_calls'] += 1
                result['context_through_ensure_cpu_ms'] += timelines[app_dp].measure(current, tick)['charged_cpu_ms']
                current = None
    return result


def analyze(out,partial=False):
    d = json.loads((out/'enumeration-definition.json').read_text())
    live = json.loads((out/'enumeration-app.json').read_text())
    events = read_events(out/'emulator.log', kinds={'cpu'})
    delta = live['base']-d['link_base']
    entries = {int(pc): n for pc, n in d['entries'].items()}
    entries.update({int(pc)+delta: n for pc, n in d['app_entries'].items()})
    exits = set(d['exits']) | {pc+delta for pc in d['app_exits']}
    returns=set(d['returns']) | {pc+delta for pc in d.get('app_returns',())}
    # The launch observer admits every legal relocation. Discard hits at other
    # placements before constructing CPU timelines; those PCs are not markers
    # in this execution and retaining them only inflates host memory use.
    relevant = {int(pc) for pc in d['points']} | set(entries) | exits | returns
    events = [(tick, e) for tick, e in events if int(e[4], 16) in relevant]
    if partial:
        # A live capture may end inside an IRQ. Analyze only a prefix ending
        # at a verified context restore, after every recorded completed sample.
        last=max(i for i,(_,e) in enumerate(events) if int(e[4],16)==d['timeline']['points']['selected'])
        events=events[:last+1]
    profile = analyze_events(events, {**d['timeline'], 'spans': {}}, include_segments=True)
    native = native_calls(events, d['timeline']['spans'])
    scan_pc = next(pc for pc, n in entries.items() if n=='app.FileScanBegin')
    app_dps = {int(e[9], 16) for _, e in events if int(e[4], 16)==scan_pc}
    require(len(app_dps)==1, 'Missing unique Files caller')
    app_dp = app_dps.pop()
    c, unfinished = calls(events, entries, returns, app_dp, exits)
    c = [dict(s, dp=app_dp) for s in c]
    fs_dps = {s['dp'] for s in native if s['kind']=='FSDIRECTORY_SELECT'}
    require(len(fs_dps)==1, 'Missing unique filesystem Task')
    fs_dp = fs_dps.pop()
    timelines = {dp: Timeline(profile['segments'], dp) for dp in d['timeline']['task_dps']}
    serial = read_events(out/'emulator.log', kinds={'command', 'rxstart', 'receive', 'read'})
    samples = json.loads((out/'enumeration-samples.json').read_text())
    rows = []
    for sample in samples:
        left = sample['start']+round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
        right = left+(sample['end']-sample['start'])%(1<<32)
        begins = [s for s in c if s['kind']=='app.FileScanBegin' and left<=s['start']<s['end']<=right]
        require(len(begins)==1, 'Expected one scan in '+sample['name'])
        start = begins[0]['start']
        end = max(s['end'] for s in c if s['kind']=='app.FileScanNext' and start<=s['start']<s['end']<=right)
        spans = [s for s in native+c if start<=s['start']<s['end']<=end]
        count = len(sample['names'])
        nexts = [s for s in spans if s['kind']==('ExNextBatch' if d.get('batch') else 'ExNext')]
        expected=count//d.get('batch_capacity',8)+1 if d.get('batch') else count+1
        returned=sum(s['return_a'] if d.get('batch') else s['return_a']!=0 for s in nexts)
        require(len(nexts)==expected and returned==count,
                'Enumeration results disagree with published listing')
        require(sum(s['kind']=='DOSCLIENT_CALL' and s['dp']==app_dp for s in spans)==expected+3,
                'Unexpected DOS traffic inside directory scan')
        for s in spans: s.update(timelines[s['dp']].measure(s['start'], s['end']))
        totals = {}
        for s in spans:
            key = str(s['dp'])+':'+s['kind']
            t = totals.setdefault(key, dict(calls=0, elapsed_ms=0, charged_cpu_ms=0))
            t['calls'] += 1
            for k in ('elapsed_ms', 'charged_cpu_ms'): t[k] += s[k]
        charges = {str(dp): t.measure(start, end) for dp, t in timelines.items()}
        irq = sum(max(0, min(b, end)-max(a, start)) for a,b,_,interrupt in profile['segments'] if interrupt)*1000/BASE_HZ
        require(abs(sum(t['charged_cpu_ms'] for t in charges.values())+irq-(end-start)*1000/BASE_HZ)<1e-6,
                'Task and interrupt accounting does not reconcile')
        gateways = {int(pc): n for pc,n in d['gateway_entries'].items()}
        row = dict(sample=sample, start=start, end=end, elapsed_ms=(end-start)*1000/BASE_HZ,
                   batch_calls=len(nexts) if d.get('batch') else 0,
                   dos_calls=expected+3,
                   complete_refresh=[dict(start=s['start'],end=s['end'],elapsed_ms=(s['end']-s['start'])*1000/BASE_HZ)
                       for s in c if s['kind']=='app.refresh_path' and left<=s['start']<s['end']<=right],
                   competing_calls=[dict(dp=s['dp'],elapsed_ms=(s['end']-s['start'])*1000/BASE_HZ)
                       for s in native if s['kind']=='DOSCLIENT_CALL' and s['dp']!=app_dp
                       and s['start']<end and s['end']>start],
                   task_charges=charges, global_interrupt_ms=irq, inclusive=totals,
                   exclusive={str(dp): exclusive(timelines[dp], [s for s in spans if s['dp']==dp], start, end)
                              for dp in (app_dp, fs_dp)},
                   gateway_entries=dict(Counter(str(int(e[9],16))+':'+gateways[int(e[4],16)]
                       for tick,e in events if start<=tick<end and int(e[4],16) in gateways)),
                   serial_events=dict(Counter(e[0] for tick,e in serial if start<=tick<end)),
                   physical_commands=sum(e[0]=='command' and e[2]=='1' for tick,e in serial if start<=tick<end),
                   queue_probe=queue_probes(events, d, timelines, app_dp, fs_dp, start, end), spans=spans)
        rows.append(row)
        print(sample['name'], round(row['elapsed_ms'],3), 'ms; FS',
              round(charges[str(fs_dp)]['charged_cpu_ms'],3), 'ms CPU;', row['serial_events'], flush=True)
    result = dict(tier='development', qualification=False, guest_changes=False,
                  archive_sha256=sha256(out/'exec816-demo.zip'), observer_sha256=sha256(Path(__file__)),
                  app_dp=app_dp, filesystem_dp=fs_dp, presenter_dp=profile['worker_dp'], samples=rows,
                  scope='ScanBegin through final ScanNext/UnLock. Inclusive routines overlap; CPU includes gateway/scheduling charges but excludes native interrupts and peer Tasks.')
    result['partial_capture']=partial
    (out/('enumeration-partial.json' if partial else 'enumeration-analysis.json')).write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--analyze', action='store_true')
    parser.add_argument('--partial',action='store_true',help='Analyze completed samples from a still-running capture')
    parser.add_argument('--capacity',type=int,choices=(8,16),default=8)
    parser.add_argument('--media',type=Path,help='Common comparison media mounted from boot')
    parser.add_argument('--app-bank',type=int,help='Previously observed desktop bank; verified before tracing')
    args = parser.parse_args(); out = args.output.resolve()
    if args.analyze: return analyze(out,args.partial)
    require(args.bundle is not None and not out.exists(), 'Supply a bundle and fresh output directory')
    shutil.copytree(args.bundle.resolve(), out, ignore=shutil.ignore_patterns('extracted', '*.log', '*.bgra', '*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as z: z.extractall(out/'extracted')
    d, points = setup(out,args.app_bank)
    d['batch_capacity']=args.capacity
    (out/'enumeration-definition.json').write_text(json.dumps(d, indent=2)+'\n')
    saved = {k: os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS')}
    os.environ.update(EXEC816_LATENCY_TRACE='1', EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in points))
    try:
        result = run(out, boot_smoke=True, distribution_root=out/'extracted/exec816-demo',
                     integration=Enumeration(args.capacity,bundle=out),
                     profile_commands=False,media_path=args.media.resolve() if args.media else None,
                     measurement_commands=[] if args.media else None,
                     measurement_media_sha256=sha256(args.media) if args.media else None)
        (out/'enumeration-runtime.json').write_text(json.dumps(result, indent=2)+'\n')
    finally:
        for k,v in saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
    return analyze(out)


if __name__=='__main__': main()
