#!/usr/bin/env python3
"""Focused mount cancellation/failure boundaries and audited SIO writes."""
import argparse
import json
import shutil
from pathlib import Path

from generate_memory import PROFILE
from library_paths import read_source
from make_data_disk import make
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN
from filesystem_audit import Audit


def instrument(output):
    for name in ('mountprobe.act', 'user_mount_integration.act'):
        shutil.copyfile(ROOT / 'tests/programs' / name, output / name)
    edits = {
        'blockwire.act': [
            ('  IF cancellable<>0 AND FSOPERATION.Canceled(scope)<>0 THEN',
             '  MOUNTPROBE.BeforeSend(0)\n  IF cancellable<>0 AND FSOPERATION.Canceled(scope)<>0 THEN'),
            ('  EXEC.SendIO(EXEC.IORequest POINTER(request))',
             '  EXEC.SendIO(EXEC.IORequest POINTER(request))\n  MOUNTPROBE.OnWire(EXEC.IORequest POINTER(request))'),
            ('  error=INT(CARD(state))',
             '  error=INT(CARD(state))\n  error=MOUNTPROBE.AfterTransfer(request,error)')],
        'fsinit.act': [
            ('mount=FSTYPES.Mount POINTER(EXEC.AllocMem(',
             'mount=FSTYPES.Mount POINTER(MOUNTPROBE.Allocate(31,'),
            ('block=BLOCKTYPES.Volume POINTER(EXEC.AllocMem(',
             'block=BLOCKTYPES.Volume POINTER(MOUNTPROBE.Allocate(32,'),
            ('  service.selected.writable=service.selected.spec.access',
             '  MOUNTPROBE.Point(20)\n  service.selected.writable=service.selected.spec.access'),
            ('    service.selected.published=1',
             '    service.selected.published=1\n    MOUNTPROBE.Point(21)')],
        'fsmount.act': [
            ('  busy=0\n  EXEC.Forbid()', '  MOUNTPROBE.Point(22)\n  busy=0\n  EXEC.Forbid()'),
            ('    service.mounts(service.index).item=FSTYPES.Mount POINTER(0)',
             '    service.mounts(service.index).item=FSTYPES.Mount POINTER(0)\n    MOUNTPROBE.Point(23)')]
    }
    for name, replacements in edits.items():
        source = read_source(ROOT / ('lib/io' if name == 'blockwire.act' else 'lib/fs') / name)
        source = source.replace('USE EXEC\n', 'USE EXEC\nUSE MOUNTPROBE\n', 1)
        for before, after in replacements:
            require(source.count(before) == 1, 'Stale mount boundary: ' + name + ' ' + before)
            source = source.replace(before, after)
        (output / name).write_text(source)
    return {name: sha256(output / name) for name in (*edits, 'mountprobe.act')}


def run(output, filesystem='mydos', size=128, point=12, scenario='boundary', reuse=None):
    output.mkdir(parents=True, exist_ok=True)
    observers = instrument(output)
    contents = output / 'contents'; contents.mkdir(exist_ok=True)
    media = output / 'disk.atr'
    if scenario == 'swap':
        (contents / 'SWAP.BIN').write_bytes(bytes([0x55])*64)
    make(media, contents, filesystem=filesystem, sector_bytes=size, sectors=720, binary_names={'SWAP.BIN'})
    second = output / 'second.atr'
    if scenario == 'swap':
        (contents / 'SWAP.BIN').write_bytes(bytes([0xaa])*64)
        make(second, contents, filesystem=filesystem, sector_bytes=size, sectors=720, binary_names={'SWAP.BIN'})
    digest = sha256(media)
    profile = json.loads(PROFILE.read_text()); profile['image_data_bytes'] = 4096
    memory = output / 'memory.json'; memory.write_text(json.dumps(profile)+'\n')
    program = read_build(reuse) if reuse else build(compiler(ROOT / 'build/actionc', release=True),
                  output / 'user_mount_integration.act', output, optimize=True,
                  tasks=True, task_capacity=8, console=True, memory_profile=memory,
                  dos_mounts=[dict(alias='RAM', format=3)])
    if reuse:
        for name, expected in program['build']['task_inputs'].items():
            require(sha256(ROOT / name) == expected, 'Stale mount integration build: ' + name)
        for name, expected in observers.items():
            require(sha256(reuse / name) == expected, 'Stale mount observer: ' + name)
        shutil.copyfile(reuse / 'manifest.bin', output / 'manifest.bin')
        program['output'] = output
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.config('diskemu', 'generic56k'); b.mount(1, str(media))
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        def before(bridge):
            for module, name, value in [('MOUNTINTEGRATION', 'scenario', {'boundary':0,'writes':1,'concurrent':2,'swap':3}[scenario]),
                        ('MOUNTINTEGRATION', 'format', 1 if filesystem == 'mydos' else 2),
                        ('MOUNTINTEGRATION', 'wantedBytes', size), ('MOUNTPROBE', 'mode', point)]:
                symbol = next(d for d in program['image']['data'] if
                              '_'+module+'_'+name.upper()+'_' in d['name'])
                bridge.memload(symbol['address'], value.to_bytes(symbol['size'], 'little'))
            if scenario == 'swap':
                flag = next(d['address'] for d in program['image']['data'] if '_MOUNTINTEGRATION_SWAPPHASE_' in d['name'])
                marker = program['labels']['native_nmi']
                condition = f'db(${flag:x})=1'
                bridge.bp_set(marker, condition=condition)
                run_to(bridge, marker, frame_limit=12000, timeout=240, condition=condition)
                bridge.mount(1, str(second))
                bridge.poke(flag, 2)
                bridge.bp_clear_all()
        try:
            runtime, _ = execute(b, program, before_run=before, timeout=240, frame_limit=12000)
        except Exception:
            print('Integration checks:', data(b, program['image'], 'checks', True), flush=True)
            print('Probe fired:', data(b, program['image'], 'fired'), flush=True)
            at = program['build']['memory']['dos_storage']['SHARED']
            raw = b.memdump(at, 594)
            runtime_pointer = int.from_bytes(raw[68:71], 'little')
            print('Registry masks/state:', raw[528:536].hex(), raw[71:73].hex(), flush=True)
            if runtime_pointer:
                print('Worker adapter/mounts:', b.memdump(runtime_pointer, 42).hex(), flush=True)
            raise
        require(data(b, program['image'], 'finished') == [1], 'Incomplete mount integration')
        checks = data(b, program['image'], 'checks', True)
        ownership(b, program, output)
    audit = None
    if scenario == 'writes':
        oracle = Audit(media.read_bytes())
        audit = getattr(oracle, filesystem)()
        require(oracle.files.get('TEST.TXT') == bytes(range(1, 65)), 'Wrong persisted mount write')
        require(audit['directories'] == 2, 'Missing persisted directory')
    else:
        require(sha256(media) == digest, 'Read-only mount boundary changed media')
    result = dict(status='pass', tier='development', scenario=scenario,
                  filesystem=filesystem, sector_bytes=size, point=point, checks=checks,
                  machine=machine, runtime=runtime, build=program['build'], observers=observers,
                  audit=audit, media_sha256=sha256(media),
                  bank_zero_delta=dict(fixed=0, per_task=0, idle=0))
    (output / 'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Mount integration passed:', scenario, filesystem, size, point, checks, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--filesystem', choices=('mydos','sdfs'), default='mydos')
    parser.add_argument('--size', type=int, choices=(128,256), default=128)
    parser.add_argument('--point', type=int, default=12)
    parser.add_argument('--scenario', choices=('boundary','writes','concurrent','swap'), default='boundary')
    a = parser.parse_args()
    run(a.output.resolve(), a.filesystem, a.size, a.point, a.scenario,
        a.from_build.resolve() if a.from_build else None)
