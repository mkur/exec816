"""Passive G4BENCH call boundaries, Task accounting and exclusive work costs.

The observer executes no guest instructions. Caller return PCs are recovered
from compiler listings and checked against linked bytes. Full native S and D
match returns, including optimized tail calls and shared compiler epilogues.
"""
from collections import defaultdict
from bisect import bisect_left
import re
import gzip

import adapter_state as adapter
from console_turn_profile import Timeline, analyze_events
from dos_concurrent_trace import call_marker
from native_program import require
from sio_transaction_trace import BASE_HZ


APP_NAMES = ('batch', 'BenchDraw', 'BenchClockRead', 'full_canvas', 'events',
             '_Mul16', '_Mod16', '_Div16')
# Measure arithmetic through its public wrappers. The compiler runtime's
# internal call successors have no C listing in this build.
C_NAMES = '''wind_update v_bar v_gtext objc_draw GemDrawingBorrow DisplayEnter
DisplayLeave GemVdiPaint vdi_v_gtext just_draw GemWidgetText
vbxe_glyph vbxe_fill_rect vbxe_text_run vbxe_widget_text_run blit_glyph
blit_glyph_run glyph_record blit_mask text_run VbxeOwnerFence idle
VbxeOwnerSubmit VbxeOwnerRead VbxeOwnerWrite _VbxeUpload _VbxeTextUpload
start fence_owner drain pointer_erase'''.split()
# Optional boundaries let the same observer compare archived pre-fill images.
FILL_NAMES='GemSolidRows GemSolidFill solid_record GemDrawingSolidBorrow drawing_borrow vdi_vr_recfl'.split()


def listing_returns(image, directory):
    """Find JSL successor PCs without scanning operand bytes as instructions.

    Local outlined sections may have no unique exported symbol. Match their
    complete emitted section, with relocation bytes as wildcards. Ambiguous
    short matches only add possible return PCs: native S must still match a
    live observed call before such a PC can finish a span.
    """
    segments = [(s['address'], bytes(s['bytes'])) for s in image['segments'] if s['executable']]
    returns = set()
    for path in sorted(directory.glob('*.lst')):
        if path.name == 'link.lst':
            continue
        for section in path.read_text().split('.section ')[1:]:
            if not section.startswith('farcode,text'):
                continue
            calls = [int(m[1], 16) for m in re.finditer(
                r'\\ ([0-9a-f]{6}) 22[.]{6}\s+jsl\s', section)]
            if not calls:
                continue
            code = {}
            for match in re.finditer(r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+', section):
                offset = int(match[1], 16)
                for i in range(0, len(match[2]), 2):
                    code[offset+i//2] = match[2][i:i+2]
            require(set(code) == set(range(max(code)+1)), 'Incomplete listing section '+str(path))
            pattern = b''.join(b'.' if code[i] == '..' else re.escape(bytes.fromhex(code[i]))
                               for i in range(len(code)))
            for base, payload in segments:
                for match in re.finditer(pattern, payload, re.S):
                    for offset in calls:
                        require(payload[match.start()+offset] == 0x22, 'Not a linked JSL')
                        returns.add(base+match.start()+offset+4)
    require(returns, 'Missing linked call returns')
    return sorted(returns)


def definition(program, foreign, app, directory):
    collect = next(r['address'] for r in program['image']['routines']
                   if r['name'].startswith('M_CONSOLEDRIVER_COLLECT_'))
    mapped = {**program, 'labels': {**program['labels'], 'collect': collect}}
    points = dict(turn=call_marker(mapped, 'M_CONSOLEDRIVER_WORKER_', 'collect'))
    address = program['labels']['context_restore']
    hosted = (program['output']/'hosted.bin').read_bytes()
    require(hosted[address-adapter.RESIDENT_BASE:address-adapter.RESIDENT_BASE+8] ==
            bytes.fromhex('c230ab2b7afa6840'), 'Unrecognized context restore')
    points['selected'] = address+4
    for name in ('native_irq', 'native_nmi', 'interrupt_schedule'):
        points[name] = program['labels'][name]
    timeline = dict(points=points, spans={},
                    task_dps=[p['dp'] for p in program['build']['memory']['task_pools']])
    entries = {foreign['symbols'][name]: name for name in C_NAMES if name in foreign['symbols']}
    require(len(entries) == len(C_NAMES), 'Missing resident trace function')
    entries.update({foreign['symbols'][name]:name for name in FILL_NAMES if name in foreign['symbols']})
    application = {app['image']['symbols'][name]: name for name in APP_NAMES}
    return dict(timeline=timeline, resident_entries=entries, app_entries=application,
                resident_returns=listing_returns(foreign, directory/'drawing'),
                app_returns=listing_returns(app['image'], directory/'apps/g4bench'),
                link_base=app['abi']['link_bank'] << 16, banks=app['verified_banks'])


def marker_pcs(d):
    points = set(d['resident_entries']) | set(d['resident_returns'])
    points.update(d['timeline']['points'].values())
    # The allocation is discovered after normal shell loading. Register only
    # legal relocations up front; analyze only the actual retained Process.
    for bank in d['banks']:
        delta = (bank << 16)-d['link_base']
        points.update(pc+delta for pc in d['app_entries'])
        points.update(pc+delta for pc in d['app_returns'])
    return sorted(points)


def loaded_markers(d, live):
    delta = live['base']-d['link_base']
    entries = {int(pc): name for pc, name in d['resident_entries'].items()}
    entries.update({int(pc)+delta: name for pc, name in d['app_entries'].items() if name in APP_NAMES})
    returns = set(d['resident_returns']) | {pc+delta for pc in d['app_returns']}
    return entries, returns


def read_trace(path, d, live):
    """Stream the large bridge log, retaining only meaningful CPU boundaries.

    Other legal application placements and unused return PCs are registered
    before loading. They cannot affect accounting for the actual app. A live
    selected frame must match D and full S before retaining a return event.
    """
    entries, returns = loaded_markers(d, live)
    points = set(d['timeline']['points'].values())
    draw = next(pc for pc, name in entries.items() if name == 'BenchDraw')
    def source():
        return gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()
    dps = set()
    with source() as lines:
        for line in lines:
            if '] cpu ' not in line: continue
            fields = line.split('] ', 1)[1].split()
            if int(fields[4], 16) == draw: dps.add(int(fields[9], 16))
    require(len(dps) == 1, 'No unique benchmark Task in trace')
    dp = dps.pop(); tick = 0; active = set(); result = []
    with source() as lines:
        for line in lines:
            tag = next((tag for tag in ('[SIOPOC] ', '[SIOTXN] ') if tag in line), None)
            if tag is None: continue
            fields = line.split(tag, 1)[1].split()
            value = int(fields[1]); fraction = 0
            if fields[0] in ('cpu', 'mask'):
                value += round((tick-value)/(1 << 32))*(1 << 32)
                require(int(fields[3]) == 8, 'Observer CPU multiplier changed')
                fraction = int(fields[2])/8
            tick = value
            if fields[0] != 'cpu': continue
            pc, owner, stack = (int(fields[i], 16) for i in (4, 9, 8))
            keep = pc in points
            if owner == dp:
                if pc in returns and stack-3 in active:
                    active.remove(stack-3); keep = True
                if pc in entries:
                    active.add(stack); keep = True
            if keep: result.append((value+fraction, fields))
    require(result, 'Empty selected CPU trace')
    # The capture ends paused at the first IRQ after phase=report. No guest
    # interrupt body ran there. Remove only that unexecuted trailing entry;
    # all measured batches and their returns precede it.
    interrupts = {d['timeline']['points'][k] for k in ('native_irq', 'native_nmi')}
    while result and int(result[-1][1][4], 16) in interrupts:
        result.pop()
    return result


def calls(events, entries, returns, dp):
    active = defaultdict(list)
    rows = []
    for tick, e in events:
        if e[0] != 'cpu' or int(e[9], 16) != dp:
            continue
        pc, stack = int(e[4], 16), int(e[8], 16)
        if pc in returns:
            # A JSL frame is three bytes. Tail-called functions share that
            # frame and end together at its caller's successor instruction.
            for opened in active.pop(stack-3, []):
                rows.append(dict(opened, end=tick, return_a=int(e[5], 16)))
        if pc in entries:
            require(not any(row['kind'] == entries[pc] for row in active[stack]),
                    'Repeated function entry without a matched return: '+entries[pc])
            active[stack].append(dict(kind=entries[pc], start=tick,
                                      argument=int(e[5], 16), stack=stack))
    return rows, [row for group in active.values() for row in group]


def category(names):
    """Priority chooses exclusive CPU costs; inclusive calls remain separate."""
    if 'wind_update' in names: return 'update'
    if 'full_canvas' in names: return 'visibility'
    if 'events' in names: return 'event_poll'
    if 'DisplayEnter' in names or 'DisplayLeave' in names: return 'display_ownership'
    if 'idle' in names: return 'completion_poll'
    if '_VbxeUpload' in names or '_VbxeTextUpload' in names: return 'upload'
    if names & {'VbxeOwnerSubmit', 'VbxeOwnerFence', 'start'}: return 'submission_fence'
    if names & {'blit_mask', 'blit_glyph', 'blit_glyph_run', 'glyph_record', 'text_run', 'GemSolidFill', 'solid_record'}:
        return 'command_build'
    if names & {'borrow_callback', 'GemVdiPaint', 'just_draw', 'GemWidgetText'}: return 'renderer'
    if names & {'GemDrawingBorrow','GemDrawingSolidBorrow','drawing_borrow'}: return 'borrow_setup_cursor'
    if names & {'v_bar', 'v_gtext', 'objc_draw'}: return 'vdi_aes_preparation'
    if names & {'_Mul16', '_Mod16', '_Div16', '_UDivMod16'}: return 'app_arithmetic'
    return 'app_other'


def partition(timeline, spans, start, end):
    boundaries = defaultdict(list)
    boundaries[start]; boundaries[end]
    for i, span in enumerate(spans):
        left, right = max(start, span['start']), min(end, span['end'])
        if left < right:
            boundaries[left].append((i, True))
            boundaries[right].append((i, False))
    active = set(); totals = defaultdict(float); previous = start
    for tick in sorted(boundaries):
        if tick > previous:
            names = {spans[i]['kind'] for i in active}
            totals[category(names)] += timeline.measure(previous, tick)['charged_cpu_ms']
        for index, opening in boundaries[tick]:
            if opening: active.add(index)
            else: active.remove(index)
        previous = tick
    measured = timeline.measure(start, end)
    require(abs(sum(totals.values())-measured['charged_cpu_ms']) < 1e-6,
            'Exclusive CPU costs do not reconcile')
    return dict(totals)


def analyze(events, d, live, benchmark):
    entries, returns = loaded_markers(d, live)
    application_pcs = {pc for pc, name in entries.items() if name == 'BenchDraw'}
    dps = {int(e[9], 16) for _, e in events if e[0] == 'cpu' and int(e[4], 16) in application_pcs}
    require(len(dps) == 1, 'No unique benchmark Task in trace')
    dp = dps.pop()
    profile = analyze_events(events, d['timeline'], include_segments=True)
    timeline = Timeline(profile['segments'], dp)
    spans, unfinished = calls(events, entries, returns, dp)
    # A reporting helper may have started before the final IRQ breakpoint.
    # Every function that began before the last measured batch ended must
    # finish, including callbacks and tail calls.
    last_batch = max(s['end'] for s in spans if s['kind'] == 'batch')
    require(all(s['start'] >= last_batch for s in unfinished),
            'Unfinished drawing functions: '+str(unfinished[:5]))
    # GemDrawingBorrow calls pointer_erase, then its drawing callback, then
    # fence_owner. Both boundaries are observed even when the application
    # uses the renamed App_just_draw implementation. This interval includes
    # callback argument setup and the call into the fence, but no fence body.
    # The outside pointer ensures pointer_erase needs no nested fence here.
    callbacks = []
    helpers = sorted((s for s in spans if s['kind'] in ('pointer_erase', 'fence_owner')),
                     key=lambda s:s['start'])
    helper_starts = [s['start'] for s in helpers]
    borrow_kind='drawing_borrow' if 'drawing_borrow' in entries.values() else 'GemDrawingBorrow'
    for borrow in [s for s in spans if s['kind'] == borrow_kind]:
        children = helpers[bisect_left(helper_starts, borrow['start']):bisect_left(helper_starts, borrow['end'])]
        erase = [s for s in children if s['kind'] == 'pointer_erase']
        fences = sorted((s for s in children if s['kind'] == 'fence_owner'), key=lambda s:s['start'])
        require(len(erase) == 1 and len(fences) == 2 and erase[0]['end'] < fences[0]['start'],
                'Borrow callback boundaries changed')
        callbacks.append(dict(kind='borrow_callback', start=erase[0]['end'], end=fences[0]['start'],
                              derived=True))
    spans.extend(callbacks)
    for span in spans:
        span.update(timeline.measure(span['start'], span['end']))
    rows = []
    viewer = []
    for row, result in enumerate(benchmark['rows']):
        batches = sorted((s for s in spans if s['kind'] == 'batch' and s['argument'] == row),
                         key=lambda s: s['start'])
        require(len(batches) >= 5, 'Missing warmup/calibration/samples')
        samples = []
        for index, batch in enumerate(batches[-3:]):
            inside = [s for s in spans if batch['start'] <= s['start'] < s['end'] <= batch['end']]
            clocks = sorted((s for s in inside if s['kind'] == 'BenchClockRead'), key=lambda s: s['start'])
            require(len(clocks) == 2, 'Sample lacks two clock reads')
            # Exclude both clock calls. Their VBI snapshots bracket this
            # interval, but tick quantization prevents exact equality.
            start, end = clocks[0]['end'], clocks[1]['start']
            selected = [s for s in inside if start <= s['start'] < s['end'] <= end]
            operations = sorted((s for s in selected if s['kind'] == 'BenchDraw'), key=lambda s: s['start'])
            raw = result['samples'][index]
            require(len(operations) == raw['operations'], 'Operation count differs from saved report')
            require(all(s['argument'] == row for s in operations), 'Mixed workload sample')
            if index == 0:
                # Include the group's UPDATE, visibility and event envelope,
                # not just BenchDraw. The first clipped string also shows a
                # partial top row, unlike most subsequent strings.
                last = operations[min(3, len(operations)-1)] if row < 4 else operations[0]
                poll = min((s for s in selected if s['kind'] == 'events' and s['start'] >= last['end']),
                           key=lambda s:s['start'])
                origin, limit = start, poll['end']
                viewer.append(dict(ph='M', name='thread_name', pid=1, tid=row,
                                   args=dict(name=result['name'])))
                viewer.append(dict(ph='X', name='UPDATE group', pid=1, tid=row, ts=0,
                    dur=(limit-origin)/BASE_HZ*1e6,
                    args=dict(operations=4 if row<4 else 1, **timeline.measure(origin, limit))))
                for span in selected:
                    if origin <= span['start'] < span['end'] <= limit:
                        viewer.append(dict(ph='X', name=span['kind'], pid=1, tid=row,
                            ts=(span['start']-origin)/BASE_HZ*1e6,
                            dur=(span['end']-span['start'])/BASE_HZ*1e6,
                            args={key:span[key] for key in ('charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')}))
            measure = timeline.measure(start, end)
            require(abs(measure['elapsed_ms']-raw['ticks']*1000/benchmark['rate']) < 1000/benchmark['rate']+2,
                    'Trace and VBI sample disagree')
            routine_totals = {}
            for kind in sorted({s['kind'] for s in selected}):
                group = [s for s in selected if s['kind'] == kind]
                routine_totals[kind] = dict(calls=len(group), **{
                    metric: sum(s[metric] for s in group) for metric in
                    ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')})
            samples.append(dict(sample=index, start=start, end=end, operations=len(operations),
                **measure, exclusive_cpu_ms=partition(timeline, selected, start, end),
                routines=routine_totals, operation_spans=operations,
                borrow_spans=[s for s in selected if s['kind']==borrow_kind]))
        count = sum(s['operations'] for s in samples)
        categories = sorted({k for s in samples for k in s['exclusive_cpu_ms']})
        kinds = sorted({k for s in samples for k in s['routines']})
        rows.append(dict(name=result['name'], samples=samples, operations=count,
            per_operation={metric: sum(s[metric] for s in samples)/count for metric in
                ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')},
            exclusive_cpu_ms_per_operation={k:sum(s['exclusive_cpu_ms'].get(k, 0) for s in samples)/count
                                           for k in categories},
            routines_per_operation={k:dict(calls=sum(s['routines'].get(k, {}).get('calls', 0) for s in samples)/count,
                charged_cpu_ms=sum(s['routines'].get(k, {}).get('charged_cpu_ms', 0) for s in samples)/count)
                for k in kinds}))
    return dict(task_dp=dp, rows=rows, balanced_calls=len(spans), viewer_events=viewer,
                outside_sample_unfinished_calls=unfinished,
                repeated_breakpoint_entries=profile['repeated_breakpoint_entries'],
                scope='Three measured batches per row; warmup/clear/calibration/report excluded. '
                      'Exclusive CPU includes bus stalls and kernel work; interrupts and other Tasks are separate. '
                      'Inclusive routine totals overlap. Completion polling is software polling time, not exact DMA occupancy.')
