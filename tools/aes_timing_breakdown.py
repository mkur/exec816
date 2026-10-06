"""Passive scheduler milestones and exclusive caller CPU categories.

Ready means TASKPOLICY.Ready has finished queue publication. Selected means the
checked context-restore boundary has restored D. Neither is a new guest marker.
Interrupt and scheduling tails retain console_turn_profile's conservative charge.
"""
from bisect import bisect_right
from collections import defaultdict
import re

from aes_latency_trace import routine
from bitmap_console_performance import native_markers
from console_turn_profile import Timeline
from generate_tasks import constants
from native_program import require
from sio_transaction_trace import BASE_HZ


def image_bytes(program, address, size):
    for segment in program['image']['segments']:
        offset = address-segment['address']
        if 0 <= offset and offset+size <= len(segment['bytes']):
            return bytes(segment['bytes'][offset:offset+size])
    raise RuntimeError('Missing emitted observer bytes')


def scheduler_markers(program):
    base, raw = routine(program, 'TASKPOLICY_READY')
    loads = list(re.finditer(rb'\xa3(.)\x85\x80\xa3(.)\x85\x81', raw, re.S))
    require(len(loads) == 1 and loads[0][2][0] == loads[0][1][0]+1,
            'Unknown Ready context load')
    span = native_markers(program, [('TASKPOLICY_READY', 'ready')])['ready']
    require(len(span['returns']) == 1, 'Unknown Ready return')
    # Wait publishes its context through an absolute indexed state store.
    # Derive its address from the generated image contract, then verify bytes.
    c = constants()
    table = max(program['build']['memory']['usable_banks']) << 16
    begin, end = (program['labels'][n] for n in ('signal_wait_begin', 'signal_wait_begin_end'))
    code = image_bytes(program, begin, end-begin)
    needle = bytes((0xa9, c['STATE_SIGNAL_WAIT'], 0x9f))+(table+c['TCB_STATE']).to_bytes(3, 'little')
    require(code.count(needle) == 1, 'Unknown signal-wait state publication')
    points = dict(ready_low=base+loads[0].start()+2, ready_high=base+loads[0].start()+6,
                  ready=span['returns'][0], blocked=begin+code.index(needle)+2)
    return dict(points=points, context_base=table, context_stride=c['SIZE'],
                task_dps=[p['dp'] for p in program['build']['memory']['task_pools']])


def scheduler_states(events, definition, selected):
    points = definition['points']
    parts = {}
    states = defaultdict(list)
    selections = defaultdict(list)
    def task(context):
        offset = context-definition['context_base']
        slot, remainder = divmod(offset, definition['context_stride'])
        require(remainder == 0 and 0 <= slot < len(definition['task_dps']),
                'Unknown scheduler context')
        return definition['task_dps'][slot]
    for tick, e in events:
        if e[0] != 'cpu':
            continue
        pc, a, x, dp = (int(e[i], 16) for i in (4, 5, 6, 9))
        if pc == points['ready_low']:
            require(not parts, 'Overlapping Ready observer')
            parts['low'] = a
        elif pc == points['ready_high']:
            require('low' in parts, 'Missing Ready low pointer')
            parts['high'] = a
        elif pc == points['ready']:
            require(set(parts) == {'low', 'high'}, 'Missing Ready context')
            require(parts['low'] >> 8 == parts['high'] & 255, 'Ready pointer overlap disagrees')
            states[task((parts['low'] & 255) | parts['high'] << 8)].append((tick, 'ready'))
            parts.clear()
        elif pc == points['blocked']:
            states[task(definition['context_base']+x)].append((tick, 'blocked'))
        elif pc == selected and dp in definition['task_dps']:
            states[dp].append((tick, 'selected'))
            selections[dp].append(tick)
    require(not parts, 'Incomplete Ready observer')
    require(states and any(s == 'blocked' for rows in states.values() for _, s in rows),
            'Missing scheduler state observations')
    return states, selections


def input_breakdown(events, definition, profile, samples, consume):
    worker = profile['worker_dp']
    states, selections = scheduler_states(events, definition, definition['selected'])
    changes = states[worker]
    ticks = [t for t, _ in changes]
    consumed = [(t, int(e[9], 16)) for t, e in events
                if e[0] == 'cpu' and int(e[4], 16) == consume]
    require(consumed and all(dp == worker for _, dp in consumed), 'Input consumer is not presenter')
    consumption = [t for t, _ in consumed]
    segments = profile['segments']
    segment_ticks = [s[0] for s in segments]
    timeline = Timeline(segments, worker)
    rows = []
    for sample in samples:
        capture = sample['capture']
        at = bisect_right(ticks, capture)-1
        require(at >= 0, 'Missing presenter state before capture')
        state = changes[at][1]
        i = bisect_right(consumption, capture)
        require(i < len(consumption), 'Missing consumption after capture')
        end = consumption[i]
        require(end <= sample['observed'], 'Consumption outside observed input boundary')
        ready = capture if state != 'blocked' else next(
            (t for t, s in changes[at+1:] if s == 'ready' and t <= end), None)
        require(ready is not None, 'Missing presenter ready publication')
        running = capture if state == 'selected' else next(
            (t for t in selections[worker] if ready <= t <= end), None)
        require(running is not None, 'Missing presenter selection')
        # Off-CPU time is split by the observed queue/wait state. This includes
        # subsequent preemptions, unlike the first-ready/first-selected pair.
        waiting = runnable = 0
        first = max(0, bisect_right(segment_ticks, capture)-1)
        last = bisect_right(segment_ticks, end)
        for a, b, owner, _ in segments[first:last]:
            lo, hi = max(a, capture), min(b, end)
            if hi <= lo or owner == worker:
                continue
            j = bisect_right(ticks, lo)-1
            require(j >= 0, 'Missing state during off-CPU interval')
            if changes[j][1] == 'blocked': waiting += hi-lo
            else: runnable += hi-lo
        charge = timeline.measure(capture, end)
        factor = 1000/BASE_HZ
        require(abs(charge['off_cpu_ms']-(waiting+runnable)*factor) < 1e-7,
                'Input off-CPU categories do not reconcile')
        rows.append(dict(sample, presenter_state_at_capture=state, ready=ready, selected=running,
                         consumed=end, capture_to_ready_ms=(ready-capture)*factor,
                         ready_to_selected_ms=(running-ready)*factor,
                         selected_to_consume_ms=(end-running)*factor,
                         runnable_off_cpu_ms=runnable*factor, blocked_off_cpu_ms=waiting*factor,
                         **charge))
    return dict(scope=__doc__, worker_dp=worker, records=rows)


CATEGORIES = {
    'binding': ('ExecAESContext', 'ExecAESEnter', 'ExecAESPointer'),
    'clock': ('ExecAESTimerRead',),
    'deadline': ('ExecAESTimerDeadline',),
    'alarm_submit': ('ExecAESTimerSend',),
    'alarm_retire': ('ExecAESTimerCollect', 'ExecAESTimerClose'),
    'message': ('ExecAESReserve', 'ExecAESPublish', 'ExecAESRecycle', 'GetMsg', 'PutMsg'),
    'device_io': ('DoIO', 'SendIO', 'CheckIO', 'AbortIO', 'OpenDevice', 'CloseDevice'),
    'wait': ('Wait',),
}


def caller_markers(program, foreign):
    """Observe checked JSL/return sites, including calls with shared epilogues."""
    symbols = foreign['symbols']
    targets = {name: category for category, names in CATEGORIES.items() for name in names}
    sites = {}
    for stem in ('aes', 'aes-events', 'aes-messages'):
        paths = list((program['output'].parent/'drawing').glob('*-'+stem+'.lst'))
        require(len(paths) == 1, 'Missing caller-cost listing '+stem)
        # Local Calypsi helpers also contain these calls. Their names collide
        # across translation units, so resolve complete emitted sections with
        # relocation wildcards and exact target operands, never the symbol map's
        # arbitrary equal-named local. This checks instruction boundaries too.
        for section in paths[0].read_text().split('.section ')[1:]:
            if not section.startswith('farcode,text'): continue
            calls = [(int(m[1], 16), m[2]) for m in re.finditer(
                r'\\ ([0-9a-f]{6}) 22[.]{6}\s+jsl\s+long:(\w+)\s*$', section, re.M)
                if m[2] in targets]
            if not calls: continue
            code = {}
            for match in re.finditer(r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+', section):
                offset = int(match[1], 16)
                for i in range(0, len(match[2]), 2):
                    code[offset+i//2] = match[2][i:i+2]
            require(set(code) == set(range(max(code)+1)), 'Incomplete caller-cost section')
            for offset, name in calls:
                for i, value in enumerate(symbols[name].to_bytes(3, 'little')):
                    code[offset+1+i] = f'{value:02x}'
            pattern = b''.join(b'.' if code[i] == '..' else re.escape(bytes.fromhex(code[i]))
                               for i in range(len(code)))
            locations = [s['address']+match.start() for s in foreign['segments'] if s['executable']
                         for match in re.finditer(pattern, bytes(s['bytes']), re.S)]
            public = re.search(r'\.public (\w+)', section)
            require(locations or public is None or public[1] not in symbols,
                    'Missing linked caller-cost section: '+str(public[1] if public else calls))
            for base in locations:
                for offset, name in calls:
                    pc = base+offset
                    sites[pc] = dict(end=pc+4, category=targets[name], callee=name)
    require(all(any(s['category'] == group for s in sites.values()) for group in CATEGORIES),
            'Incomplete caller-cost categories')
    return sites


def caller_breakdown(events, sites, segments, calls):
    sites = {int(pc): value for pc, value in sites.items()}
    stacks = defaultdict(list)
    spans = []
    for tick, e in events:
        if e[0] != 'cpu': continue
        pc, dp = int(e[4], 16), int(e[9], 16)
        stack = stacks[dp]
        if stack and pc == stack[-1]['end_pc']:
            row = stack.pop()
            spans.append(dict(row, end=tick))
        if pc in sites:
            site = sites[pc]
            stack.append(dict(start=tick, end_pc=site['end'], dp=dp,
                              category=site['category'], callee=site['callee'], depth=len(stack)))
    require(not any(stacks.values()), 'Incomplete caller-cost span')
    timelines = {dp: Timeline(segments, dp) for dp in {r['dp'] for r in calls}}
    rows = []
    for call in calls:
        begin, end, dp = call['start'], call['client'], call['dp']
        selected = [s for s in spans if s['dp'] == dp and begin <= s['start'] < s['end'] <= end]
        boundaries = sorted({begin, end, *(t for s in selected for t in (s['start'], s['end']))})
        buckets = defaultdict(float)
        for a, b in zip(boundaries, boundaries[1:]):
            enclosing = [s for s in selected if s['start'] <= a < b <= s['end']]
            category = max(enclosing, key=lambda s: s['depth'])['category'] if enclosing else 'other'
            buckets[category] += timelines[dp].measure(a, b)['charged_cpu_ms']
        measured = timelines[dp].measure(begin, end)
        require(abs(sum(buckets.values())-measured['charged_cpu_ms']) < 1e-7,
                'Caller CPU categories do not reconcile')
        io_calls = [dict(callee=s['callee'], **timelines[dp].measure(s['start'], s['end']))
                    for s in selected if s['category'] == 'device_io']
        rows.append(dict(dp=dp, operation=call['operation'], start=begin, end=end,
                         device_io_calls=io_calls,
                         exclusive_cpu_ms=dict(buckets), **measured))
    return dict(scope='Exclusive charged CPU by innermost checked C call site. Other includes wrapper setup, event matching, copying and unclassified helper work. Wait CPU excludes sleeping/off-Task time.',
                records=rows)
