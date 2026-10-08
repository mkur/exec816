#!/usr/bin/env python3
"""Cold-motor verified writes with accurate Generic 57600 mechanics."""
import argparse
import json
import os
import time
from pathlib import Path

from native_program import ROOT, build, compiler, require, verify_machine, sha256
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from sector_images import disk_image
from mydos_fixtures import Image
from banked_test_memory import read
from sio_transaction_trace import read_events, BASE_HZ

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def transactions(events, terminal_pc):
    starts = [t for t, e in events if e[0] == 'command' and e[2] == '1']
    terminals = [t for t, e in events
                 if e[0] == 'cpu' and int(e[4], 16) == terminal_pc]
    rows = []
    for terminal in terminals:
        start = max(t for t in starts if t < terminal)
        tx = [int(e[2]) for t, e in events
              if start <= t < terminal and e[0] == 'write']
        rx = [int(e[2]) for t, e in events
              if start <= t < terminal and e[0] == 'receive']
        rows.append(dict(unit=tx[0], command=tx[1], sector=tx[2]+256*tx[3],
                         active_ms=(terminal-start)/BASE_HZ*1000,
                         tx_bytes=len(tx), rx_bytes=rx if tx[1] == 0x57 else len(rx)))
    return rows


def run(toolchain, output, size):
    program = build(toolchain, ROOT/'tests/programs/sio_write_deadline.act', output,
                    optimize=True, tasks=True, task_capacity=8,
                    image_data=[(0xaffd0, bytes([0xa5])*320)])
    disk = output/'sectors.atr'
    disk_image(disk, size, 720)
    before_hash = sha256(disk)
    expected = Image(disk.read_bytes())
    sectors = [720, 360, 4]
    for sector in sectors:
        at = expected.offset(sector)
        expected.data[at:at+size] = bytes((i ^ (sector & 255) ^ 0x6d) & 255 for i in range(size))
    binary = ROOT/'build/shell-paced-bridge'
    require(sha256(binary/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Unpinned emulator')
    os.environ['EXEC816_LATENCY_TRACE'] = '1'
    os.environ['EXEC816_LATENCY_PCS'] = f"{program['labels']['sio_terminal']:x}"
    with emulator(binary, ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        configuration = {**PIN['configuration'], 'diskemu': 'generic56k', 'accuratedisk': True}
        for key, value in configuration.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        def before(bridge):
            bridge.mount(7, str(disk))
            at = next(d['address'] for d in program['image']['data'] if '_SECTORBYTES_' in d['name'])
            bridge.memload(at, size.to_bytes(2, 'little'))
            bridge.profile_start()
        runtime, _ = execute(bridge, program, before_run=before, timeout=120, frame_limit=5000)
        bridge.profile_stop()
        ownership(bridge, program, output)
        guards = read(bridge, 0xaffd0, 320, output)
        require(guards[:32] == guards[-32:] == bytes([0xa5])*32, 'Changed transfer guards')
        hardware = read(bridge, program['build']['task_storage']['BASE']+0x800, 128, output)
        require(hardware[45] == 0 and int.from_bytes(hardware[56:58], 'little') == 6,
                'Wrong offline state or wire request count')
        require(int.from_bytes(hardware[6:8], 'little') == 248, 'Ordinary read deadline changed')
        checks = data(bridge, program['image'], 'checks', True)
        time.sleep(3)
        bridge.regs()
        bridge._cmd_ok('EJECT drive=7')
    require(disk.read_bytes() == expected.data, 'Persisted cold writes differ from independent oracle')
    rows = transactions(read_events(output/'emulator.log'), program['labels']['sio_terminal'])
    require([(r['command'], r['sector']) for r in rows] ==
            [(command, sector) for sector in sectors for command in (0x57, 0x52)],
            'Incomplete cold-write observation')
    for row in rows:
        if row['command'] == 0x57:
            require(row['tx_bytes'] == size+6 and row['rx_bytes'] == [0x41, 0x41, 0x43],
                    'WRITE omitted payload, ACK or verified completion')
        require(row['active_ms'] < (2001 if row['command'] == 0x57 else 1003),
                'Transaction exceeded its bounded allowance')
    return dict(status='pass', tier='development', build=program['build'], pin=PIN,
                runtime=runtime, machine=machine, configuration=configuration,
                sector_bytes=size, checks=checks, transactions=rows,
                runner_sha256=sha256(Path(__file__)), media_before_sha256=before_hash,
                media_after_sha256=sha256(disk), log_sha256=sha256(output/'emulator.log'),
                bank_zero_delta=dict(fixed=0, per_task=0),
                scope='Optimized native cold-motor WRITE/readback, exact persisted sectors, '
                      'guarded cross-bank buffer, ownership and OS restoration; emulator development evidence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, choices=(128, 256), default=256)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(compiler(ROOT/'build/actionc'), out, args.size)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Cold verified writes passed', args.size)
