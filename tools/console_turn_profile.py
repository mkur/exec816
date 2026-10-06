"""Passive console turn accounting on the pinned native adapter.

Charged CPU includes calls into C and the kernel, scheduling/return overhead and
bus stalls. Native IRQ/NMI bodies and time assigned to another Task are separate.
This is a conservative service charge, not an instruction-only profiler. No
instructions, storage or scheduling changes are inserted into the guest.
"""
from bisect import bisect_right
from collections import defaultdict

from bitmap_console_performance import native_markers, markers as drawing_markers
from dos_concurrent_trace import call_marker
from native_program import require
from sio_transaction_trace import BASE_HZ, read_events


def markers(program, foreign, output):
    routines = [('CONSOLEDRIVER_COLLECT', 'collect'),
                ('CONSOLEINPUT_SERVICE', 'input'),
                ('CONSOLECONTROL_PROCESS', 'control'),
                ('CONSOLEDRIVER_ARRIVAL', 'arrival'),
                ('CONSOLEWINDOWS_TAKE', 'take'),
                ('CONSOLEDRIVER_READQUANTUM', 'read'),
                ('CONSOLEDRIVER_WRITEQUANTUM', 'write'),
                ('CONSOLECORE_FEED', 'feed'),
                ('CONSOLECORE_EDITQUANTUM', 'model_edit'),
                ('CONSOLEDISPLAY_PRESENT', 'present'),
                ('CONSOLEDISPLAY_CELLS', 'cells'),
                ('CONSOLEDISPLAY_POLL', 'poll'),
                ('CONSOLEDISPLAY_ADVANCE', 'advance'),
                ('CONSOLEBITMAP_TEXT', 'text'),
                ('CONSOLEBITMAP_TEXTCARET', 'text_fill'),
                ('CONSOLEBITMAP_FILL', 'fill'),
                ('CONSOLEBITMAP_SCROLL', 'scroll'),
                ('CONSOLEDRIVER_RUNNABLE', 'runnable')]
    spans = native_markers(program, routines)
    drawing = drawing_markers(program, foreign, output)
    spans['idle'] = drawing['idle']
    mapped = {**program, 'labels': {**program['labels'], 'collect': spans['collect']['entry']}}
    points = dict(turn=call_marker(mapped, 'M_CONSOLEDRIVER_WORKER_', 'collect'))
    # Check emitted bytes, not a guessed source offset. PLD has restored the
    # selected Task's D at this marker; the following register/RTI tail is charged
    # to that Task. IRQ entry and interrupt_schedule bracket the native body.
    address = program['labels']['context_restore']
    hosted = (program['output']/'hosted.bin').read_bytes()
    require(hosted[address-0x1400:address-0x1400+8] == bytes.fromhex('c230ab2b7afa6840'),
            'Unrecognized context restore sequence')
    points['selected'] = address+4
    for name in ('native_irq', 'native_nmi', 'interrupt_schedule'):
        points[name] = program['labels'][name]
    for name in ('blitter_irq_complete', 'blitter_irq_posted', 'blitter_expired'):
        if name in program['labels']:
            points[name] = program['labels'][name]
    points['worker_retire'] = next(r['address'] for r in program['image']['routines']
                                  if r['name'].startswith('M_CONSOLEDRIVER_RETIREWORKER_'))
    return dict(spans=spans, points=points,
                task_dps=[p['dp'] for p in program['build']['memory']['task_pools']])


def flat_markers(definition):
    result = {'turn_'+key: pc for key, pc in definition['points'].items()}
    for name, span in definition['spans'].items():
        result['turn_'+name+'_entry'] = span['entry']
        for i, pc in enumerate(span['returns']):
            result[f'turn_{name}_return_{i}'] = pc
    return result


class Timeline:
    """Prefix sums of exclusive wall time, charged CPU and native interrupts."""
    def __init__(self, segments, worker):
        self.ticks = [segments[0][0]]
        self.sums = [(0, 0, 0)]
        self.rates = []
        for start, end, owner, interrupt in segments:
            require(start == self.ticks[-1] and end >= start, 'Broken CPU timeline')
            # IRQs on peers remain off-worker time; IRQs on the worker are
            # separated from its conservative CPU charge.
            rate = (int(owner == worker and not interrupt),
                    int(owner != worker), int(owner == worker and interrupt))
            self.rates.append(rate)
            self.sums.append(tuple(a+(end-start)*b for a, b in zip(self.sums[-1], rate)))
            self.ticks.append(end)

    def at(self, tick):
        require(self.ticks[0] <= tick <= self.ticks[-1], 'Time outside CPU trace')
        i = min(bisect_right(self.ticks, tick)-1, len(self.rates)-1)
        return tuple(a+(tick-self.ticks[i])*b for a, b in zip(self.sums[i], self.rates[i]))

    def measure(self, start, end):
        delta = [(b-a)/BASE_HZ*1000 for a, b in zip(self.at(start), self.at(end))]
        return dict(elapsed_ms=(end-start)/BASE_HZ*1000,
                    charged_cpu_ms=delta[0], off_cpu_ms=delta[1], interrupt_ms=delta[2])


def analyze_events(events, definition, window=None, allow_empty_window=False, intervals=()):
    points, definitions = definition['points'], definition['spans']
    turns = [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == points['turn']]
    workers = {int(e[9], 16) for t, e in events
               if e[0] == 'cpu' and int(e[4], 16) == points['turn']}
    require(len(workers) == 1 and len(turns) > 1, 'Missing unique console worker turns')
    worker = workers.pop()
    owner = None
    interrupts = []
    segments = []
    previous = events[0][0]
    active = {}
    spans = []
    previous_cpu = None
    repeated_entries = 0
    boundaries = defaultdict(list)
    for name, d in definitions.items():
        boundaries[d['entry']].append((name, True))
        for pc in d['returns']:
            boundaries[pc].append((name, False))
    for tick, e in events:
        if e[0] != 'cpu':
            continue
        if tick > previous:
            segments.append((previous, tick, owner, bool(interrupts)))
        previous = tick
        pc, dp = int(e[4], 16), int(e[9], 16)
        if pc in (points['native_irq'], points['native_nmi']):
            # A bridge breakpoint at interrupt entry records the stopped PC
            # again on resume, without executing its instruction twice. Only
            # coalesce an identical consecutive context at the still-live frame.
            frame = int(e[8], 16)-9
            if interrupts and interrupts[-1] == frame and previous_cpu == e[4:]:
                repeated_entries += 1
            else:
                interrupts.append(frame)
        elif pc == points['interrupt_schedule']:
            require(interrupts and interrupts.pop() == int(e[8], 16),
                    'Unbalanced native interrupt frame')
        elif pc == points['selected'] and dp in definition['task_dps']:
            require(not interrupts, 'Task selected inside a live interrupt')
            owner = dp
        if pc == points['turn']:
            require(owner == worker and not interrupts, 'Worker ownership trace disagrees')
        previous_cpu = e[4:]
        for name, entry in boundaries[pc]:
            if dp != worker:
                continue
            if entry:
                require(name not in active, 'Nested worker span '+name)
                active[name] = tick
            elif name in active:
                spans.append(dict(kind=name, start=active.pop(name), end=tick,
                                  return_a=int(e[5], 16), return_x=int(e[6], 16)))
    require(not active and not interrupts, 'Incomplete worker/interrupt trace')
    timeline = Timeline(segments, worker)
    rows = [dict(start=a, end=b, **timeline.measure(a, b)) for a, b in zip(turns, turns[1:])]
    for span in spans:
        span.update(timeline.measure(span['start'], span['end']))
    # The last worker loop is partial (Stop exits instead of beginning another
    # turn). Routine spans still include shutdown, with their own names.
    if window is not None:
        rows = [r for r in rows if window[0] <= r['start'] < r['end'] <= window[1]]
        require(rows or allow_empty_window, 'No complete worker turns in workload window')
    start, end = (rows[0]['start'], rows[-1]['end']) if rows else window
    totals = {}
    for kind in definitions:
        selected = [s for s in spans if s['kind'] == kind and start <= s['start'] < s['end'] <= end]
        if selected:
            totals[kind] = dict(calls=len(selected), **{
                label: dict(total=sum(s[label] for s in selected), max=max(s[label] for s in selected))
                for label in ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')})
    interval_timelines = {worker: timeline}
    measured_intervals = []
    for interval in intervals:
        dp = interval['dp']
        require(dp in definition['task_dps'], 'Unknown interval Task direct page')
        if dp not in interval_timelines:
            interval_timelines[dp] = Timeline(segments, dp)
        measured_intervals.append(dict(interval, **interval_timelines[dp].measure(
            interval['start'], interval['end'])))
    slow = sorted(rows, key=lambda row: row['elapsed_ms'], reverse=True)[:10]
    for row in slow:
        row['routines'] = [s for s in spans if row['start'] <= s['start'] <= s['end'] <= row['end']]
    return dict(scope=__doc__, worker_dp=worker, complete_turns=len(rows), window=window,
                measured_intervals=measured_intervals,
                observed_turn_entries=sum(start <= t <= end for t in turns),
                window_cpu=timeline.measure(start, end),
                repeated_breakpoint_entries=repeated_entries,
                turns=rows, routines=totals, routine_spans=spans, slowest_turns=slow,
                global_interrupt_ms=sum(max(0, min(b, end)-max(a, start))
                    for a, b, _, irq in segments if irq)/BASE_HZ*1000,
                max_charged_cpu_ms=max((r['charged_cpu_ms'] for r in rows), default=0),
                max_elapsed_ms=max((r['elapsed_ms'] for r in rows), default=0),
                max_off_cpu_ms=max((r['off_cpu_ms'] for r in rows), default=0))


def analyze(path, definition, marks):
    events = read_events(path)
    starts = [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == marks['flood_begin']]
    ends = [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == marks['flood_collected']]
    require(starts and ends and len(starts) == len(ends), 'Incomplete producer workload')
    return analyze_events(events, definition, (starts[0], ends[-1]))
