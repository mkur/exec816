#!/usr/bin/env python3
"""Run the actual loadable FUJI command with inherited DOS output and serial."""
import argparse
import json
import shutil
from pathlib import Path
from build_command import compile_command
from fujinet_peer import make_peer
from make_data_disk import make
from native_program import ROOT, build, compiler, require, verify_machine, sha256, read_build
from os_boundary import emulator, run_to
from filesystem_audit import Audit
from test_dos_stack import execute, ownership
from test_cooperative import data
from test_sio_device import PIN


def run(output, reuse=None, absent=False, images=False, workflow=False,
        filesystem='mydos', size=128):
    output.mkdir(parents=True, exist_ok=True)
    t = compiler(ROOT / 'build/actionc', release=True)
    peer = make_peer(output / 'peer', discovery=False, commands=True)
    contents = output / 'contents'; contents.mkdir(exist_ok=True)
    compile_command(t, ROOT / 'examples/commands/fuji.act', output / 'commands/FUJI')
    shutil.copyfile(output / 'commands/FUJI', contents / 'FUJI')
    for path in contents.glob('FUJI.*.json'):
        path.unlink()
    make(output / 'commands.atr', contents, filesystem='sdfs', sectors=720,
         sector_bytes=128, binary_names={'FUJI'})
    if workflow:
        selected = output / 'selected'; selected.mkdir(exist_ok=True)
        (selected / 'SWAP.BIN').write_bytes(b'\x55' * 64)
        make(output / 'first.atr', selected, filesystem=filesystem,
             sectors=720, sector_bytes=size, binary_names={'SWAP.BIN'})
        (selected / 'SWAP.BIN').write_bytes(b'\xaa' * 64)
        make(output / 'second.atr', selected, filesystem=filesystem,
             sectors=720, sector_bytes=size, binary_names={'SWAP.BIN'})
        first_digest = sha256(output / 'first.atr')
    profile = json.loads((ROOT / 'platform/altirraos/memory-4m.json').read_text())
    # The native workflow fixture carries its own 2 KiB readback buffer and
    # metadata snapshots. This is test arena capacity, not a demo reservation.
    profile['image_data_bytes'] = 8192
    memory = output / 'memory.json'; memory.write_text(json.dumps(profile, indent=2) + '\n')
    p = read_build(reuse) if reuse else build(t, ROOT / 'tests/programs/fuji_command.act', output / 'program',
              tasks=True, task_capacity=8, optimize=True, console_deferred=True,
              dos_mounts=[dict(alias='D1', unit=49, profile=4, format=2, sectors=720, sector_bytes=128),
                          dict(alias='RAM', format=3)], system_mount='D1', memory_profile=memory)
    if reuse:
        for name, digest in p['build']['task_inputs'].items():
            require(sha256(ROOT / name) == digest, 'Stale FUJI input: ' + name)
        require(sha256(ROOT / 'tests/programs/fuji_command.act') ==
                p['build']['source_sha256'], 'Stale FUJI test source')
        inputs = json.loads((reuse / 'fuji-test-inputs.json').read_text())
        for name in ('images', 'workflow'):
            source = ROOT / ('tests/programs/fuji-images-test.inc' if name == 'images'
                             else 'tests/programs/fuji-workflow.inc')
            require(sha256(source) == inputs[name], 'Stale FUJI test: ' + name)
    else:
        (output / 'program/fuji-test-inputs.json').write_text(json.dumps(dict(
            images=sha256(ROOT / 'tests/programs/fuji-images-test.inc'),
            workflow=sha256(ROOT / 'tests/programs/fuji-workflow.inc')))+'\n')
    digest = sha256(output / 'commands.atr')
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        if not absent:
            b.device_set('custom', path=str(peer))
        for k, v in PIN['configuration'].items():
            b.config(k, str(v).lower() if isinstance(v, bool) else v)
        # This is a functional command test, not a disk timing measurement.
        b.config('accuratedisk', 'false')
        b.config('diskemu', 'generic56k'); b.mount(0, str(output / 'commands.atr'))
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        def before(bridge):
            flag = next(d for d in p['image']['data'] if '_FUJICOMMANDTEST_SCENARIO_' in d['name'])
            bridge.memload(flag['address'], bytes([1 if absent else 2 if images else 3 if workflow else 0]))
            if workflow:
                def symbol(name):
                    return next(d['address'] for d in p['image']['data']
                                if '_FUJICOMMANDTEST_' + name + '_' in d['name'])
                bridge.poke(symbol('TESTFORMAT'), 1 if filesystem == 'mydos' else 2)
                bridge.memload(symbol('WANTEDBYTES'), size.to_bytes(2, 'little'))
                phase = symbol('MEDIAPHASE')
                marker = p['labels']['native_nmi']
                condition = f'db(${phase:x})!=0'
                bridge.bp_set(marker, condition=condition)
                for index, media in enumerate(('first.atr', 'second.atr'), 1):
                    run_to(bridge, marker, 12000, 240, condition)
                    require(bridge.memdump(phase, 1) == bytes([index]), 'Wrong image rendezvous')
                    bridge.mount(1, str(output / media))
                    bridge.poke(phase, 0)
                bridge.bp_clear_all()
        try:
            runtime, _ = execute(b, p, before_run=before, timeout=240, frame_limit=12000,
                                 expected_status=0xff93 if absent else 0)
        except Exception:
            print('FUJI assertions', data(b, p['image'], 'checks', True), flush=True)
            print('Outcome', data(b, p['image'], 'outcome'), flush=True)
            raise
        checks = data(b, p['image'], 'checks', True)[0]
        if absent:
            require(checks >= 6 and data(b, p['image'], 'outcome') ==
                    [10, 0, 0, 0, 1, 0, 0, 0], 'Missing bounded absence error')
        else:
            require(data(b, p['image'], 'completed') == [1], 'FUJI workflow incomplete')
            ownership(b, p, p['output'])
    require(sha256(output / 'commands.atr') == digest, 'Commands disk changed')
    audit = None
    if workflow:
        require(sha256(output / 'first.atr') == first_digest, 'Readonly image changed')
        oracle = Audit((output / 'second.atr').read_bytes())
        audit = getattr(oracle, filesystem)()
        require(oracle.files.get('SWAP.BIN') == b'\xaa' * 64 and
                oracle.files.get('NEW.BIN') == bytes(range(1, 65)), 'Wrong persisted image data')
    return dict(status='pass', tier='development', absent=absent, images=images,
                workflow=workflow, filesystem=filesystem if workflow else None,
                sector_bytes=size if workflow else None, audit=audit, checks=checks, build=p['build'],
                machine=machine, runtime=runtime, peer_sha256=sha256(peer),
                command_sha256=sha256(contents / 'FUJI'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/fujinet/fn3')
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--absent', action='store_true')
    parser.add_argument('--images', action='store_true')
    parser.add_argument('--workflow', action='store_true')
    parser.add_argument('--filesystem', choices=('mydos', 'sdfs'), default='mydos')
    parser.add_argument('--size', type=int, choices=(128, 256), default=128)
    args = parser.parse_args()
    require(sum((args.absent, args.images, args.workflow)) <= 1, 'Select one FUJI test scope')
    result = run(args.output.resolve(), args.from_build, args.absent, args.images,
                 args.workflow, args.filesystem, args.size)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('FUJI command workflow passed', result['checks'])
