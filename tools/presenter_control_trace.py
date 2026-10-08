"""Passive native admissions, including the opcode loads already in the guest."""
import re
from bisect import bisect_left
from collections import defaultdict

from aes_latency_trace import routine
from generate_desktop import ABI, layout
from native_program import require


def markers(program):
    points = {}
    offset = layout()['Request']['fields']['operation']
    # SEP #$20; LDY #operation; LDA [pointer],Y. Observe A8 after the read,
    # including the busy-scene checks which can defer without calling Dispatch.
    needle = b'\xe2\x20\xa0'+offset.to_bytes(2, 'little')+b'\xb7\x80'
    for name in ('PUMP', 'DISPATCH'):
        base, raw = routine(program, 'DESKCORE_'+name)
        loads = [m.end() for m in re.finditer(re.escape(needle), raw)]
        require(loads, 'Missing native operation loads in '+name)
        for index, end in enumerate(loads):
            points[f'native_operation_{name.lower()}_{index}'] = base+end
    target = next(r['address'] for r in program['image']['routines']
                  if r['name'].startswith('M_EXECLISTS_ADDTAIL_'))
    base, raw = routine(program, 'DESKCORE_PUMP')
    call = b'\x22'+target.to_bytes(3, 'little')
    require(raw.count(call) == 1, 'Ambiguous native deferral call')
    points['native_deferred'] = base+raw.index(call)
    return points


def admissions(events, definition, spans, worker):
    """Charge each Pump(1), excluding the subsequent input boundary."""
    points = definition['points']
    operations = {pc for name, pc in points.items()
                  if name.startswith('native_operation_')}
    if not operations:
        return []
    interesting = operations | {points['native_deferred']}
    observations = [(t, int(e[4], 16), int(e[5], 16) & 255)
                    for t, e in events if e[0] == 'cpu'
                    and int(e[9], 16) == worker and int(e[4], 16) in interesting]
    ticks = [row[0] for row in observations]
    names = 'REGISTER OPEN SHOW HIDE MOVE RAISE FOCUS REPLACE NEXT_EVENT CANCEL_EVENT CLOSE UNREGISTER SET_TREE UPDATE_WIDGETS READ_WIDGET_STATE'.split()
    names = {ABI['constants'][name]: name for name in names}
    result = []
    for span in spans:
        if span['kind'] != 'deskcore_pump' or not span['return_a'] & 255:
            continue
        require(span['return_a'] & 255 == 1, 'Expected single native admission')
        selected = observations[bisect_left(ticks, span['start']):
                                bisect_left(ticks, span['end'])]
        codes = {a for _, pc, a in selected if pc in operations}
        require(len(codes) <= 1, 'Opcode changed inside native admission')
        code = next(iter(codes), None)
        result.append(dict(span, operation=code,
            operation_name=names.get(code, 'unobserved' if code is None else 'unknown'),
            deferred=any(pc == points['native_deferred'] for _, pc, _ in selected)))
    return result


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['operation_name']].append(row)
    return {name: dict(calls=len(values), deferred=sum(r['deferred'] for r in values),
                      total_cpu_ms=sum(r['charged_cpu_ms'] for r in values),
                      slowest=max(values, key=lambda r: r['charged_cpu_ms']))
            for name, values in sorted(groups.items())}
