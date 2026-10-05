#!/usr/bin/env python3
"""Read original-DOS-modified media through Exec and compare every file byte."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, require, verify_machine, sha256
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute
from test_heap_api import clean_ownership
from filesystem_audit import Audit
from test_filesystem_write import reuse
from generate_dos_mounts import encode


def run(output, mode, filesystem, media, from_build=None):
    audit = Audit(media.read_bytes())
    getattr(audit, filesystem)()
    paths, contents = bytearray(72*len(audit.files)), bytearray()
    for index, (name, payload) in enumerate(sorted(audit.files.items())):
        path = ('D1:' + name).encode() + b'\0'
        require(len(path) <= 64 and len(payload) < 65536, 'Roundtrip fixture limits')
        row = index*72
        paths[row:row+len(path)] = path
        paths[row+64:row+68] = len(payload).to_bytes(2, 'little') + len(contents).to_bytes(2, 'little')
        contents.extend(payload)
    require(len(contents) < 65536, 'Roundtrip expected arena full')
    mounts = [dict(alias='D1', unit=49, sectors=audit.image.count,
                   sector_bytes=audit.image.size, format=1 if filesystem == 'mydos' else 2)]
    program = reuse(from_build) if from_build else build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/filesystem_roundtrip.act', output,
                    optimize=mode == 'opt', tasks=True, console_deferred=True,
                    dos_mounts=mounts,
                    image_data=[(0xd1000, bytes(paths)), (0xe0000, bytes(contents))])
    before_hash = sha256(media)
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        configuration = {**PIN['configuration'], 'diskemu': 'fastest', 'accuratedisk': False}
        for key, value in configuration.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)

        def before(bridge):
            bridge.mount(0, str(media))
            bridge.memload(program['build']['task_storage']['BASE'] + 0x900, encode(mounts))
            bridge.memload(0xd1000, bytes(paths))
            bridge.memload(0xe0000, bytes(contents))
            address = next(d['address'] for d in program['image']['data'] if '_FSROUNDTRIP_COUNT_' in d['name'])
            bridge.memload(address, len(audit.files).to_bytes(2, 'little'))

        runtime, _ = execute(bridge, program, before_run=before, timeout=900, frame_limit=50000)
        clean_ownership(bridge, program, program['output'])
    require(sha256(media) == before_hash, 'Readback changed media')
    return dict(status='pass', build=program['build'], runtime=runtime, configuration=configuration,
                machine=machine, media_sha256=before_hash,
                files={name: len(content) for name, content in audit.files.items()},
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--filesystem', choices=('mydos', 'sdfs'), required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(output, args.case, args.filesystem, args.image.resolve(), args.from_build)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Exec native-DOS roundtrip passed', args.filesystem)
