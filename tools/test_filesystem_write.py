#!/usr/bin/env python3
"""Public filesystem mutations, persisted ATR audit and unchanged-file oracle."""
import argparse
import json
import shutil
import time
from pathlib import Path

from native_program import ROOT, build, compiler, verify_machine, sha256, require, read_build
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from test_heap_api import clean_ownership
from test_dos_stack import execute
from filesystem_audit import Audit
from banked_test_memory import read as far_read
from generate_dos_mounts import encode

CAPACITY = 33038


def reuse(path):
    program = read_build(path)
    record = program['build']
    require(sha256(ROOT/'tests/programs'/record['source']) == record['source_sha256'],
            'Changed test source')
    for group in ('platform_inputs', 'task_inputs', 'console_inputs', 'banked_inputs'):
        for name, digest in record.get(group, {}).items():
            require(sha256(ROOT/name) == digest, 'Changed build input: ' + name)
    return program


def run(toolchain, output, mode, filesystem, size, amount, fast_media=False,
        from_build=None, hint=0):
    require(140 <= amount <= 33000, 'Amount must be 140..33000')
    paths = bytearray(7 * 64)
    for index, name in enumerate(['WRITE.BIN', 'WRENAMED.BIN', 'WRITEDIR',
                                  'WRITEDIR/CHILD', 'WTRUNC.BIN', 'WEMPTY', '']):
        value = ('D1:' + name).encode() + b'\0'
        paths[index * 64:index * 64 + len(value)] = value
    media = output/'volume.atr'
    shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-{size}.atr', media)
    before = Audit(media.read_bytes())
    getattr(before, filesystem)()
    mounts = [dict(alias='D1', unit=49, sectors=before.image.count,
                   sector_bytes=size, format=1 if filesystem == 'mydos' else 2,
                   access='readwrite')]
    program = reuse(from_build) if from_build else build(
                    toolchain, ROOT/'tests/programs/filesystem_write.act', output,
                    optimize=mode == 'opt', tasks=True, dos_mounts=mounts,
                    console_deferred=True,
                    image_data=[(0xd1000, bytes(paths)),
                                (0xaffd0, bytes([0xa5])*(CAPACITY+64))])
    require(program['build']['optimize'] == (mode == 'opt'), 'Changed emission mode')
    binary = ROOT/'build/altirra-sio-multi'
    with emulator(binary, ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        configuration = {**PIN['configuration'], 'diskemu': 'fastest'}
        if fast_media:
            configuration['accuratedisk'] = False
        for key, value in configuration.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)

        def before_run(bridge):
            bridge.mount(0, str(media))
            bridge.memload(program['build']['task_storage']['BASE'] + 0x900, encode(mounts))
            address = next(d['address'] for d in program['image']['data'] if '_AMOUNT_' in d['name'])
            for offset, value in enumerate(amount.to_bytes(4, 'little')):
                bridge.poke(address + offset, value)
            address = next(d['address'] for d in program['image']['data'] if '_HINT_' in d['name'])
            bridge.memload(address, hint.to_bytes(2, 'little'))

        try:
            runtime, _ = execute(bridge, program, before_run=before_run,
                                 timeout=900, frame_limit=60000)
        except Exception:
            for name in ['checks', 'phase', 'lastResult', 'lastError']:
                print(name, data(bridge, program['image'], name, True), flush=True)
            raise
        clean_ownership(bridge, program, program['output'])
        guard = far_read(bridge, 0xaffd0, amount + 102, output)
        require(guard[:32] == guard[-32:] == bytes([0xa5])*32, 'Caller buffer guard changed')
        checks = data(bridge, program['image'], 'checks', True)
        layouts = data(bridge, program['image'], 'layouts', True)
        time.sleep(3)
        bridge.regs()
        bridge._cmd_ok('EJECT drive=0')
    after = Audit(media.read_bytes())
    report = getattr(after, filesystem)()
    expected = dict(before.files)
    content = bytearray((i & 255) ^ 0x6d for i in range(amount))
    content[123:140] = bytes(i + 0x31 for i in range(17))
    content.extend(i + 0x93 for i in range(37))
    expected.update({'WRENAMED.BIN': bytes(content), 'WEMPTY': b''})
    require(after.files == expected, 'Persisted file content or unrelated files changed')
    return dict(status='pass', build=program['build'], runtime=runtime, machine=machine,
                filesystem=filesystem, sector_bytes=size, amount=amount, checks=checks,
                allocation=report, media_sha256=sha256(media), layouts=layouts,
                configuration=configuration,
                runtime_mounts=mounts, allocation_hint=hint,
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--filesystem', choices=('mydos', 'sdfs'), required=True)
    parser.add_argument('--size', choices=(128, 256), type=int, default=128)
    parser.add_argument('--amount', type=int, default=257)
    parser.add_argument('--fast-media', action='store_true',
                        help='Disable rotational delays for functional tests; serial I/O remains physical')
    parser.add_argument('--from-build', type=Path, help='Reuse unchanged emitted code with explicit runtime geometry')
    parser.add_argument('--hint', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(compiler(ROOT/'build/actionc'), output, args.case,
                     args.filesystem, args.size, args.amount, args.fast_media,
                     args.from_build, args.hint)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Persisted filesystem writes passed', args.case, args.filesystem, args.size)
