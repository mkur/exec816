"""Passive presenter phases and signal sites on the frozen MGVIEW fixture.

All PCs come from decoded emitted instructions. The guest is unchanged; the
observer records registers at linked calls, returns and selected branch paths.
"""
import re
from collections import Counter, defaultdict

from aes_latency_trace import routine
from native_program import ROOT, require
from console_turn_profile import Timeline, analyze_events
from g4bench_trace import calls
from presenter_control_trace import BOOKKEEPING
from sio_transaction_trace import BASE_HZ, read_events


NAMES = set(BOOKKEEPING) | set('''
AESGATE_RECLAIM AESGATE_TRYOWNER AESGATE_RELEASE AESGATE_ENTERTASK
AESGATE_WAKECALLERS AESSNAPSHOT_PUBLISH DESKINPUT_REPLAYKEYS
CONSOLEDISPLAY_POLL DESKHOST_MENUCONTINUATION DESKHOST_CONTROLS
DESKHOST_READY DESKHOST_AFTERPAINT DESKHOST_EVENTS AESHOST_SETTLE
DESKPAINT_PUMP AESHOST_RUNNABLE AESHOST_PUMP AESHOST_WAKE
AESCORE_RUNNABLE AESCORE_SETTLE AESMOUSE_REFRESH AESWINDOWSTATE_SYNC
AESLOCKS_PAINTBLOCKED AESLOCKS_MOUSEBLOCKED
DISPLAY_BLOCKED DISPLAY_LEAVE DISPLAY_NEXT DISPLAY_ENTER
DISPLAY_OWNERENTER DISPLAY_OWNERDROP
CONSOLEDRIVER_SYSTEMSTOPPING CONSOLEDRIVER_SYSTEMINPUT
CONSOLEDRIVER_SYSTEMRUNNABLE CONSOLEDRIVER_SYSTEMTURN
CONSOLEDRIVER_BACKENDTURN CONSOLECONTROL_PROCESS
'''.split())
DETAILED = set('''AESSYSTEM_RUN AESSYSTEM_COLLECT DISPLAY_BLOCKED
DISPLAY_LEAVE DISPLAY_NEXT AESGATE_RELEASE AESGATE_ENTERTASK
AESGATE_RECLAIM AESCORE_RUNNABLE'''.split())


def definition(program):
    decoder = {'__name__': 'presenter_decoder'}
    source = ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(source.read_text(), str(source), 'exec'), decoder)
    names = NAMES | DETAILED
    selected = [r for r in program['image']['routines']
                if any(r['name'].startswith('M_'+name+'_') for name in names)]
    labels = {r['address']: r['name'].rsplit('_', 1)[0][2:]
              for r in program['image']['routines']}
    targets = {program['labels'][n]: n for n in
               ('tasks_signal', 'tasks_set_signal', 'tasks_wait', 'exec_yield')}
    entries, returns, exits, pcs, sites, instructions = {}, set(), set(), set(), {}, {}
    for r in selected:
        name = labels[r['address']]
        base, raw = routine(program, name)
        segment = dict(address=base, executable=True, bytes=list(raw))
        listing = decoder['disassemble']({**program['image'], 'version': 3,
                                          'segments': [segment]})
        entries[base] = name
        for line in listing.splitlines():
            match = re.match(r'^([0-9A-F]{6})\s+((?:[0-9A-F]{2} )+)\s*(.*)$', line)
            if not match:
                continue
            pc = int(match[1], 16)
            code = bytes.fromhex(match[2])
            if name in DETAILED:
                pcs.add(pc)
                instructions[pc] = dict(routine=name, text=match[3], bytes=code.hex())
            if code[0] == 0x22:
                target = int.from_bytes(code[1:], 'little')
                require(raw[pc-base:pc-base+4] == code, 'Changed native JSL')
                returns.add(pc+4)
                sites[pc] = dict(caller=name, target=targets.get(target, labels.get(target, hex(target))),
                                 return_pc=pc+4)
            if code == b'\x6b':
                exits.add(pc)
    pcs.update(entries)
    pcs.update(returns)
    pcs.update(exits)
    # Also observe signal sites in other native modules. A site name identifies
    # its producer; only source-proven presenter targets are called its wakes.
    for r in program['image']['routines']:
        if r in selected or not r['name'].startswith('M_'):
            continue
        name = labels[r['address']]
        base, raw = routine(program, name)
        for target, label in targets.items():
            needle = b'\x22'+target.to_bytes(3, 'little')
            for match in re.finditer(re.escape(needle), raw):
                # Validate these rare matches by decoding that whole routine.
                listing = decoder['disassemble']({**program['image'], 'version': 3,
                    'segments': [dict(address=base, executable=True, bytes=list(raw))]})
                pc = base+match.start()
                require(any(line.startswith(f'{pc:06X} ') and ' JSL ' in line
                            for line in listing.splitlines()), 'Signal match is not an instruction')
                sites[pc] = dict(caller=name, target=label, return_pc=pc+4)
                pcs.update((pc, pc+4))
    require(all(any(n == name for n in entries.values()) for name in DETAILED),
            'Missing presenter branch routines')
    return dict(entries=entries, returns=sorted(returns), exits=sorted(exits),
                pcs=sorted(pcs), sites=sites, instructions=instructions)


PHASES = {
    'scene_admission': 'AESGATE_RECLAIM',
    'signals': 'AESSYSTEM_COLLECT',
    'input': 'DESKINPUT_REPLAYKEYS DESKINPUT_SERVICE DESKINPUT_ADVANCE DESKINPUT_PRESENT CONSOLEDRIVER_SYSTEMINPUT',
    'completion_poll': 'CONSOLEDISPLAY_POLL',
    'menu_continuation': 'DESKHOST_MENUCONTINUATION',
    'controls': 'DESKHOST_CONTROLS DESKHOST_AFTERPAINT',
    'painting': 'DESKPAINT_PUMP',
    'console': 'CONSOLEDRIVER_SYSTEMTURN',
    'events': 'DESKHOST_EVENTS',
    'settlement': 'AESHOST_SETTLE',
    'readiness': 'DESKHOST_READY AESHOST_SETTLED DESKHOST_RUNNABLE CONSOLEDRIVER_SYSTEMRUNNABLE DESKPAINT_READY AESLOCKS_NATIVEREADY',
    'cache': 'DESKHOST_CACHE',
    'scene_publication': 'AESGATE_OFFER',
    'stop_check': 'CONSOLEDRIVER_SYSTEMSTOPPING',
}


def phase_costs(spans, timeline, start, end):
    """Exclusive CPU by outermost selected phase, including clipped calls."""
    kinds = {name: group for group, names in PHASES.items() for name in names.split()}
    edges = defaultdict(list)
    for i, s in enumerate(spans):
        if s['kind'] in kinds and s['start'] < end and start < s['end']:
            edges[max(start, s['start'])].append((i, True))
            edges[min(end, s['end'])].append((i, False))
    edges[start]; edges[end]
    totals = Counter()
    active = set()
    previous = start
    for tick, changes in sorted(edges.items()):
        outer = min(active, key=lambda i: spans[i]['start']) if active else None
        group = kinds[spans[outer]['kind']] if outer is not None else 'loop_other'
        totals[group] += timeline.measure(previous, tick)['charged_cpu_ms']
        for i, entering in changes:
            if entering: active.add(i)
            else: active.remove(i)
        previous = tick
    measured = timeline.measure(start, end)
    require(abs(sum(totals.values())-measured['charged_cpu_ms']) < 1e-6,
            'Presenter phase accounting does not reconcile')
    return dict(measured=measured, exclusive_cpu_ms=dict(totals))


def signal_arguments(history):
    """Decode the checked Action! Signal packet's six PHA observations."""
    pushes = [e for _, instruction, e in history if instruction['bytes'] == '48'][-6:]
    if len(pushes) != 6:
        return None
    widths = [8 if int(e[11], 16) & 0x20 else 16 for e in pushes]
    if widths != [8, 16, 16, 8, 8, 16]:
        return None
    values = [int(e[5], 16) & ((1 << width)-1) for e, width in zip(pushes, widths)]
    return dict(task=values[5] | values[4] << 16, mask=values[2] | values[1] << 16)


def mouse_returns(foreign, directory, selected):
    """The first capture already selected every linked C call successor."""
    result = []
    for path in directory.glob('*console-bitmap.lst'):
        for section in path.read_text().split('.section ')[1:]:
            if not re.search(r'\\ 000000\s+ConsoleBitmapEntry:', section):
                continue
            for match in re.finditer(r'\\ ([0-9a-f]{6}) 22[.]{6}\s+jsl\s+long:GemDrawingMouse\s', section):
                pc = foreign['symbols']['ConsoleBitmapEntry']+int(match[1], 16)
                segment = next(s for s in foreign['segments']
                               if s['address'] <= pc < s['address']+len(s['bytes']))
                raw = bytes(segment['bytes'][pc-segment['address']:pc-segment['address']+4])
                require(raw == b'\x22'+foreign['symbols']['GemDrawingMouse'].to_bytes(3, 'little'),
                        'Changed console mouse call')
                require(pc+4 in selected, 'Console mouse return was not captured')
                result.append(pc+4)
    require(len(result) == 1, 'Missing unique console mouse call')
    return set(result)


def analyze(out, definition, base_audit, foreign, directory):
    """Attribute presenter work and exact signal sites within owned UPDATE."""
    events = read_events(out/'emulator.log', kinds={'cpu'})
    interrupts = {definition['timeline']['points'][n] for n in ('native_irq', 'native_nmi')}
    while events and int(events[-1][1][4], 16) in interrupts:
        events.pop()
    profile = analyze_events(events, definition['timeline'], include_segments=True)
    d = definition['presenter']
    worker = profile['worker_dp']
    timeline = Timeline(profile['segments'], worker)
    worker_events = [(t, e) for t, e in events if int(e[9], 16) == worker]
    spans, unfinished = calls(worker_events, d['entries'], set(d['returns']), worker, set(d['exits']))
    cspans, _ = calls(worker_events, definition['entries'], set(definition['returns']),
                      worker, set(definition['exits']))
    mouse_pcs = mouse_returns(foreign, directory, definition['returns'])
    mouse_calls = [dict(tick=t, status=int(e[5], 16)) for t, e in worker_events
                   if int(e[4], 16) in mouse_pcs]
    getter_sites = {site['return_pc']: site['target'] for site in d['sites'].values()
                    if site['caller'] == 'DESKINPUT_PRESENT' and site['target'] in
                    ('CONSOLEBITMAP_CHANGED', 'AESCURSOR_PENDING', 'CONSOLEBITMAP_MOUSE')}
    require(set(getter_sites.values()) == {'CONSOLEBITMAP_CHANGED', 'AESCURSOR_PENDING', 'CONSOLEBITMAP_MOUSE'},
            'Missing cursor-presentation decision boundaries')
    getters = [dict(tick=t, kind=getter_sites[int(e[4], 16)], value=int(e[5], 16) & 255)
               for t, e in worker_events if int(e[4], 16) in getter_sites]
    by_tick = {t: e for t, e in worker_events}
    for s in spans:
        s['return_bits'] = int(by_tick[s['end']][5], 16) | int(by_tick[s['end']][6], 16) << 16

    signal_sites = {pc: site for pc, site in d['sites'].items() if site['target'] == 'tasks_signal'}
    wait_sites = {pc: site for pc, site in d['sites'].items() if site['target'] in ('tasks_wait', 'exec_yield')}
    pending, waits, signals, history = {}, [], [], defaultdict(list)
    for tick, e in events:
        pc, dp, stack = (int(e[i], 16) for i in (4, 9, 8))
        if pc in d['instructions']:
            history[dp].append((tick, d['instructions'][pc], e))
            history[dp] = history[dp][-80:]
        key = dp, stack, pc
        if key in pending:
            opened = pending.pop(key)
            waits.append(dict(opened, end=tick,
                return_bits=int(e[5], 16) | int(e[6], 16) << 16))
        if pc in wait_sites and dp == worker:
            site = wait_sites[pc]
            pending[dp, stack, site['return_pc']] = dict(start=tick, caller=site['caller'],
                                                        operation=site['target'])
        if pc in signal_sites:
            site = signal_sites[pc]
            nearby = [row for row in history[dp] if row[1]['routine'] == site['caller']]
            signals.append(dict(tick=tick, dp=dp, pc=pc, caller=site['caller'],
                                arguments=signal_arguments(nearby)))

    turn_pc = next(pc for pc, site in d['sites'].items()
                   if site['caller'] == 'AESSYSTEM_RUN' and site['target'] == 'AESGATE_RECLAIM')
    turn_ticks = [t for t, e in worker_events if int(e[4], 16) == turn_pc]
    quiet_pc = min(pc for pc, site in d['sites'].items()
                   if site['caller'] == 'AESSYSTEM_RUN' and site['target'] == 'DESKHOST_CACHE')
    quiet_ticks = [t for t, e in worker_events if int(e[4], 16) == quiet_pc]
    result = []
    for sample in base_audit['samples']:
        shift = next(s for s in sample['spans'] if s['kind'] == 'set_shift')
        begin = next(s for s in sample['spans'] if s['kind'] == 'ExecAESBeginUpdate')
        release = next(s for s in sample['spans'] if s['kind'] == 'wind_update')
        windows = dict(whole_shift=(shift['start'], shift['end']),
                       owned_core=(begin['end'], release['start']))
        sample_result = dict(action=sample['action'], windows={})
        for name, (start, end) in windows.items():
            selected = [s for s in spans if s['start'] < end and start < s['end']]
            routines = {}
            for s in selected:
                row = routines.setdefault(s['kind'], dict(calls=0, starts=0, completions=0,
                                                         cpu_ms=0, returns=Counter()))
                row['calls'] += 1
                row['starts'] += start <= s['start'] < end
                row['completions'] += start <= s['end'] < end
                row['cpu_ms'] += timeline.measure(max(start, s['start']), min(end, s['end']))['charged_cpu_ms']
                if start <= s['end'] < end:
                    row['returns'][str(s['return_a'] & 255)] += 1
            active_waits = [dict(w, **timeline.measure(max(start, w['start']), min(end, w['end'])))
                            for w in waits if w['start'] < end and start < w['end']]
            posted = [s for s in signals if start <= s['tick'] < end]
            presenter_tasks = {s['arguments']['task'] for s in signals
                               if s['caller'] == 'AESGATE_RELEASE' and s['arguments']}
            require(len(presenter_tasks) == 1, 'No unique presenter signal target')
            presenter_task = next(iter(presenter_tasks))
            presenter_posts = [s for s in posted if s['arguments']
                               and s['arguments']['task'] == presenter_task]
            wake_counts = Counter((s['caller'], s['arguments']['mask']) for s in presenter_posts)
            wait_counts = Counter((w['caller'], w['return_bits']) for w in active_waits
                                  if w['operation'] == 'tasks_wait' and start <= w['end'] < end)
            turns = []
            for a, b in zip(turn_ticks, turn_ticks[1:]):
                if a >= end or b <= start:
                    continue
                completed_waits = [w for w in waits if a <= w['start'] < b]
                collected = [s['return_bits'] for s in spans if s['kind'] == 'AESSYSTEM_COLLECT'
                             and a <= s['start'] < b]
                turns.append(dict(start=a, end=b, clipped=a < start or b > end,
                    quiet=any(a <= t < b for t in quiet_ticks), collected=collected,
                    waits=completed_waits, **phase_costs(spans, timeline, max(a, start), min(b, end))))
            sample_result['windows'][name] = dict(start=start, end=end,
                **phase_costs(spans, timeline, start, end),
                routine_costs=routines, signals=posted, waits=active_waits, turns=turns,
                presenter_task=presenter_task,
                presenter_signal_counts=[dict(caller=k[0], mask=k[1], count=v)
                                         for k, v in wake_counts.items()],
                wait_return_counts=[dict(caller=k[0], bits=k[1], count=v)
                                    for k, v in wait_counts.items()],
                mouse_returns=[m for m in mouse_calls if start <= m['tick'] < end],
                cursor_decisions={kind: dict(Counter(str(g['value']) for g in getters
                    if g['kind'] == kind and start <= g['tick'] < end))
                    for kind in getter_sites.values()},
                c_routines={kind: dict(calls=sum(s['kind'] == kind and s['start'] < end and start < s['end'] for s in cspans),
                    cpu_ms=sum(timeline.measure(max(start, s['start']), min(end, s['end']))['charged_cpu_ms']
                               for s in cspans if s['kind'] == kind and s['start'] < end and start < s['end']))
                    for kind in ('VbxeOwnerFence', 'VbxeOwnerSubmit')})
        result.append(sample_result)
    return dict(status='pass', trace_events=len(events), selected_pcs=len(d['pcs']),
        presenter_dp=worker, samples=result, unfinished_calls=unfinished,
        owned_core_scope='ExecAESBeginUpdate return to END wind_update entry: UPDATE is already owned throughout.',
        phase_scope='Exclusive presenter CPU by outermost selected native phase; clipped calls included; IRQ/NMI separate.')
