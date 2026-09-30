"""Bounded passive observations of the existing console benchmark."""
import os
import statistics
from contextlib import contextmanager

from native_program import ROOT, require
from sio_transaction_trace import BASE_HZ, read_events


def markers(program):
    image = program['image']
    decoder = {'__name__': 'console_decoder'}
    path = ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(path.read_text(), str(path), 'exec'), decoder)
    result = {}
    for module, routine, key in (
            ('CONSOLECORE', 'EDITQUANTUM', 'edit'),
            ('CONSOLEDISPLAY', 'PRESENT' if any(r['name'].startswith('M_CONSOLEDISPLAY_PRESENT_')
                                             for r in image['routines']) else 'QUANTUM', 'display'),
            ('CONSOLEDRIVER', 'WRITEQUANTUM', 'write'),
            ('CONSOLEWINDOWS', 'TAKE', 'worker_turn'),
            ('CONSOLEDISPLAY', 'CELLS', 'translated_cell')):
        matches = [r for r in image['routines']
                   if r['name'].startswith(f'M_{module}_{routine}_')]
        require(len(matches) == 1, 'Missing console observation: '+key)
        r = matches[0]
        segments = []
        for s in image['segments']:
            lo = max(s['address'], r['address'])
            hi = min(s['address']+len(s['bytes']), r['address']+r['size'])
            if lo < hi:
                segments.append(dict(address=lo, executable=True,
                                     bytes=s['bytes'][lo-s['address']:hi-s['address']]))
        listing = decoder['disassemble']({**image, 'version': 3, 'segments': segments})
        if key == 'translated_cell':
            if 'console_span_store' in program['labels']:
                entry = program['labels']['console_span_store']
            else:
                # The first indirect store is the glyph store; remaining stores
                # commit the dirty interval after the nested loops have ended.
                stores = [line for line in listing.splitlines() if 'STA [$' in line]
                require(len(stores) == 4, 'Changed legacy Cells store shape')
                entry = int(stores[0][:6], 16)
            result[key] = dict(entry=entry, returns=[])
            continue
        if key == 'worker_turn':
            result[key] = dict(entry=r['address'], returns=[])
            continue
        result[key] = dict(entry=r['address'], returns=[int(line[:6], 16)
                           for line in listing.splitlines() if line.endswith(' RTL')])
    return result


@contextmanager
def observation(program, enabled):
    marks = markers(program) if enabled else {}
    keys = ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE')
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        if enabled:
            pcs = {pc for item in marks.values() for pc in [item['entry'], *item['returns']]}
            os.environ['EXEC816_LATENCY_TRACE'] = '1'
            os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in sorted(pcs))
        yield marks
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def summarize(path, marks):
    active = {}
    durations = {key: [] for key in marks}
    counts = {key: 0 for key in marks}
    for tick, event in read_events(path):
        if event[0] != 'cpu':
            continue
        pc = int(event[4], 16)
        for key, item in marks.items():
            if pc == item['entry']:
                counts[key] += 1
                if not item['returns']:
                    continue
                require(key not in active, 'Overlapping console observation: '+key)
                active[key] = tick
            elif pc in item['returns']:
                require(key in active, 'Unmatched console return: '+key)
                durations[key].append((tick-active.pop(key)+6/8)/BASE_HZ*1000)
    require(not active, 'Incomplete console observations')
    return {key: dict(calls=counts[key], **(dict(median_ms=statistics.median(values),
                      max_ms=max(values)) if values else {}))
            for key, values in durations.items()}
