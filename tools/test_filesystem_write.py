#!/usr/bin/env python3
"""Public filesystem mutations, persisted ATR audit and unchanged-file oracle."""
import argparse
import json
import shutil
import time
import re
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
        from_build=None, hint=0, fixture=None, cache_blocks=None, profile=4,
        file_only=False):
    require(140 <= amount <= 33000, 'Amount must be 140..33000')
    paths = bytearray(7 * 64)
    for index, name in enumerate(['WRITE.BIN', 'WRENAMED.BIN', 'WRITEDIR',
                                  'WRITEDIR/CHILD', 'WTRUNC.BIN', 'WEMPTY', '']):
        value = ('D1:' + name).encode() + b'\0'
        paths[index * 64:index * 64 + len(value)] = value
    media = output/'volume.atr'
    shutil.copyfile(fixture or ROOT/f'tests/fixtures/filesystem-write/{filesystem}-{size}.atr', media)
    before = Audit(media.read_bytes())
    getattr(before, filesystem)()
    mounts = [dict(alias='D1', unit=49, sectors=before.image.count,
                   sector_bytes=size, format=1 if filesystem == 'mydos' else 2,
                   access='readwrite', profile=profile)]
    program = reuse(from_build) if from_build else build(
                    toolchain, ROOT/'tests/programs/filesystem_write.act', output,
                    optimize=mode == 'opt', tasks=True, dos_mounts=mounts,
                    console_deferred=True,
                    image_data=[(0xd1000, bytes(paths)),
                                (0x30ffd0, bytes([0xa5])*(CAPACITY+64))])
    require(program['build']['optimize'] == (mode == 'opt'), 'Changed emission mode')
    binary = ROOT/'build/altirra-sio-multi'
    with emulator(binary, ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        configuration = {**PIN['configuration'],
                         'diskemu': {1:'fastest', 2:'810', 4:'generic56k'}[profile]}
        if fast_media:
            configuration['accuratedisk'] = False
        for key, value in configuration.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)

        def before_run(bridge):
            bridge.mount(0, str(media))
            if cache_blocks is not None:
                boot=program['build']['memory']['boot_config']
                bridge.memload(boot['address']+boot['abi']['fields']['cache_blocks'],
                               cache_blocks.to_bytes(2,'little'))
            bridge.memload(program['build']['task_storage']['BASE'] + 0x900, encode(mounts))
            address = next(d['address'] for d in program['image']['data'] if '_AMOUNT_' in d['name'])
            for offset, value in enumerate(amount.to_bytes(4, 'little')):
                bridge.poke(address + offset, value)
            address = next(d['address'] for d in program['image']['data'] if '_HINT_' in d['name'])
            bridge.memload(address, hint.to_bytes(2, 'little'))
            address = next(d['address'] for d in program['image']['data'] if '_FILEONLY_' in d['name'])
            bridge.poke(address, int(file_only))

        original_regs = bridge.regs
        polls = 0
        def sampled_regs():
            nonlocal polls
            registers = original_regs()
            polls += 1
            if polls % 20 == 0:
                status = int.from_bytes(bridge.memdump(0x800, 2), 'little')
                require(status in (0, 0xffff), f'Native failure status ${status:04x}')
            if polls % 200 == 0:
                view = {**program['image'], 'data': [d for d in program['image']['data']
                                                   if '_FSWRITETEST_' in d['name']]}
                progress = dict(registers=registers, fields={name:data(bridge,view,name,True)
                                for name in ('checks','phase','lastResult','lastError')})
                (output/'live.json').write_text(json.dumps(progress,indent=2)+'\n')
            return registers
        bridge.regs = sampled_regs
        try:
            try:
                runtime, _ = execute(bridge, program, before_run=before_run,
                                     timeout=900, frame_limit=60000)
            finally:
                bridge.regs = original_regs
        except Exception:
            view = {**program['image'], 'data': [d for d in program['image']['data']
                                               if '_FSWRITETEST_' in d['name']]}
            fields = {name: data(bridge, view, name, True)
                      for name in ('checks', 'phase', 'lastResult', 'lastError')}
            storage = (program['output']/'sio-storage-action.inc').read_text()
            addresses = dict(re.findall(r'CONST (SD_\w+)=\$(\w+)', storage))
            diagnostic = dict(fields=fields, registers=bridge.regs(),
                              paths=list(bridge.memdump(0xd1000, 7*64)),
                              sio={name:list(bridge.memdump(int(addresses[name],16),2))
                                   for name in ('SD_PHASE','SD_ERROR','SD_ACTUAL',
                                                'SD_CLOCK','SD_DEADLINE','SD_OFFLINE')},
                              command=list(bridge.memdump(int(addresses['SD_COMMAND'],16),5)))
            (output/'failure.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
            print(fields, flush=True)
            raise
        clean_ownership(bridge, program, program['output'])
        guard = far_read(bridge, 0x30ffd0, amount + 102, output)
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
    expected.update({'WRENAMED.BIN': bytes(content)})
    if not file_only:
        expected['WEMPTY'] = b''
    require(after.files == expected, 'Persisted file content or unrelated files changed')
    return dict(status='pass', build=program['build'], runtime=runtime, machine=machine,
                filesystem=filesystem, sector_bytes=size, amount=amount, checks=checks,
                allocation=report, media_sha256=sha256(media), layouts=layouts,
                configuration=configuration,
                runtime_mounts=mounts, allocation_hint=hint,
                fixture=str(fixture) if fixture else None, cache_blocks_override=cache_blocks,
                file_only=file_only,
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
    parser.add_argument('--fixture', type=Path, help='Independent audited input media')
    parser.add_argument('--cache-blocks', type=int, help='Boot cache override; zero disables it')
    parser.add_argument('--profile', type=int, choices=(1, 2, 4), default=4,
                        help='Peripheral profile; development defaults to nominal 57.6k')
    parser.add_argument('--file-only', action='store_true',
                        help='Focus geometry cases on Write/read-back/overwrite/append/remount')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(compiler(ROOT/'build/actionc'), output, args.case,
                     args.filesystem, args.size, args.amount, args.fast_media,
                     args.from_build, args.hint, args.fixture, args.cache_blocks,
                     args.profile, args.file_only)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Persisted filesystem writes passed', args.case, args.filesystem, args.size)
