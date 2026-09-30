#!/usr/bin/env python3
"""Time one 70,003-byte DOS.Read on the existing MyDOS fixture, without contention."""
import argparse
import json
import os
import shutil
from pathlib import Path

from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute, ownership
from test_cooperative import data
from banked_test_memory import read
from dos_concurrent_trace import call_marker
from sio_transaction_trace import BASE_HZ, checksum, read_events, stats


def marks_for(p):
    marks = {name: p['labels'][name] for name in ('sio_start', 'signal_post', 'sio_retire')}
    for name, caller, callee in (
        ('read', 'M_DOSLARGEREAD_READONE_', 'M_DOS_READ_'),
        ('copy', 'M_MYDOSFILE_CONSUME_', 'M_MYDOSFILE_COPY_'),
        ('sector', 'M_BLOCKWIRE_TRANSFER_', 'io_do_io'),
        ('recovery', 'M_SIODRIVER_RUNREQUEST_', 'tasks_sleep'),
    ):
        if callee.startswith('M_'):
            matches = [r['address'] for r in p['image']['routines'] if r['name'].startswith(callee)]
            require(len(matches) == 1, 'Ambiguous routine ' + callee)
            p['labels'][callee] = matches[0]
        marks[name + '_begin'] = call_marker(p, caller, callee)
        marks[name + '_end'] = call_marker(p, caller, callee, after=True)
    return marks


def timing(path, marks, profile=1):
    events = read_events(path)
    marker = lambda name: [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == marks[name]]
    begin, end = marker('read_begin'), marker('read_end')
    require(len(begin) == len(end) == 1 and begin[0] < end[0], 'Expected exactly one Read')
    first, last = begin[0], end[0]
    times = lambda name: [t for t in marker(name) if first <= t <= last]
    submit, start, post, retire, done = [times(n) for n in (
        'sector_begin', 'sio_start', 'signal_post', 'sio_retire', 'sector_end')]
    require(len(submit) == len(start) == len(post) == len(retire) == len(done) == 277,
            'Expected 277 sectors, each read once')
    require(all(a < b < c < d < e for a, b, c, d, e in zip(submit, start, post, retire, done)),
            'Unexpected sector timeline')
    require(all(a < b for a, b in zip(done, submit[1:])), 'Overlapping sector calls')
    elapsed = last - first
    # Disjoint intervals cover the entire Read, including its first/last overhead.
    parts = dict(
        submit_to_start=[b-a for a, b in zip(submit, start)],
        start_to_terminal_post=[b-a for a, b in zip(start, post)],
        terminal_post_to_sector_return=[b-a for a, b in zip(post, done)],
        between_sector_calls=[b-a for a, b in zip(done, submit[1:])],
        read_edges=[submit[0]-first, last-done[-1]],
    )
    require(abs(sum(map(sum, parts.values())) - elapsed) < 0.01, 'Incomplete time accounting')
    frames, frame = [], None
    selected = [(t, e) for t, e in events if first <= t <= last]
    for t, e in selected:
        if e[0] == 'command':
            if int(e[2]):
                require(frame is None, 'Overlapping command frames')
                frame = []
            else:
                require(frame is not None, 'Unpaired command release')
                frames.append(frame)
                frame = None
        elif e[0] == 'ready':
            require(frame is not None, 'TX outside command frame')
            frame.append(int(e[2]))
    require(frame is None and len(frames) == 277, 'Incomplete wire command trace')
    require(all(len(f) == 5 and f[:2] == [49, 0x52] and f[-1] == checksum(f[:-1]) for f in frames),
            'Unexpected wire command')
    sectors = [f[2] + (f[3] << 8) for f in frames]
    require(sectors == list(range(18, 26)) + list(range(1152, 1421)), 'Unexpected file sector chain')
    rx_events = [(t, e) for t, e in selected if e[0] == 'rxstart']
    rx = [e for t, e in rx_events]
    tx = [e for t, e in selected if e[0] == 'ready']
    require(len(rx) == 277*259 and len(tx) == 277*5, 'Unexpected serial byte count')
    tx_cycles,rx_cycles=(30,31) if profile==4 else (14,14)
    require(all(int(e[3]) == rx_cycles for e in rx) and all(int(e[3]) == tx_cycles for e in tx), 'Unexpected target baud')
    drive_wait = []
    for index in range(277):
        ack, complete = rx_events[index*259:index*259+2]
        require(int(ack[1][2]) == 0x41 and int(complete[1][2]) == 0x43, 'Missing ACK/Complete')
        drive_wait.append(complete[0] - ack[0] - int(ack[1][3])*10)
    copy_begin, copy_end = times('copy_begin'), times('copy_end')
    require(len(copy_begin) == len(copy_end) == 277, 'Incomplete copy trace')
    recovery_begin, recovery_end = marker('recovery_begin'), marker('recovery_end')
    require(len(recovery_begin) == len(recovery_end), 'Incomplete recovery trace')
    recovery = [(a, b) for a, b in zip(recovery_begin, recovery_end) if a < last and b > first]
    # Recovery overlaps filesystem work. Only its intersection with the next
    # submitted sector's queue wait is directly exposed in this workload.
    exposed = sum(max(0, min(b, d)-max(a, c)) for a, b in recovery for c, d in zip(submit, start))
    return dict(
        elapsed_seconds=elapsed/BASE_HZ, file_bytes=70003, file_bytes_per_second=70003*BASE_HZ/elapsed,
        sectors=len(sectors), sector_payload_bytes=277*256, rx_bytes=len(rx), tx_bytes=len(tx),
        tx_cycles_per_bit=tx_cycles, rx_cycles_per_bit=rx_cycles,
        serial_byte_clock_seconds=sum(int(e[3])*10 for e in rx+tx)/BASE_HZ,
        ack_end_to_complete_begin=dict(seconds=sum(drive_wait)/BASE_HZ, **stats(drive_wait)),
        breakdown={k: dict(seconds=sum(v)/BASE_HZ, percent=100*sum(v)/elapsed, **stats(v)) for k, v in parts.items()},
        copy_wall_seconds=sum(b-a for a, b in zip(copy_begin, copy_end))/BASE_HZ,
        copy=stats([b-a for a, b in zip(copy_begin, copy_end)]),
        recovery_sleep=stats([b-a for a, b in recovery]),
        recovery_overlap_with_queue_seconds=exposed/BASE_HZ,
        terminal_post_to_retire=stats([b-a for a, b in zip(post, retire)]),
        boundary='JSL DOS.Read entry to return; guest time; excludes Open, verification and cleanup. Copy/recovery are overlapping diagnostics, not additional breakdown terms.',
    )


def run(out, mode, accurate_disk=True, profile=1, compiler_dir=ROOT/'build/actionc', paced=False):
    require(profile in (1,4),'Unsupported large-read profile')
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text()) if paced else PIN
    diskemu='generic56k' if profile==4 else 'fastest'
    out.mkdir(parents=True, exist_ok=True)
    p = build(compiler(compiler_dir), ROOT/'tests/programs/dos_large_read.act', out,
              tasks=True, task_capacity=8, optimize=mode == 'opt',
              dos_mounts=[dict(alias='D1', unit=49, sectors=2000, sector_bytes=256, profile=profile)],
              image_data=[(0xd1000, b'D1:LARGE.BIN\0')])
    marks = marks_for(p)
    for key in ('EXEC816_LATENCY_TRACE', 'EXEC816_MASK_TRACE', 'EXEC816_LATENCY_PCS'):
        os.environ.pop(key, None)
    os.environ.update(EXEC816_LATENCY_TRACE='1', EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    binary = ROOT/('build/shell-paced-bridge' if paced else 'build/altirra-sio-multi-observer')
    require(sha256(binary/'AltirraBridgeServer') == pin['observer']['binary_sha256'], 'Unpinned observer')
    media = out/'volume.atr'
    shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-256.atr', media)
    media_hash = sha256(media)
    rom = ROOT/'build/firmware/altirraos-816.rom'
    configuration = {**pin['configuration'], 'accuratedisk': accurate_disk}
    with emulator(binary, rom, out, pin=pin) as b:
        for key, value in configuration.items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, rom, pin)
        b.config('diskemu', diskemu)
        b.mount(0, str(media))
        original_regs=b.regs;last=[0]
        import time
        def regs():
            r=original_regs()
            if time.monotonic()-last[0]>30:
                print('Large read frame',b.eval_expr('@frame'),flush=True);last[0]=time.monotonic()
            return r
        b.regs=regs
        try:runtime, _ = execute(b, p, before_run=lambda b: b.profile_start(), timeout=1800, frame_limit=30000)
        finally:b.regs=original_regs
        b.profile_stop()
        observed = {name: int.from_bytes(bytes(data(b, p['image'], name)), 'little')
                    for name in ('received', 'ioError', 'verified', 'checks')}
        require(observed == dict(received=70003, ioError=0, verified=70003, checks=7), 'Read/cleanup failed')
        ownership(b, p, out)
        hardware = read(b, p['build']['task_storage']['BASE']+0x800, 128, out)
        require(hardware[0] == hardware[1] == hardware[45] == 0 and hardware[12:15] == hardware[16:19] == bytes(3),
                'Bus ownership retained')
        require(sha256(media) == media_hash, 'Media modified')
    result = dict(status='pass', mode=mode, build=p['build'], runtime=runtime, machine=machine,
                  configuration={**configuration, 'diskemu': diskemu},profile=profile,pin=pin,
                  observed=observed, media_sha256=media_hash, marks=marks,
                  timing=timing(out/'emulator.log', marks,profile), reserved_bank_zero_delta=0)
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['timing'], indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--no-disk-timing', action='store_true',
                        help='Disable mechanical disk delays; retain real SIO bytes, no patch or burst I/O')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile',type=int,choices=(1,4),default=1)
    parser.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    parser.add_argument('--paced',action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.case, accurate_disk=not args.no_disk_timing,profile=args.profile,compiler_dir=args.compiler_dir,paced=args.paced)
