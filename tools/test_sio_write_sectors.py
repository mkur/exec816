#!/usr/bin/env python3
"""Write disposable ATR sectors through emitted code and verify persisted bytes."""
import argparse
import json
import time
from pathlib import Path

from native_program import ROOT, build, compiler, execute, require, verify_machine, sha256
from os_boundary import emulator
from sector_images import disk_image
from test_sio_device import PIN
from test_cooperative import data
from banked_test_memory import read as far_read
from test_heap_api import clean_ownership
from mydos_fixtures import Image


def run(toolchain, output, optimize, profile, size, block=False):
    require(profile in (1, 2, 4) and (profile != 2 or size == 128), 'Unsupported profile/size')
    source = 'block_write.act' if block else 'sio_write_sectors.act'
    program = build(toolchain, ROOT/'tests/programs'/source, output,
                    optimize=optimize, tasks=True, image_data=[(0xaffd0, bytes([0xa5])*320)])
    disk = output/'sectors.atr'
    disk_image(disk, size, 65535)
    expected = Image(disk.read_bytes())
    sectors = [1, 4, 65534] if block else [1, 2, 3, 4, 720, 1024, 32768, 65535]
    for sector in sectors:
        length = 128 if sector < 4 else size
        offset = expected.offset(sector)
        seed = {1: 0x6c, 4: 0x69, 65534: 0x93}[sector] if block else (sector & 255) ^ 0x6d
        expected.data[offset:offset + length] = bytes(i ^ seed for i in range(length))
    binary = ROOT/'build/altirra-sio-multi'
    require(sha256(binary/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Unpinned emulator')
    with emulator(binary, ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        diskemu = {1: 'fastest', 2: '810', 4: 'generic56k'}[profile]
        for key, value in {**PIN['configuration'], 'diskemu': diskemu}.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)

        def before(bridge):
            bridge.mount(0, str(disk))
            for name, value in [('PROFILE', profile), ('SECTORBYTES', size)]:
                address = next(d['address'] for d in program['image']['data'] if f'_{name}_' in d['name'])
                bridge.poke(address, value & 255)
                bridge.poke(address + 1, value >> 8)

        try:
            runtime, _ = execute(bridge, program, before_run=before, timeout=240, frame_limit=12000)
        except Exception:
            print('checks', data(bridge, program['image'], 'checks', True),
                  'profile', data(bridge, program['image'], 'profile', True),
                  'sectorBytes', data(bridge, program['image'], 'sectorBytes', True), flush=True)
            if block:
                address = int.from_bytes(data(bridge, program['image'], 'adapter'), 'little')
                print('adapter', hex(address), far_read(bridge, address, 64, output).hex(), flush=True)
            raise
        clean_ownership(bridge, program, output)
        buffer = far_read(bridge, 0xaffd0, 320, output)
        require(buffer[:32] == buffer[-32:] == bytes([0xa5])*32, 'Buffer guard changed')
        hardware = far_read(bridge, program['build']['task_storage']['BASE'] + 0x800, 128, output)
        if not block:
            require(int.from_bytes(hardware[56:58], 'little') == 16, 'Wrong wire transaction count')
        checks = data(bridge, program['image'], 'checks', True)
        # The pinned emulator flushes dirty disk images on its host idle timer.
        # Eject alone is not a flush; retain attachment beyond that interval.
        time.sleep(3)
        bridge.regs()
        bridge._cmd_ok('EJECT drive=0')
    require(disk.read_bytes() == expected.data, 'Persisted ATR differs from exact sector writes')
    return dict(status='pass', build=program['build'], runtime=runtime, machine=machine,
                profile=profile, sector_bytes=size, sectors=sectors, checks=checks,
                media_sha256=sha256(disk), bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--profile', type=int, choices=(1, 2, 4), default=1)
    parser.add_argument('--size', type=int, choices=(128, 256), default=256)
    parser.add_argument('--block', action='store_true', help='Exercise the write-through block cache')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(compiler(ROOT/'build/actionc'), out, args.case == 'opt', args.profile, args.size, args.block)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Persisted SIO sector writes passed', args.case, args.profile, args.size)
