"""Passive UPDATE request, logical ownership and physical access observations.

All markers come from emitted sections/instructions. Native argument observations
use the compiler's frame metadata and actual S; no guessed stack displacement.
Indirect reads expose values already inspected by policy, not extra guest reads.
"""
import json
import re
from collections import defaultdict

from aes_timing_breakdown import image_bytes
from native_program import ROOT, read_build, require
from text_performance_trace import sites
from sio_transaction_trace import BASE_HZ, read_events


DETAILED = (
    'AESLOCKS_REQUEST AESLOCKS_ELIGIBLE AESLOCKS_NATIVEREADY AESLOCKS_ACQUIRE '
    'AESLOCKS_WAKE AESSTATE_REPLY AESMOUSE_LOCKREADY AESCORE_DISPATCH'
).split()
SPANS = (
    'AESHOST_SETTLE AESCORE_SETTLE AESCORE_PUMP AESWINDOWSTATE_SNAPSHOT '
    'AESWINDOWSTATE_SYNC DESKPAINT_PUMP DESKCACHE_PUMP DESKMOVE_PUMP '
    'DESKHOST_CONTROLS DESKHOST_AFTERPAINT CONSOLEDISPLAY_PRESENT '
    'CONSOLEDISPLAY_POLL CONSOLEDISPLAY_DISCARDBATCH DISPLAY_OWNERDROP '
    'DISPLAY_ENTER DISPLAY_LEAVE DISPLAY_BLOCKED CONSOLEBITMAP_PENDING'
).split()


def prepare(out):
    p = read_build(out)
    directory = out/'bitmap-console'
    foreign = json.loads((directory/'c-image.json').read_text())
    decoder = {'__name__': 'admission_decoder'}
    path = ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(path.read_text(), str(path), 'exec'), decoder)
    routines = {}
    pcs = set()
    for name in DETAILED+SPANS:
        matches = [r for r in p['image']['routines'] if r['name'].startswith('M_'+name+'_')]
        require(len(matches) == 1, 'Missing/ambiguous admission routine '+name)
        r = matches[0]
        raw = image_bytes(p, r['address'], r['size'])
        listing = decoder['disassemble']({**p['image'], 'version': 3, 'segments': [
            dict(address=r['address'], bytes=list(raw), executable=True)]})
        ins = {}
        for line in listing.splitlines():
            m = re.fullmatch(r'([0-9A-F]{6})  ((?:[0-9A-F]{2} )+)\s*(.+)', line)
            require(m is not None, 'Unknown native disassembly: '+line)
            ins[int(m[1], 16)] = dict(raw=m[2].strip(), asm=m[3])
        returns = [pc for pc, i in ins.items() if i['asm'] == 'RTL']
        require(returns, 'Missing admission return '+name)
        if name=='AESLOCKS_ELIGIBLE':
            operands={i['asm'] for i in ins.values()}
            require(all('LDY #$%04X'%offset in operands for offset in (0x326,0x32a,0x3e)),
                    'AES Service observer offsets changed')
        routines[name] = dict(entry=r['address'], returns=returns,
                              arguments=r['arguments'], frame=r['fixed_frame'],
                              instructions=ins if name in DETAILED else {})
        pcs.update([r['address'], *returns])
        if name in DETAILED:
            for pc, instruction in ins.items():
                raw=bytes.fromhex(instruction['raw'])
                if raw[0] in (0xa3,0xa7,0xb7,0xaf):
                    pcs.update((pc,pc+len(raw)))
                elif raw[0]==0x22 or (raw[0] in (0x85,0x87,0x97) and raw[1] in (0x80,0x81,0x82)):
                    pcs.add(pc)
    calls = sites(directory/'drawing', foreign, {'ExecAESSubmit': 'rpc', 'PutMsg': 'rpc', 'GetMsg': 'rpc'})
    # Existing checked C call sites supply balanced entry/return spans for all
    # clients. Observe the request pointer/sequence from ExecAESSubmit's stores.
    source = next((directory/'drawing').glob('*aes.lst')).read_text().replace('\r\n', '\n')
    section = next(s for s in source.split('.section ') if '.public ExecAESSubmit\n' in s)
    emitted = {int(m[1], 16): (m[2], m[3].strip()) for m in re.finditer(
        r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+([^\n]+)', section)}
    base = foreign['symbols']['ExecAESSubmit']
    captures = {}
    for label, pattern in [('request_low', '830b'), ('request_high', '830d'),
                           ('sequence_low', '8303'), ('sequence_high', '8305')]:
        matches = [off for off, (code, _) in emitted.items() if code == pattern]
        if label.startswith('sequence_'):
            # First assignment follows sequence=c->sequence+1; later stores
            # reuse the same compiler stack slots for reply checking.
            require('sequence = c->sequence+1;' in section, 'Missing sequence expression')
            matches = matches[:1]
        require(len(matches) == 1, 'Unknown ExecAESSubmit '+label)
        off = matches[0]
        require(image_bytes({'image': foreign}, base+off, 2) == bytes.fromhex(pattern),
                'Unlinked ExecAESSubmit capture')
        captures[base+off] = label
    pcs.update(captures)
    for pc, call in calls.items():
        pcs.update((pc, call['end']))
    result = dict(routines=routines, calls=calls, captures=captures, pcs=sorted(pcs))
    (out/'update-admission-markers.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def decode(events, definition):
    """Return balanced native/C spans and the reads within native policy calls."""
    definitions = definition['routines']
    entries = {r['entry']: name for name, r in definitions.items()}
    returns = {pc: name for name, r in definitions.items() for pc in r['returns']}
    instructions = {int(pc): ins for r in definitions.values() for pc, ins in r['instructions'].items()}
    calls = {int(pc): call for pc, call in definition['calls'].items()}
    captures = {int(pc): name for pc, name in definition['captures'].items()}
    active = defaultdict(list)
    c_active = defaultdict(list)
    previous = {}
    pointer = defaultdict(dict)
    result = []
    c_result = []

    def put(memory, address, value, size):
        for i in range(size):
            memory[address+i] = (value >> (8*i)) & 255

    for tick, e in events:
        if e[0] != 'cpu':
            continue
        pc, a, x, y, sp, dp, p = (int(e[i], 16) for i in (4, 5, 6, 7, 8, 9, 11))
        size = 1 if p & 32 else 2
        if c_active[dp] and pc == c_active[dp][-1]['return_pc'] and sp == c_active[dp][-1]['stack']:
            c_result.append(dict(c_active[dp].pop(), end=tick, value=a))
        if pc in calls:
            call = calls[pc]
            c_active[dp].append(dict(name=call['callee'], dp=dp, start=tick,
                                     return_pc=call['end'], stack=sp, value_in=a))
        if pc in captures:
            enclosing = next((s for s in reversed(c_active[dp]) if s['name'] == 'ExecAESSubmit'), None)
            require(enclosing is not None, 'Submit capture without caller')
            enclosing[captures[pc]] = a
        # A post-load marker sees the returned value even when an interrupt ran
        # in between. Its restored Task registers are the original load result.
        old = previous.get(dp)
        if old and old['next'] == pc:
            if old['kind'] == 'stack':
                for s in active[dp]:
                    put(s['argument_bytes'], old['address'], a, old['size'])
            elif old['kind'] == 'read':
                for s in active[dp]:
                    s['reads'].append(dict(tick=tick, address=old['address'], size=old['size'], value=a & ((1 << (8*old['size']))-1)))
        if (old and old['next']==pc) or pc in instructions:
            previous.pop(dp, None)
        if pc in entries:
            name = entries[pc]
            active[dp].append(dict(name=name, start=tick, stack=sp, dp=dp, reads=[], writes=[], argument_bytes={}))
        if pc in returns:
            name = returns[pc]
            # A trace may start inside a routine; only spans with observed entry
            # participate. A mismatched observed entry is never silently dropped.
            if active[dp] and active[dp][-1]['name'] == name:
                s = active[dp].pop()
                require(s['stack'] == sp, 'Unbalanced native admission return '+name)
                r = definitions[name]
                args = []
                for arg in r['arguments']:
                    address = s['stack']+arg['body_displacement']-r['frame']
                    data = [s['argument_bytes'].get(address+i) for i in range(arg['size'])]
                    args.append(None if None in data else sum(b << (8*i) for i, b in enumerate(data)))
                s.pop('argument_bytes')
                result.append(dict(s, end=tick, value=a, arguments=args))
            elif any(s['name'] == name for s in active[dp]):
                raise RuntimeError('Crossed native admission returns: '+name)
        ins = instructions.get(pc)
        if not ins:
            continue
        raw = bytes.fromhex(ins['raw'])
        if raw[0] == 0x22:
            pointer[dp].clear()
        elif raw[0] == 0x85 and raw[1] in (0x80, 0x81, 0x82):
            put(pointer[dp], raw[1], a, size)
        elif raw[0] == 0xa3:
            previous[dp] = dict(kind='stack', address=sp+raw[1], size=size, next=pc+len(raw))
        elif raw[0] in (0xa7, 0xb7) and raw[1] == 0x80 and all(i in pointer[dp] for i in (0x80, 0x81, 0x82)):
            address = sum(pointer[dp][0x80+i] << (8*i) for i in range(3))
            previous[dp] = dict(kind='read', address=address+(y if raw[0] == 0xb7 else 0), size=size, next=pc+len(raw))
        elif raw[0] in (0x87, 0x97) and raw[1] == 0x80 and all(i in pointer[dp] for i in (0x80, 0x81, 0x82)):
            address = sum(pointer[dp][0x80+i] << (8*i) for i in range(3))
            for s in active[dp]:
                s['writes'].append(dict(tick=tick,address=address+(y if raw[0]==0x97 else 0),
                                        size=size,value=a & ((1 << (8*size))-1)))
        elif raw[0] == 0xaf:
            previous[dp] = dict(kind='read', address=int.from_bytes(raw[1:], 'little'), size=size, next=pc+len(raw))
    # Profiling can end in a sleeping event call or presenter continuation.
    # Completed measurement windows below must contain their complete spans.
    return sorted(result, key=lambda s:s['start']), sorted(c_result, key=lambda s:s['start'])


def read_value(span, address, size):
    """First observed value at each byte; absent reads stay explicitly unknown."""
    data = {}
    for read in span['reads']:
        for i in range(read['size']):
            data.setdefault(read['address']+i, (read['value'] >> (8*i)) & 255)
    values = [data.get(address+i) for i in range(size)]
    return None if None in values else sum(b << (8*i) for i, b in enumerate(values))


def analyze(out, definition, timing_definition, record):
    from bisect import bisect_right
    from aes_timing_breakdown import scheduler_states
    from console_turn_profile import Timeline
    from generate_aes_server import layout
    from native_program import sha256
    from text_performance_trace import timeline
    trace = out/'emulator.log'
    require(trace.stat().st_size < 256*1024*1024, 'Admission trace exceeds cap')
    events = read_events(trace, kinds={'cpu'})
    relocated = record['app']['base']-timing_definition['reference']
    definition = {**definition, 'calls': {**definition['calls'], **{
        int(pc)+relocated: {**v, 'end': v['end']+relocated}
        for pc, v in timing_definition['local'].items()}}}
    native, calls = decode(events, definition)
    (out/'update-admission-spans.json').write_text(json.dumps(dict(native=native, calls=calls))+'\n')
    segments = timeline(events, timing_definition['points'])
    segment_ticks = [s[0] for s in segments]
    states, selections = scheduler_states(events, timing_definition['scheduler'], timing_definition['points']['selected'])
    clocks = {dp: Timeline(segments, dp) for dp in states}
    fields = layout()['Request']['fields']
    factor = 1000/BASE_HZ
    grouped = defaultdict(list)
    for s in native:
        grouped[s['name']].append(s)
    presenter = {s['dp'] for s in grouped['AESHOST_SETTLE']}
    require(len(presenter) == 1, 'Missing unique presenter')
    presenter = presenter.pop()

    def account(dp, begin, end):
        total = clocks[dp].measure(begin, end)
        changes = states[dp]; ticks = [t for t, _ in changes]
        waiting = runnable = 0
        lo_index=max(0,bisect_right(segment_ticks,begin)-1)
        hi_index=bisect_right(segment_ticks,end)
        for a, b, owner, _ in segments[lo_index:hi_index]:
            lo, hi = max(a, begin), min(b, end)
            if hi <= lo or owner == dp:
                continue
            i = bisect_right(ticks, lo)-1
            require(i >= 0, 'Missing admission Task state')
            if changes[i][1] == 'blocked': waiting += hi-lo
            else: runnable += hi-lo
        total.update(blocked_off_cpu_ms=waiting*factor, runnable_off_cpu_ms=runnable*factor)
        require(abs(total['off_cpu_ms']-(waiting+runnable)*factor) < 1e-7, 'Admission time does not reconcile')
        return total

    def inside(name, begin, end):
        return [s for s in grouped[name] if begin <= s['start'] < s['end'] <= end]

    rows = []
    for call in calls:
        if call['name'] != 'ExecAESSubmit' or call['value_in'] != 107:
            continue
        require(all(k in call for k in ('request_low','request_high','sequence_low','sequence_high')), 'Missing request identity')
        address = call['request_low'] | call['request_high'] << 16
        sequence = call['sequence_low'] | call['sequence_high'] << 16
        requests = [s for s in inside('AESLOCKS_REQUEST', call['start'], call['end']) if s['arguments'][2] == address]
        require(len(requests) == 1, 'Missing unique lock dispatch')
        request = requests[0]
        service, client, _ = request['arguments']
        code = read_value(request, address+fields['intin'], 2)
        require(code is not None, 'Missing UPDATE argument')
        replies = [s for s in grouped['AESSTATE_REPLY'] if call['start'] <= s['start'] < call['end'] and s['arguments'][0] == address]
        require(len(replies) == 1, 'Missing unique UPDATE reply')
        reply = replies[0]
        dispatches=[s for s in grouped['AESCORE_DISPATCH'] if call['start']<=s['start']<=request['start'] and s['arguments'][1]==address]
        require(len(dispatches)==1,'Missing dequeued UPDATE dispatch')
        pumps=[s for s in grouped['AESCORE_PUMP'] if s['start']<=dispatches[0]['start']<s['end']]
        require(len(pumps)==1,'Missing intake boundary')
        submits = [s for s in calls if s['name'] == 'PutMsg' and s['dp'] == call['dp'] and call['start'] <= s['start'] < s['end'] <= call['end']]
        require(len(submits) == 1, 'Missing request publication')
        submit = submits[0]
        acquired = [s for s in inside('AESLOCKS_ACQUIRE', call['start'], reply['start']) if s['arguments'][1] == client]
        tests = [s for s in inside('AESLOCKS_ELIGIBLE', call['start'], reply['start']) if s['arguments'][1] == client]
        row = dict(request=address, sequence=sequence, client_address=client, caller_dp=call['dp'],
                   code=code, begin=call['start'], submitted=submit['start'], submit_return=submit['end'],
                   dequeue_observed=dispatches[0]['start'], dispatch=request['start'],
                   dequeue_bounds=[pumps[0]['start'],dispatches[0]['start']],
                   request_return=request['end'], queued=request['value']==8,
                   reply=reply['start'], reply_return=reply['end'], returned=call['end'],
                   caller=account(call['dp'],call['start'],call['end']),
                   presenter=account(presenter,call['start'],call['end']))
        outer = [s for s in calls if s['name']=='wind_update' and s['dp']==call['dp'] and s['start']<=call['start']<call['end']<=s['end']]
        if outer:
            require(len(outer)==1, 'Nested wind_update observation')
            row.update(wind_begin=outer[0]['start'], wind_return=outer[0]['end'])
        row['ownership_stores']=list({w['tick']:w for s in [request,*acquired] for w in s['writes']
                                 if service+0x326<=w['address']<service+0x332}.values())
        released=[w['tick'] for w in request['writes'] if service+0x326<=w['address']<service+0x32a and w['value']==0]
        if code==0 and released:
            row['release_store']=max(released)
        row['ready'] = next((t for t,state in states[call['dp']] if reply['start']<=t<=call['end'] and state=='ready'),None)
        row['selected'] = next((t for t in selections[call['dp']] if reply['start']<=t<=call['end']),None)
        row['eligibility'] = []
        for test in tests:
            ready = inside('AESLOCKS_NATIVEREADY',test['start'],test['end'])
            mouse = inside('AESMOUSE_LOCKREADY',test['start'],test['end'])
            # Internal Service offsets are checked against the emitted field
            # operands by the observed addresses. Unknown/short-circuited fields
            # remain null; values do not imply they held throughout a gap.
            values = dict(update_owner=read_value(test,service+0x326,4),
                          mouse_owner=read_value(test,service+0x32a,4),
                          window_pending=read_value(test,service+0x3e,1),
                          client=read_value(test,client,4),
                          gesture_ready=mouse[0]['value'] if mouse else None)
            if ready:
                native_ready=ready[0]
                observed=native_ready['reads']
                require(len(observed)==4 and [r['size'] for r in observed]==[2,2,1,1]
                        and observed[1]['address']==observed[0]['address']+2,
                        'Unknown NativeReady field read sequence')
                # Read addresses/values remain in the companion spans, allowing
                # scene/batch/outline observations to be checked against build data.
                values.update(native_ready=native_ready['value'],native_reads=native_ready['reads'],
                    scene_token=observed[0]['value'] | (observed[1]['value']<<16),
                    batch_phase=observed[2]['value'],outline_visible=observed[3]['value'],
                    display_blocked=[s['value'] for s in inside('DISPLAY_BLOCKED',native_ready['start'],native_ready['end'])],
                    console_pending=[s['value'] for s in inside('CONSOLEBITMAP_PENDING',native_ready['start'],native_ready['end'])])
            row['eligibility'].append(dict(at=test['start'],observed=test['end'],eligible=bool(test['value']),**values))
        cuts=[('submit',call['start']),('intake',submit['start']),('admitted',request['start'])]
        if code & 1:
            require(len(acquired)==1 and tests and tests[-1]['value'], 'Missing successful UPDATE acquisition')
            acquire=acquired[0]
            snapshots=inside('AESWINDOWSTATE_SNAPSHOT',acquire['start'],acquire['end'])
            row.update(acquire=acquire['start'],acquire_return=acquire['end'],
                       snapshot=[dict(begin=s['start'],end=s['end']) for s in snapshots])
            failed=[s for s in tests if not s['value']]
            row['eligibility_transition_bounds']=dict(
                last_observed_ineligible=failed[-1]['end'] if failed else None,
                observed_eligible=tests[-1]['end'],
                eligible_test_to_acquire_ms=(acquire['start']-tests[-1]['end'])*factor)
            cuts += [('grant',acquire['start']),('reply_work',acquire['end'])]
            physical=next((s for s in grouped['DISPLAY_ENTER'] if s['dp']==call['dp'] and s['start']>=call['end']),None)
            if physical:
                row['first_physical'] = dict(begin=physical['start'],admitted=physical['end'],
                    **account(call['dp'],physical['start'],physical['end']))
                row['owner_drops']=[dict(begin=s['start'],end=s['end']) for s in grouped['DISPLAY_OWNERDROP']
                                    if call['start']<=s['start']<=physical['end']]
        cuts += [('resume',reply['start']),('returned',call['end'])]
        row['phases_ms'] = {name:(end-begin)*factor for (name,begin),(_,end) in zip(cuts,cuts[1:])}
        require(abs(sum(row['phases_ms'].values())-row['caller']['elapsed_ms'])<1e-7,'Admission phases do not reconcile')
        row['presenter_work'] = []
        for name in SPANS:
            for s in grouped[name]:
                lo,hi=max(s['start'],call['start']),min(s['end'],call['end'])
                if hi>lo:
                    row['presenter_work'].append(dict(name=name,begin=lo,end=hi,**clocks[presenter].measure(lo,hi)))
        rows.append(row)
    identities={r['client_address']:e['client'] for r in rows for e in r['eligibility'] if e['client'] is not None}
    holds=[]
    for row in rows:
        row['client_id']=identities.get(row['client_address'])
        if row['code']!=1:
            continue
        end=next((r for r in rows if r['client_address']==row['client_address'] and r['begin']>row['begin'] and 'release_store' in r),None)
        if end:
            holds.append(dict(client=row['client_id'],caller_dp=row['caller_dp'],
                begin_sequence=row['sequence'],end_sequence=end['sequence'],
                acquired=row['acquire'],released=end['release_store'],
                logical_hold_ms=(end['release_store']-row['acquire'])*factor,
                application_to_end_call_ms=(end['begin']-row['returned'])*factor,
                end_call_ms=end['caller']['elapsed_ms']))
    require(rows and any(r['queued'] for r in rows), 'No queued UPDATE samples')
    viewers={s['dp'] for s in calls if s['name']=='TextRow'}
    require(len(viewers)==1, 'Missing relocated viewer Task')
    viewer=viewers.pop()
    samples=[]
    for sample in record['samples']:
        selected=[r for r in rows if r['caller_dp']==viewer and sample['start']<=r['begin']<r['returned']<=sample['complete']]
        require(selected and all('wind_return' in r for r in selected),'Incomplete measured viewer UPDATE')
        samples.append(dict(operation=sample['operation'],index=sample['index'],requests=selected))
    result=dict(scope=__doc__,presenter_dp=presenter,samples=samples,requests=rows,logical_holds=holds,
                trace_bytes=trace.stat().st_size,trace_sha256=sha256(trace),
                eligibility_scope='Values at policy observations; transitions between tests are bounded, not interpolated. Presenter work spans may overlap and must not be added.')
    (out/'update-admission-breakdown.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
