"""Passive scroll completion boundaries; hardware BUSY edges are not inferred."""
from native_program import require
from sio_transaction_trace import BASE_HZ, read_events


def markers(program):
    labels = program['labels']
    result = {}
    for name in ('blitter_irq_complete', 'blitter_irq_posted', 'blitter_expired',
                 'tasks_wait', 'exec_yield', 'native_irq', 'native_nmi',
                 'interrupt_schedule', 'blitter_watchdog', 'blitter_watchdog_done'):
        if name in labels:
            result['completion_' + name] = dict(entry=labels[name], returns=[], entry_only=True)
    if 'context_restore' in labels:
        address = labels['context_restore']
        from adapter_state import RESIDENT_BASE
        binary = (program['output']/'hosted.bin').read_bytes()
        require(binary[address-RESIDENT_BASE:address-RESIDENT_BASE+8] ==
                bytes.fromhex('c230ab2b7afa6840'), 'Unknown context restore')
        result['completion_selected'] = dict(entry=address+4, returns=[], entry_only=True)
    return result


def analyze_events(events, marks):
    names = {}
    for name, spec in marks.items():
        names.setdefault(spec['entry'], []).append(name)
    launch_name = 'async_launch' if 'async_launch' in marks else 'launch'
    submitted = set()
    active = None
    rows = []
    for tick, event in events:
        if event[0] != 'cpu':
            continue
        dp = int(event[9], 16)
        for name in names.get(int(event[4], 16), []):
            if name == 'GemDrawingScrollStart':
                submitted.add(dp)
            elif name == launch_name and dp in submitted:
                require(active is None, 'Overlapping scroll completion trace')
                submitted.remove(dp)
                active = dict(start=tick, worker_dp=dp, polls=0, waits=0,
                              yields=0, irq=None, posted=None, expired=None,
                              resumed=None, hardware_busy_end=None)
            elif active is not None:
                point = {'completion_blitter_irq_complete': 'irq',
                         'completion_blitter_irq_posted': 'posted',
                         'completion_blitter_expired': 'expired'}.get(name)
                if point:
                    require(active[point] is None, 'Duplicate terminal boundary '+point)
                    active[point] = tick
                elif dp == active['worker_dp']:
                    if name == 'GemDrawingScrollPoll':
                        active['polls'] += 1
                    elif name == 'completion_tasks_wait':
                        active['waits'] += 1
                    elif name == 'completion_exec_yield':
                        active['yields'] += 1
                    elif name == 'completion_selected' and active['posted'] is not None and active['resumed'] is None:
                        active['resumed'] = tick
                    elif name == 'bitmap_complete':
                        active['adopt_begin'] = tick
                        for label, first, last in (
                            ('launch_to_adoption_upper_ms', 'start', 'adopt_begin'),
                            ('launch_to_irq_observation_upper_ms', 'start', 'irq'),
                            ('irq_to_post_ms', 'irq', 'posted'),
                            ('post_to_resumed_ms', 'posted', 'resumed'),
                            ('post_to_adoption_ms', 'posted', 'adopt_begin')):
                            a, b = active[first], active[last]
                            active[label] = None if a is None or b is None else (b-a)/BASE_HZ*1000
                        rows.append(active)
                        active = None
    require(active is None, 'Incomplete scroll completion trace')
    return dict(scope='CPU observation boundaries. IRQ observation and adoption are upper bounds on hardware completion; exact BUSY edges unavailable.',
                scrolls=rows)


def analyze(path, marks):
    events = read_events(path)
    result = analyze_events(events, marks)
    cpu_cost(events, marks, result['scrolls'])
    return result


def cpu_cost(events, marks, rows):
    """Exclusive worker charge plus global native interrupt cost per active list.

    Do not count interrupt bodies again as worker CPU, or add nested watchdog
    time to the IRQ total. Scheduling/RTI remains a conservative Task charge.
    """
    from console_turn_profile import Timeline
    keys = ('native_irq', 'native_nmi', 'interrupt_schedule', 'selected')
    if not all('completion_'+key in marks for key in keys):
        return
    require(events, 'Empty completion CPU trace')
    points = {key: marks['completion_'+key]['entry'] for key in keys}
    watchdog = {key: marks['completion_'+key]['entry'] for key in
                ('blitter_watchdog', 'blitter_watchdog_done') if 'completion_'+key in marks}
    owner = None
    frames = []
    previous = events[0][0]
    previous_cpu = None
    segments = []
    watch_start = None
    watch_spans = []
    for tick, e in events:
        if e[0] != 'cpu':
            continue
        pc, dp = int(e[4], 16), int(e[9], 16)
        if tick > previous:
            segments.append((previous, tick, owner, bool(frames)))
        previous = tick
        if pc in (points['native_irq'], points['native_nmi']):
            frame = int(e[8], 16)-9
            if not (frames and frames[-1] == frame and previous_cpu == e[4:]):
                frames.append(frame)
        elif pc == points['interrupt_schedule']:
            require(frames and frames.pop() == int(e[8], 16), 'Unbalanced completion IRQ trace')
        elif pc == points['selected']:
            require(not frames, 'Selection inside completion IRQ trace')
            owner = dp
        if pc == watchdog.get('blitter_watchdog'):
            require(watch_start is None, 'Nested watchdog check')
            watch_start = tick
        elif pc == watchdog.get('blitter_watchdog_done') and watch_start is not None:
            watch_spans.append((watch_start, tick))
            watch_start = None
        previous_cpu = e[4:]
    require(not frames and watch_start is None, 'Incomplete completion CPU trace')
    if not rows:
        return
    worker = rows[0]['worker_dp']
    require(all(row['worker_dp'] == worker for row in rows), 'Multiple completion owners')
    worker_time = Timeline(segments, worker)
    irq_time = Timeline([(a, b, worker, irq) for a, b, owner, irq in segments], worker)
    for row in rows:
        a, b = row['start'], row['adopt_begin']
        charge = worker_time.measure(a, b)
        irq = irq_time.measure(a, b)['interrupt_ms']
        checks = [(x, y) for x, y in watch_spans if a <= x < y <= b]
        row['cpu'] = dict(worker_charged_ms=charge['charged_cpu_ms'],
            off_worker_ms=charge['off_cpu_ms'], native_interrupt_ms=irq,
            worker_plus_native_interrupt_ms=charge['charged_cpu_ms']+irq,
            watchdog_checks=len(checks), watchdog_nested_ms=sum(y-x for x, y in checks)/BASE_HZ*1000)
