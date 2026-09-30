#!/usr/bin/env python3
"""Compare one cold 8192-byte Read under Exec816 and original SpartaDOS X."""
import argparse
import json
import os
from pathlib import Path
import shutil

from banked_test_memory import read, write
from dos_concurrent_trace import call_marker
from filesystem_formats import SDFS
from make_sdfs_fixtures import CAR_SHA, CAR_URL, Media
from measure_loading_breakdown import packets, partition_packet
from measure_spartados import prepare as prepare_sdx, stop
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from sdfs_reference import make, verify
from sio_transaction_trace import BASE_HZ, read_events
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
CONFIGURATION = {**PIN['configuration'], 'diskemu': 'generic56k'}
BRIDGE = ROOT/'build/shell-paced-bridge'
ROM = ROOT/'build/firmware/altirraos-816.rom'
PAYLOAD = bytes((i & 255) ^ (i >> 8) ^ 0x81 for i in range(8192))


def prepare(output, emit=False, background=False):
    files = output/'files'
    files.mkdir(parents=True, exist_ok=True)
    (files/'READ8K.BIN').write_bytes(PAYLOAD)
    media = output/'read8k.atr'
    if not media.exists():
        if background:
            # Preserve the exact original disk layout and rotational profile.
            shutil.copyfile(ROOT/'build/development/read-8k/read8k.atr', media)
        else:
            make(media, files)
    verify(media, {'READ8K.BIN': PAYLOAD}, output/'extracted')
    if emit:
        source = 'read_8k_background.act' if background else 'read_8k.act'
        build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs'/source, output/'exec-build',
              tasks=True, task_capacity=8, optimize=True,
              dos_mounts=[dict(alias='D1', unit=49, sectors=720, sector_bytes=128, profile=4, format=SDFS)],
              image_data=[(0xd1000, b'D1:READ8K.BIN\0')] + ([(0xd1020, b'\1')] if background else []))
    return media


def observe(marks):
    for name in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE'):
        os.environ.pop(name, None)
    os.environ['EXEC816_LATENCY_TRACE'] = '1'
    if marks:
        os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{v:x}' for v in marks.values())


def configure(b):
    for key, value in CONFIGURATION.items():
        b.config(key, str(value).lower() if isinstance(value, bool) else value)
    return verify_machine(b, ROM, PIN)


def timing(log, marks, media_path):
    events = read_events(log)
    stamps = [[t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == marks[name]]
              for name in ('read_begin', 'read_end')]
    require(all(len(s) == 1 for s in stamps), 'Expected exactly one complete Read call')
    begin, end = [s[0] for s in stamps]
    require(begin < end, 'Reversed Read markers')
    selected = [p for p in packets(events) if begin <= p['begin'] < end]
    rows = [partition_packet(p) for p in selected]
    require(rows and rows[-1]['end'] <= end, 'Read returned before last checksum')
    media = Media(media_path.read_bytes())
    entry = media.row(media.entry(media.word(25), 'READ8K.BIN'))
    require(int.from_bytes(entry[3:6], 'little') == len(PAYLOAD), 'Unexpected on-disk length')
    maps, sectors = media.chain(int.from_bytes(entry[1:3], 'little'))
    sectors = sectors[:64]
    data_rows = [r for r in rows if r['sector'] in sectors]
    require([r['sector'] for r in data_rows] == sectors, 'Missing, repeated or reordered file data')
    require(all(r['sector'] in maps+sectors for r in rows), 'Unexpected I/O inside Read')
    for packet, row in zip(selected, rows):
        at = media.at(row['sector'])
        require(bytes(v for _, v, _ in packet['rx'][2:-1]) == media.raw[at:at+media.size],
                'Wire bytes differ from common media')
    gaps = [b['begin']-a['end'] for a, b in zip(rows, rows[1:])]
    require(all(g >= 0 for g in gaps), 'Overlapping transactions')
    parts = {k:sum(r['parts_ms'][k] for r in rows)/1000 for k in rows[0]['parts_ms']}
    parts['outside_transactions'] = ((rows[0]['begin']-begin) + sum(gaps) + (end-rows[-1]['end']))/BASE_HZ
    elapsed = (end-begin)/BASE_HZ
    require(abs(sum(parts.values())-elapsed) < 1e-8, 'Incomplete time accounting')
    worker = [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == marks.get('background_work')
              and begin <= t < end]
    if 'background_work' in marks:
        require(worker, 'No CPU worker progress during Read')
    return dict(seconds=elapsed, bytes_per_second=len(PAYLOAD)/elapsed,
                data_sector_count=len(data_rows), map_sectors=[r['sector'] for r in rows if r['sector'] in maps],
                sector_sequence=[r['sector'] for r in rows], parts_seconds=parts,
                between_transactions_seconds=sum(gaps)/BASE_HZ,
                mean_between_transactions_ms=sum(gaps)/len(gaps)/BASE_HZ*1000,
                data_sector_span_seconds=(data_rows[-1]['end']-data_rows[0]['begin'])/BASE_HZ,
                tx_cycles_per_bit=30, rx_cycles_per_bit=31,
                background_work_entries=len(worker),
                transactions_with_background_work=sum(any(r['begin'] <= t < r['end'] for t in worker) for r in rows),
                boundary='Read call instruction through return; elapsed guest time; Open, Close, allocation, '
                         'program loading and byte verification excluded.',
                log_sha256=sha256(log))


def data_span(log):
    """Hardware-only control: find the unique first data block by its bytes.

    This discards startup-volume traffic without relying on debugger log text.
    The common media places its data at 8..69,71,72 and its second map at 70.
    """
    events = read_events(log)
    require(not any(e[0] == 'cpu' for _, e in events), 'CPU observation enabled in hardware control')
    reads = [p for p in packets(events)
             if len(p['tx']) == 5 and [v for _, v, _ in p['tx'][:2]] == [49, 82]]
    starts = [i for i, p in enumerate(reads) if p['tx'][2][1] == 8 and p['tx'][3][1] == 0
              and bytes(v for _, v, _ in p['rx'][2:-1]) == PAYLOAD[:128]]
    require(len(starts) == 1, 'Missing/ambiguous initial payload block')
    selected = reads[starts[0]:starts[0]+65]
    rows = [partition_packet(p) for p in selected]
    require([r['sector'] for r in rows] == list(range(8, 73)), 'Changed common data/map layout')
    contents = b''.join(bytes(v for _, v, _ in p['rx'][2:-1])
                        for p, r in zip(selected, rows) if r['sector'] != 70)
    require(contents == PAYLOAD, 'Hardware-only wire payload differs')
    return dict(data_sector_span_seconds=(rows[-1]['end']-rows[0]['begin'])/BASE_HZ,
                cpu_observation=False, verified_wire_bytes=len(contents), log_sha256=sha256(log))


def run_sdx(output, media, cpu_trace=True):
    labels = prepare_sdx(output, ROOT/'tests/programs/spartados_read_8k.s')
    marks = {name:labels[name] for name in ('read_begin', 'read_end')}
    observe(marks if cpu_trace else {})
    car = ROOT/'build/development/spartados-s1/SDX450_maxflash1.car'
    require(sha256(car) == CAR_SHA, 'Changed original SDX cartridge')
    with emulator(BRIDGE, ROM, output, pin=PIN) as b:
        machine = configure(b)
        b.mount(0, str(output/'startup.atr'))
        b.bp_set(labels['start']); b.bp_set(labels['failed'])
        b.boot(str(car))
        stop(b, labels['start'], labels['failed'])
        b.mount(0, str(media))
        b.bp_clear_all(); b.bp_set(labels['done']); b.bp_set(labels['failed'])
        if cpu_trace:
            b.profile_start()
        stop(b, labels['done'], labels['failed'])
        if cpu_trace:
            b.profile_stop()
        require(b.peek(labels['result'])[0] == 1, 'Missing SDX completion')
        require(b.memdump(labels['buffer'], len(PAYLOAD)) == PAYLOAD, 'SDX returned different bytes')
    return dict(system='SpartaDOS X 4.50', machine=machine, marks=marks,
                verified_bytes=len(PAYLOAD), cartridge_sha256=CAR_SHA, cartridge_url=CAR_URL,
                probe_sha256=sha256(output/'probe.bin'), startup_sha256=sha256(output/'startup.atr'))


def run_exec(output, media, cpu_trace=True, background=None):
    output.mkdir(parents=True, exist_ok=True)
    p = read_build(output.parent/'exec-build')
    source = 'read_8k_background.act' if background else 'read_8k.act'
    require(p['build']['source_sha256'] == sha256(ROOT/'tests/programs'/source), 'Stale benchmark source')
    routine = next(r for r in p['image']['routines'] if r['name'].startswith('M_DOS_READ_'))
    p['labels']['dos_read'] = routine['address']
    begin = call_marker(p, 'M_READ8K_READONE_', 'dos_read')
    marks = dict(read_begin=begin, read_end=begin+4)
    if background == 'running':
        marks['background_work'] = next(r['address'] for r in p['image']['routines']
                                        if r['name'].startswith('M_READ8K_WORK_'))
    observe(marks if cpu_trace else {})
    def before(b):
        if background:
            write(b, 0xd1020, bytes([background == 'running']), output)
        if cpu_trace:
            b.profile_start()
    with emulator(BRIDGE, ROM, output, pin=PIN) as b:
        machine = configure(b)
        b.mount(0, str(media))
        runtime, _ = execute(b, p, before_run=before, timeout=300, frame_limit=15000)
        if cpu_trace:
            b.profile_stop()
        observed = {name:int.from_bytes(bytes(data(b, p['image'], name)), 'little')
                    for name in ('received', 'ioError', 'verified', 'checks')}
        require(observed == dict(received=8192, ioError=0, verified=8192, checks=9 if background else 7),
                'Exec read/cleanup failed')
        if background:
            observed.update({name:int.from_bytes(bytes(data(b, p['image'], name)), 'little')
                             for name in ('workerEnabled', 'workerPriority', 'workerReady', 'stopWorker',
                                          'workRounds', 'workValue', 'workBeforeRead', 'workAfterRead')})
            require(observed['workerEnabled'] == int(background == 'running') and
                    observed['workerReady'] == observed['stopWorker'] == 1, 'Worker setup/shutdown failed')
            require((observed['workAfterRead'] > observed['workBeforeRead']) if background == 'running' else
                    observed['workRounds'] == observed['workBeforeRead'] == observed['workAfterRead'] == 0,
                    'Incorrect background progress')
        ownership(b, p, p['output'])
        hardware = read(b, p['build']['task_storage']['BASE']+0x800, 128, output)
        require(hardware[0] == hardware[1] == hardware[45] == 0 and
                hardware[12:15] == hardware[16:19] == bytes(3), 'Bus ownership retained')
    return dict(system='Exec816 SDFS', machine=machine, marks=marks, observed=observed,
                verified_bytes=len(PAYLOAD), runtime=runtime, build=p['build'], background=background)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--prepare', action='store_true', help='Compile the dedicated optimized Exec reader')
    parser.add_argument('--system', choices=('both', 'exec', 'sdx'), default='both')
    parser.add_argument('--repetitions', type=int, default=2, help='Independent cold boots per system')
    parser.add_argument('--hardware-only', action='store_true', help='Replay with instruction observation disabled')
    parser.add_argument('--background', choices=('running', 'stopped'),
                        help='Exec CPU worker; both modes use the same dedicated image')
    args = parser.parse_args()
    require(args.repetitions > 0, 'Repetitions must be positive')
    require(not args.background or args.system == 'exec', 'Use --system exec with --background')
    output = (args.output or ROOT/('build/development/read-8k-background' if args.background else
                                  'build/development/read-8k')).resolve()
    media = prepare(output, args.prepare, bool(args.background))
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Changed emulator')
    media_hash = sha256(media)
    for name, runner in (('sdx', run_sdx), ('exec', run_exec)):
        if args.system not in ('both', name):
            continue
        for index in range(args.repetitions):
            suffix = f'-{args.background}' if args.background else ''
            target = output/f'{name}-{index+1}{suffix}{"-hardware" if args.hardware_only else ""}'
            print('Running', target.name, flush=True)
            result = runner(target, media, cpu_trace=not args.hardware_only,
                            **({'background':args.background} if name == 'exec' else {}))
            require(sha256(media) == media_hash, 'Benchmark media modified')
            result.update(status='pass', pin=PIN, configuration=CONFIGURATION,
                          media_sha256=media_hash, payload_sha256=sha256(output/'files/READ8K.BIN'),
                          timing=(data_span(target/'emulator.log') if args.hardware_only else
                                  timing(target/'emulator.log', result['marks'], media)),
                          harness_sha256=sha256(Path(__file__)),
                          source_sha256=sha256(ROOT/'tests/programs'/('read_8k_background.act' if args.background else
                                               'read_8k.act' if name == 'exec' else 'spartados_read_8k.s')),
                          reserved_bank_zero_delta=dict(fixed=0, per_task=0))
            (target/'results.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(dict(system=name, sample=index+1, **result['timing'])), flush=True)


if __name__ == '__main__':
    main()
