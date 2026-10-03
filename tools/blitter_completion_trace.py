"""Passive scroll completion boundaries; hardware BUSY edges are not inferred."""
from native_program import require
from sio_transaction_trace import BASE_HZ, read_events


def markers(program):
    labels = program['labels']
    result = {}
    for name in ('blitter_irq_complete', 'blitter_irq_posted', 'blitter_expired',
                 'tasks_wait', 'exec_yield'):
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
    return analyze_events(read_events(path), marks)
