#!/usr/bin/env python3
"""Native current-directory, lock-name and relative-path slice qualification."""
import argparse
import json
import shutil
from pathlib import Path
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute, ownership
from test_cooperative import data
from ports_budget import current


def directory(t, out, mode, bank=2, removal=False):
    out.mkdir(parents=True, exist_ok=True)
    media = out / 'volume.atr'
    shutil.copyfile(ROOT / 'tests/fixtures/mydos/mydos450-128.atr', media)
    digest = sha256(media)
    names = bytearray(128)
    for offset, name in ((0, b'D1:'), (32, b'D1:TOOLS/SUB'), (64, b'D1:TOOLS/SUB/DATA.BIN'), (96, b'NIL:')):
        names[offset:offset+len(name)] = name
    p = build(t, ROOT / 'tests/programs/dos_current_directory.act', out, optimize=mode == 'opt',
              tasks=True, task_capacity=8, kernel_bank=bank, console=False,
              dos_mounts=[dict(alias='D1', unit=49, sectors=720, sector_bytes=128, profile=1)],
              image_data=[(0xd1000, bytes(names)), (0xe0000, bytes(128))])
    with emulator(ROOT / 'build/altirra-sio-multi', ROOT / 'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        b.config('diskemu', 'fastest'); b.mount(0, str(media))
        def before(b):
            address=next(x['address'] for x in p['image']['data'] if '_REMOVAL_' in x['name'])
            b.poke(address,int(removal))
        try:
            runtime, _ = execute(b, p, before_run=before, expected_status=4 if removal else 0, timeout=240, frame_limit=12000)
        except Exception:
            print('Directory checks:', data(b, p['image'], 'checks', True), flush=True)
            raise
        if not removal: ownership(b, p, out)
        checks = int.from_bytes(bytes(data(b, p['image'], 'checks')), 'little')
        require(data(b, p['image'], 'finished') == [0 if removal else 1], 'Incomplete directory fixture')
        require(runtime['created'] == (2 if removal else 5), 'Unexpected task creation: '+str(runtime['created']))
        require(sha256(media) == digest, 'Read-only media modified')
    return dict(status='pass', build=p['build'], runtime=runtime, machine=machine,
                observations=dict(checks=checks), media_sha256=digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--output', type=Path, default=ROOT/'build/dos-current-directory')
    parser.add_argument('--case', choices=('raw','opt'))
    parser.add_argument('--only')
    parser.add_argument('--record', type=Path)
    args = parser.parse_args()
    t = compiler(args.compiler_dir)
    from test_dos_streams import defaults, fixture
    from test_dos_abi import run as abi
    from test_dos_client import run as client
    from test_dos_files import run as files
    from test_dos_lifetime import run as lifetime
    cases = [('directory-bank1', lambda p,m: directory(t,p,m)),
             ('directory-bank3', lambda p,m: directory(t,p,m,3)),
             ('defaults-bank1', lambda p,m: defaults(t,p,m)),
             ('defaults-bank3', lambda p,m: defaults(t,p,m,3)),
             ('abi', lambda p,m: abi(t,p,m=='opt')),
             ('selected-removal', lambda p,m: directory(t,p,m,removal=True)),
             ('client', lambda p,m: client(t,p,m=='opt')),
             ('lifetime', lambda p,m: lifetime(t,p,m)),
             ('reuse', lambda p,m: client(t,p,m=='opt','reuse')),
             ('files', lambda p,m: files(t,p,m,128,capacity=8,concurrent=True)),
             ('large-read', lambda p,m: fixture(t,p,m,'dos_large_read.act',large=True))]
    report = dict(schema_version=1, status='running', cases=[], bank_zero=current(),
                  memory_delta=dict(bank_zero_fixed=0, bank_zero_per_task=0, client_active=86, client_record=86, client_allocation=88,
                                    previous_client_allocation=80),
                  completion_limits=dict(host_seconds=240, frames=12000, large_read_host_seconds=600, large_read_frames=30000))
    try:
        for mode in ([args.case] if args.case else ('raw','opt')):
            for name, action in cases:
                if args.only and name != args.only: continue
                print('Running', mode, name, flush=True)
                out = args.output / mode / name; out.mkdir(parents=True, exist_ok=True)
                result = action(out, mode); result.update(name=name, mode=mode)
                (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
                report['cases'].append(result)
        require(report['cases'], 'No selected cases')
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error)); raise
    finally:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.record:
        # Retain image/production hashes, machine pin, observations and stack evidence;
        # omit bulky generated maps already hashed by the builder.
        for result in report['cases']:
            result['build'] = {k:v for k,v in result['build'].items() if k in (
                'revision','changes','override','binary_sha256','source_sha256','image_sha256','xex_sha256',
                'optimize','task_inputs','task_generated','abi_sha256','abi_assembly_sha256')}
        args.record.write_text(json.dumps(report,indent=2)+'\n')
    print('Directory qualification passed', flush=True)

if __name__ == '__main__': main()
