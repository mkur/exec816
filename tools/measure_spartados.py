#!/usr/bin/env python3
"""Read the unchanged demo HELLO under original SDX at the Exec disk profile."""
import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import time

from native_program import ROOT, require, sha256, verify_machine
from os_boundary import emulator
from make_sdfs_fixtures import CAR_SHA, CAR_URL, Media
from sdfs_reference import make


def prepare(output, source=None):
    output.mkdir(parents=True, exist_ok=True)
    source = source or ROOT/'tests/programs/spartados_read.s'
    (output/'probe.cfg').write_text('MEMORY { RAM: start=$6000,size=$2000,file=%O; } SEGMENTS { CODE: load=RAM,type=ro; }\n')
    subprocess.run(['ca65', '-o', str(output/'probe.o'), str(source)], check=True)
    subprocess.run(['ld65', '-C', str(output/'probe.cfg'), '-o', str(output/'probe.bin'),
                    '-Ln', str(output/'probe.lbl'), str(output/'probe.o')], check=True)
    labels = {s.split()[2].lstrip('.'): int(s.split()[1], 16)
              for s in (output/'probe.lbl').read_text().splitlines()}
    raw = (output/'probe.bin').read_bytes()
    startup = output/'startup'; startup.mkdir(exist_ok=True)
    (startup/'PROBE.COM').write_bytes(struct.pack('<HHH', 65535, 0x6000, 0x6000+len(raw)-1)
                                    +raw+struct.pack('<HHH', 0x2e0, 0x2e1, labels['start']))
    (startup/'AUTOEXEC.BAT').write_bytes(b'D1:PROBE.COM\x9b')
    (startup/'CONFIG.SYS').write_bytes(b'USE OSRAM\x9bDEVICE SPARTA\x9bDEVICE SIO\x9b')
    make(output/'startup.atr', startup)
    # Distinct volume identity is essential when swapping to the demo disk.
    disk = bytearray((output/'startup.atr').read_bytes())
    disk[16+38:16+40] = bytes([2, 0x81])
    (output/'startup.atr').write_bytes(disk)
    return labels


def stop(b, success, failure, frame_limit=12000, timeout=240):
    initial = b.eval_expr('@frame'); deadline = time.monotonic()+timeout
    b.resume()
    while time.monotonic() < deadline:
        regs = b.regs(); pc = int(regs['PC'].lstrip('$'), 16)
        if pc in (success, failure):
            b.pause()
            require(pc == success, 'Original SDX probe failed: '+str(regs))
            return regs
        if b.eval_expr('@frame')-initial > frame_limit:
            break
        time.sleep(.02)
    b.pause()
    raise RuntimeError('Original SDX probe timed out: '+str(regs))


def payload_trace(log_path, media_path):
    """Compare identical data-sector spans, independent of filesystem phases.

    POKEY's observer stamps peripheral/master ticks, including disk waiting.
    The final receive stamp is the start bit; include its ten serial bits.
    """
    media = Media(media_path.read_bytes())
    commands = media.row(media.entry(media.word(25), 'C'))
    entry = media.row(media.entry(int.from_bytes(commands[1:3], 'little'), 'HELLO'))
    _, sectors = media.chain(int.from_bytes(entry[1:3], 'little'))
    sectors = sectors[:(2359+media.size-1)//media.size]
    text = log_path.read_text()
    marker = '[Bridge] command: MOUNT'
    require(marker in text, 'Missing disk mount in trace')
    text = text[text.rfind(marker):]
    packets = []; packet = None
    for line in text.splitlines():
        match = re.match(r'\[SIOTXN\] command (\d+) 1$', line)
        if match:
            packet = dict(start=int(match[1]), tx=[], rx=[], tx_bits=[], rx_bits=[])
            packets.append(packet)
        match = re.match(r'\[SIOPOC\] ready (\d+) (\d+) (\d+) ', line)
        if match and packet is not None:
            packet['tx'].append(int(match[2])); packet['tx_bits'].append(int(match[3]))
        match = re.match(r'\[SIOTXN\] rxstart (\d+) (\d+) (\d+)$', line)
        if match and packet is not None:
            packet['rx'].append((int(match[1]), int(match[2])))
            packet['rx_bits'].append(int(match[3]))
    reads = [p for p in packets if len(p['tx']) == 5 and p['tx'][:2] == [0x31, 0x52]]
    sector = lambda p: p['tx'][2]+256*p['tx'][3]
    first = next(i for i, p in enumerate(reads) if sector(p) == sectors[0])
    payload = reads[first:first+len(sectors)]
    require([sector(p) for p in payload] == sectors, 'Noncontiguous or retried HELLO reads')
    require(all(len(p['rx']) == media.size+3 and [x[1] for x in p['rx'][:2]] == [0x41, 0x43]
                for p in payload), 'Unsuccessful/incomplete data-sector transaction')
    end = lambda p: p['rx'][-1][0]+10*p['rx_bits'][-1]
    gaps = [b['start']-end(a) for a, b in zip(payload, payload[1:])]
    hz = 1773447
    return dict(sectors=sectors, read_count=len(payload), clock_hz=hz,
                tx_cycles_per_bit=sorted({v for p in payload for v in p['tx_bits']}),
                rx_cycles_per_bit=sorted({v for p in payload for v in p['rx_bits']}),
                span_ticks=end(payload[-1])-payload[0]['start'],
                span_seconds=(end(payload[-1])-payload[0]['start'])/hz,
                between_requests_ticks=gaps, between_requests_seconds=sum(gaps)/hz,
                mean_between_requests_ms=sum(gaps)/len(gaps)/hz*1000,
                log_sha256=sha256(log_path))


def run(bundle, output):
    labels = prepare(output)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    pin = manifest['pin']; configuration = manifest['configuration']
    car = ROOT/'build/development/spartados-s1/SDX450_maxflash1.car'
    require(sha256(car) == CAR_SHA, 'Changed original SDX cartridge')
    require(manifest['filesystem'] == 'sdfs', 'SpartaDOS benchmark requires SDFS media')
    media = bundle/manifest['media']
    require(sha256(media) == manifest['artifacts'][manifest['media']], 'Changed benchmark disk')
    payload = bundle/'media/C/HELLO'
    require(sha256(payload) == manifest['files']['C/HELLO']['sha256'], 'Changed HELLO payload')
    require(payload.stat().st_size == 2359, 'Reassemble reader for the changed HELLO length')
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer') == pin['emulator']['sha256'],
            'Changed emulator binary')
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', output, pin=pin) as b:
        for key, value in configuration.items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', pin)
        b.mount(0, str(output/'startup.atr'))
        b.bp_set(labels['start']); b.bp_set(labels['failed'])
        b.boot(str(car))
        try:
            stop(b, labels['start'], labels['failed'])
            print('SDX ready at reader entry', flush=True)
            b.mount(0, str(media))
            b.bp_clear_all(); b.bp_set(labels['done']); b.bp_set(labels['failed'])
            before = dict(frame=b.eval_expr('@frame'), cycles=b.regs()['cycles'])
            stop(b, labels['done'], labels['failed'])
            after = dict(frame=b.eval_expr('@frame'), cycles=b.regs()['cycles'])
            require(b.peek(labels['result'])[0] == 1, 'Missing SDX completion')
            contents = b.memdump(labels['buffer'], len(payload.read_bytes()))
            require(contents == payload.read_bytes(), 'Original SDX returned different payload bytes')
            raw = b.peek(labels['ticks'], 12)
            ticks = [int.from_bytes(raw[i:i+3], 'big') for i in range(0, 12, 3)]
            phases = {name: dict(frames=(ticks[i+1]-ticks[i])&0xffffff,
                                 seconds=((ticks[i+1]-ticks[i])&0xffffff)/50)
                      for i, name in enumerate(('open', 'payload', 'close'))}
            result = dict(status='pass', machine=machine, configuration=configuration,
                          pin=pin, cartridge_sha256=CAR_SHA, cartridge_url=CAR_URL,
                          media_sha256=sha256(media), payload_sha256=sha256(payload), payload_bytes=len(contents),
                          probe_source_sha256=sha256(ROOT/'tests/programs/spartados_read.s'),
                          harness_sha256=sha256(Path(__file__)),
                          probe_sha256=sha256(output/'probe.bin'), startup_sha256=sha256(output/'startup.atr'),
                          serial_trace_enabled='EXEC816_LATENCY_TRACE' in os.environ,
                          phases=phases, ticks=ticks, before=before, after=after,
                          conditions='Original SDX 4.50; DEVICE SPARTA and DEVICE SIO; 512-byte CIO reads; '
                                     'first HELLO access after swapping from a distinct startup volume; '
                                     'no payload cache warmup; guest timing excludes debugger pauses.')
            print(json.dumps(phases), flush=True)
        finally:
            b.pause()
            (output/'screen.png').write_bytes(b.screenshot())
    if result['serial_trace_enabled']:
        result['payload_trace'] = payload_trace(output/'emulator.log', media)
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, default=ROOT/'build/development/spartados-s6/sdfs/bundle')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.bundle.resolve(), args.output.resolve())
