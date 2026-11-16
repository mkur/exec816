"""Decode emitted native call spans, argument values and observed memory reads."""
from collections import defaultdict
from native_program import require


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
            enclosing = next((s for s in reversed(c_active[dp]) if s['name'] == 'ExecAESServiceCall'), None)
            require(enclosing is not None, 'Service capture without caller')
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


