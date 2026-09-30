#!/usr/bin/env python3
"""Read 8 KiB with 2, 4 or 6 application Tasks in the existing eight slots."""
import argparse
import json
from pathlib import Path

from banked_test_memory import read, write
from dos_concurrent_trace import call_marker
from filesystem_formats import SDFS
from measure_read_8k import (BRIDGE, CONFIGURATION, PIN, ROM, configure, data_span,
                             observe, prepare, timing)
from native_program import ROOT, build, compiler, read_build, require, sha256
from os_boundary import emulator
from sio_transaction_trace import read_events
from test_dos_stack import execute, ownership

SOURCE = ROOT/'tests/programs/read_8k_scaling.act'


def symbol(p, name):
    found = [d for d in p['image']['data'] if d['name'].startswith('M_READ8K_'+name.upper()+'_')]
    require(len(found) == 1, 'Ambiguous benchmark field: '+name)
    return found[0]


def field(b, p, name, width=None):
    item = symbol(p, name)
    raw = b.memdump(item['address'], item['size'])
    if width is None:
        return int.from_bytes(raw, 'little')
    return [int.from_bytes(raw[i:i+width], 'little') for i in range(0, len(raw), width)]


def progress(log, p, marks, worker_count):
    events = read_events(log)
    stamps = lambda key:[t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == marks[key]]
    begin, end = stamps('read_begin'), stamps('read_end')
    require(len(begin) == len(end) == 1, 'Incomplete Read interval')
    first, last = begin[0], end[0]
    work = [(t, int(e[9], 16)) for t, e in events if e[0] == 'cpu' and
            int(e[4], 16) == marks['background_work'] and first <= t < last]
    expected = [p['build']['memory']['task_pools'][i+3]['dp'] for i in range(worker_count)]
    require({dp for _, dp in work} == set(expected), 'Missing or unexpected worker context')
    result = []
    for index, dp in enumerate(expected):
        ticks = [t for t, context in work if context == dp]
        quarters = [sum(first+(last-first)*q/4 <= t < first+(last-first)*(q+1)/4 for t in ticks)
                    for q in range(4)]
        require(all(quarters), 'Worker did not progress throughout Read: '+str(index))
        result.append(dict(worker=index, direct_page=dp, entries_during_read=len(ticks),
                           entries_per_quarter=quarters))
    return result


def run(output, media, application_tasks, cpu_trace=True):
    output.mkdir(parents=True, exist_ok=True)
    p = read_build(output.parent/'exec-build')
    require(p['build']['source_sha256'] == sha256(SOURCE), 'Stale scaling reader')
    worker_count = application_tasks-1
    p['labels']['dos_read'] = next(r['address'] for r in p['image']['routines']
                                   if r['name'].startswith('M_DOS_READ_'))
    begin = call_marker(p, 'M_READ8K_READONE_', 'dos_read')
    marks = dict(read_begin=begin, read_end=begin+4,
                 background_work=next(r['address'] for r in p['image']['routines']
                                      if r['name'].startswith('M_READ8K_WORK_')))
    observe(marks if cpu_trace else {})
    media_hash = sha256(media)
    with emulator(BRIDGE, ROM, output, pin=PIN) as b:
        machine = configure(b)
        b.mount(0, str(media))
        def before(b):
            write(b, 0xd1020, bytes([application_tasks]), output)
            b.memload(symbol(p, 'liveAddress')['address'], p['build']['task_storage']['LIVE'].to_bytes(4, 'little'))
            if cpu_trace:
                b.profile_start()
        runtime, _ = execute(b, p, before_run=before, timeout=300, frame_limit=15000)
        if cpu_trace:
            b.profile_stop()
        observed = {name:field(b, p, name) for name in
                    ('received', 'ioError', 'verified', 'checks', 'workerCount', 'workerPriority',
                     'liveDuringRead', 'stopWorkers')}
        require(observed == dict(received=8192, ioError=0, verified=8192, checks=9+2*worker_count,
                                 workerCount=worker_count, workerPriority=0,
                                 liveDuringRead=application_tasks+2, stopWorkers=1), 'Reader/worker checks failed')
        arrays = {name:field(b, p, name, width) for name, width in
                  (('ready', 1), ('rounds', 4), ('values', 2), ('workBefore', 4), ('workAfter', 4))}
        for index in range(5):
            if index < worker_count:
                require(arrays['ready'][index] == 1 and arrays['workAfter'][index] > arrays['workBefore'][index],
                        'Missing worker progress')
                value = 0
                for _ in range(arrays['rounds'][index]):
                    for n in range(256):
                        value = ((value << 1) ^ (value >> 1) ^ n) & 65535
                require(value == arrays['values'][index], 'Worker calculation differs from host oracle')
            else:
                require(all(a[index] == 0 for a in arrays.values()), 'Unused worker ran')
        observed.update(arrays)
        ownership(b, p, p['output'])
        hardware = read(b, p['build']['task_storage']['BASE']+0x800, 128, output)
        require(hardware[0] == hardware[1] == hardware[45] == 0 and
                hardware[12:15] == hardware[16:19] == bytes(3), 'Bus ownership retained')
    require(sha256(media) == media_hash, 'Benchmark media changed')
    result = dict(status='pass', application_tasks=application_tasks, computing_tasks=worker_count,
                  total_public_tasks=application_tasks+2, verified_bytes=8192, machine=machine,
                  configuration=CONFIGURATION, pin=PIN, media_sha256=media_hash,
                  runtime=runtime, observed=observed, build=p['build'], marks=marks,
                  timing=timing(output/'emulator.log', marks, media) if cpu_trace else data_span(output/'emulator.log'),
                  worker_progress=progress(output/'emulator.log', p, marks, worker_count) if cpu_trace else None,
                  harness_sha256=sha256(Path(__file__)), shared_harness_sha256=sha256(ROOT/'tools/measure_read_8k.py'),
                  source_sha256=sha256(SOURCE), reserved_bank_zero_delta=dict(fixed=0, per_task=0))
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/development/read-8k-scaling')
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--tasks', type=int, nargs='+', choices=(2, 4, 6), default=[2, 4, 6],
                        help='Application count, including the reader; two service Tasks are additional')
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--hardware-only', action='store_true')
    args = parser.parse_args()
    require(args.repetitions > 0, 'Repetitions must be positive')
    output = args.output.resolve()
    media = prepare(output, background=True)
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Changed emulator')
    if args.prepare:
        build(compiler(ROOT/'build/actionc'), SOURCE, output/'exec-build', tasks=True, task_capacity=8, optimize=True,
              dos_mounts=[dict(alias='D1', unit=49, sectors=720, sector_bytes=128, profile=4, format=SDFS)],
              image_data=[(0xd1000, b'D1:READ8K.BIN\0'), (0xd1020, b'\2')])
    for count in args.tasks:
        for index in range(args.repetitions):
            target = output/f'apps-{count}-{index+1}{"-hardware" if args.hardware_only else ""}'
            print('Running', target.name, flush=True)
            result = run(target, media, count, cpu_trace=not args.hardware_only)
            print(json.dumps(dict(application_tasks=count, public_slots=count+2,
                                  timing=result['timing'], worker_progress=result['worker_progress'])), flush=True)


if __name__ == '__main__':
    main()
