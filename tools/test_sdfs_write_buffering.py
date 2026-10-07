#!/usr/bin/env python3
"""One real DOS Write, verified physical-write trace and independent media audit."""
import argparse
from collections import Counter
import json
import shutil
import time
from pathlib import Path

from banked_test_memory import read
from filesystem_audit import Audit, word
from generate_dos_mounts import encode
from library_paths import library_file, read_source
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN


def run(out, mode, size, amount, expected_writes=None, cache_blocks=None,
        ordered=False):
    require(1 <= amount <= 32768, 'Amount must be 1..32768')
    for name in ('sdfsbatchprobe.act', 'sdfs_write_buffering.act'):
        (out/name).write_text(read_source(ROOT/'tests/programs'/name))
    source = read_source(library_file('fswriteio.act'))
    source = source.replace('USE EXEC\n', 'USE EXEC\nUSE SDFSBATCHPROBE\n', 1)
    marker = '\nRETURN(1)\n\nPUBLIC PROC Zero('
    require(source.count(marker) == 1, 'Stale verified-write observer')
    source = source.replace(marker, '\n  SDFSBATCHPROBE.Completed(service,sector)\n' + marker)
    (out/'fswriteio.act').write_text(source)
    media = out/'volume.atr'
    shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/sdfs-{size}.atr', media)
    before = Audit(media.read_bytes())
    before.sdfs()
    mounts = [dict(alias='D1', unit=49, sectors=before.image.count,
                   sector_bytes=size, format=2, access='readwrite', profile=4)]
    program = build(compiler(ROOT/'build/actionc'), out/'sdfs_write_buffering.act',
                    out, optimize=mode == 'opt', tasks=True, task_capacity=8,
                    console_deferred=True,
                    dos_mounts=mounts,
                    image_data=[(0x30ffd0, bytes([0xa5])*(amount+64)),
                                (0xd0000, bytes(384*2))])
    with emulator(ROOT/'build/altirra-sio-multi',
                  ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        configuration = {**PIN['configuration'], 'diskemu': 'generic56k',
                         'accuratedisk': False}
        for key, value in configuration.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)

        def before_run(b):
            b.mount(0, str(media))
            b.memload(program['build']['task_storage']['BASE']+0x900, encode(mounts))
            at = next(d['address'] for d in program['image']['data']
                      if '_SDFSBATCHTEST_AMOUNT_' in d['name'])
            b.memload(at, amount.to_bytes(4, 'little'))
            if cache_blocks is not None:
                boot = program['build']['memory']['boot_config']
                b.memload(boot['address']+boot['abi']['fields']['cache_blocks'],
                          cache_blocks.to_bytes(2, 'little'))

        try:
            runtime, _ = execute(bridge, program, before_run=before_run,
                                 timeout=900, frame_limit=60000)
        except Exception:
            for name in ('checks', 'phase', 'result', 'error'):
                print(name, data(bridge, program['image'], name, True), flush=True)
            raise
        ownership(bridge, program, out)
        view = {**program['image'], 'data': [d for d in program['image']['data']
                                           if '_SDFSBATCHPROBE_' in d['name']]}
        count = int.from_bytes(bytes(data(bridge, view, 'count')), 'little')
        require(count < 384, 'Physical-write trace overflow')
        raw_trace = read(bridge, 0xd0000, count*2, out)
        trace = [int.from_bytes(raw_trace[i:i+2], 'little')
                 for i in range(0, len(raw_trace), 2)]
        workspace = data(bridge, program['image'], 'workspaceBytes', True)[0]
        guard = read(bridge, 0x30ffd0, amount+64, out)
        require(guard[:32] == guard[-32:] == bytes([0xa5])*32,
                'Caller buffer guard changed')
        time.sleep(3)
        bridge.regs()
        bridge._cmd_ok('EJECT drive=0')
    after = Audit(media.read_bytes())
    allocation = after.sdfs()
    require(after.files == {**before.files, 'BATCH.BIN':
                           bytes((i & 255) ^ 0x6d for i in range(amount))},
            'Persisted bytes or unrelated file changed')
    header = after.image.sector(1)
    bitmap = range(word(header, 16), word(header, 16)+header[15])

    def classify(sector):
        owner = after.owners.get(sector, '')
        if sector == 1:
            return 'header'
        if sector in bitmap:
            return 'bitmap'
        if owner.startswith('BATCH.BIN map'):
            return 'map'
        if owner == 'BATCH.BIN data':
            return 'payload'
        require(owner == ' data', f'Unexpected write sector {sector}: {owner}')
        return 'directory'

    phases = [classify(s) for s in trace]
    counts = dict(Counter(phases))
    if expected_writes is not None:
        require(count == expected_writes, f'Write count {count}, expected {expected_writes}')
        if size == 256 and amount == 16384 and expected_writes in (68, 128):
            metadata = 1 if expected_writes == 68 else 16
            require(counts == dict(payload=64, bitmap=metadata, header=metadata,
                                   map=metadata, directory=metadata),
                    f'Incorrect focused write breakdown: {counts}')
    if ordered:
        require(size == 256 and amount <= 16384,
                'Ordered trace check requires the single-map 256-byte fixture')
        at = 0
        while at < len(phases):
            start = at
            while at < len(phases) and phases[at] == 'payload':
                at += 1
            require(at > start and phases[at:at+4] ==
                    ['bitmap', 'header', 'map', 'directory'],
                    f'Incorrect publication order at write {at}: {phases}')
            at += 4
    return dict(status='pass', tier='development', build=program['build'],
                runtime=runtime, machine=machine, configuration=configuration,
                amount=amount, sector_bytes=size, verified_writes=count,
                phases=phases, sectors=trace, counts=counts,
                workspace_requested_bytes=workspace,
                workspace_rounded_bytes=(workspace+7)//8*8,
                allocation=allocation, media_sha256=sha256(media),
                cache_blocks_override=cache_blocks,
                observer_sha256=sha256(out/'fswriteio.act'),
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=('raw', 'opt'), default='opt')
    p.add_argument('--size', choices=(128, 256), type=int, default=256)
    p.add_argument('--amount', type=int, default=16384)
    p.add_argument('--expected-writes', type=int)
    p.add_argument('--cache-blocks', type=int)
    p.add_argument('--ordered', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.case, args.size, args.amount,
                     args.expected_writes, args.cache_blocks, args.ordered)
        print('SDFS Write:', result['verified_writes'], result['counts'], flush=True)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
