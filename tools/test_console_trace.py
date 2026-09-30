#!/usr/bin/env python3
"""Reject corrupted observations using an existing passing console trace."""
import argparse
import json
from pathlib import Path

from console_concurrent_trace import analyze
from native_program import require, sha256
from sio_transaction_trace import read_events


def run(probe, output):
    result = json.loads((probe / 'results.json').read_text())
    require(result['status'] == 'pass', 'Controls require a passing observation')
    # Candidate qualification wraps the unchanged console result with compiler
    # provenance. Preserve the same corruption checks for either producer.
    result = result.get('result', result)
    require(result['status'] == 'pass' and result['case']['speed'] == 0,
            'Controls require a passing FASTEST125 console observation')
    source = probe / 'observed/trace.log'
    events = read_events(source)
    marks = result['marks']
    capture = next(i for i, (_, e) in enumerate(events)
                   if e[0] == 'cpu' and int(e[4], 16) == marks['console_capture'])
    arrival = next(t for t, e in events if e[0] == 'receive')
    read = next(i for i, (t, e) in enumerate(events) if e[0] == 'read' and t >= arrival)
    # 140 base cycles is the physical byte interval. Keep CPU/mask events
    # untouched; move only the first SERIN observation beyond that deadline.
    delayed = list(events)
    _, fields = delayed.pop(read)
    fields = list(fields)
    fields[1] = str(int(arrival) + 141)
    tick = int(fields[1])
    insertion = next(i for i, (t, _) in enumerate(delayed) if t >= tick)
    delayed.insert(insertion, (tick, fields))
    controls = [
        ('missing-key', events[:capture] + events[capture + 1:],
         'lost/duplicate key, read reply or visible echo'),
        ('late-rx', delayed, 'RX physical byte deadline'),
    ]
    cases = []
    for name, edited, expected in controls:
        dest = output / name
        dest.mkdir(parents=True, exist_ok=True)
        trace = dest / 'trace.log'
        trace.write_text(''.join('[SIOTXN] ' + ' '.join(e) + '\n' for _, e in edited))
        checked = analyze(trace, marks, probe / 'observed/volume.atr',
                          result['case']['sector_bytes'], 0,
                          result['case']['counters']['verified'])
        require(checked['verdict'] == 'fail' and expected in checked['violations'],
                'Corrupted trace escaped the expected oracle: ' + name)
        cases.append(dict(name=name, trace_sha256=sha256(trace),
                          expected_violation=expected, violations=checked['violations']))
    return dict(status='pass', source_trace_sha256=sha256(source), cases=cases,
                scope='Deliberately edited traces, not guest execution or new hardware-fault claims.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = run(args.probe, args.output)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Console trace negative controls passed')
