#!/usr/bin/env python3
"""Two BASIC guests, native peer, SDX coexistence, BREAK and image relaunch."""
import argparse
import hashlib
import json
from pathlib import Path

from build_fastbasic import compile_program, sha256
from native_program import ROOT, build, compiler, read_build, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN


def run(out, probe=0, replay=False):
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in ('worker', 'busy'):
        binary = out/'guest'/f'{name.upper()}.COM'
        compile_program(ROOT/'build/fastbasic/source', ROOT/f'tests/fastbasic/{name}.bas', binary)
        files[binary.name] = binary.read_bytes()
    files['MD5.COM'] = (ROOT/'build/sdx-inputs/md5/MD5.COM').read_bytes()
    files['ABC.TXT'] = b'abc'
    payload, setup = bytearray(), []
    for name, raw in files.items():
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${0x300000+len(payload):x})),{len(raw)})')
        payload += raw
    source = out/'probe.act'
    source.write_text((ROOT/'tests/programs/fastbasic_lifetime.act').read_text().replace('SETUP_FILES', '\n'.join(setup)))
    memory = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    memory['image_data_bytes'] = 16384
    config = out/'memory-profile.json'
    config.write_text(json.dumps(memory))
    p = read_build(out) if replay else build(compiler(ROOT/'build/actionc', release=True),
        source, out, tasks=True, task_capacity=8, console=False, console_test=True,
        sdx=True, sdx_return_probe=probe, memory_profile=config,
        image_data=[(0x300000, bytes(payload))], dos_mounts=[dict(alias='RAM', format=3)])
    result = dict(status='running', tier='development', return_probe=probe, build=p['build'],
        inputs={name:hashlib.sha256(raw).hexdigest() for name, raw in files.items()})
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        result['machine'] = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            result['runtime'], _ = execute(b, p, timeout=150, frame_limit=7500)
        except Exception:
            print({k:data(b, p['image'], k, True) for k in
                  ('checks', 'currentCase', 'primary', 'secondary', 'reason', 'breakTicks')}, flush=True)
            raise
        ownership(b, p, out)
        for name in ('checks', 'breakTicks', 'firstProgress', 'secondProgress'):
            result[name] = int.from_bytes(bytes(data(b, p['image'], name)), 'little')
        actual = bytes(data(b, p['image'], 'actual'))
        require(actual[:21] == b'WORKER\x9b'*3, repr(actual[:21]))
        expected = b'WORKER\x9bMD5 (ABC.TXT) = '+hashlib.md5(b'abc').hexdigest().upper().encode()+b'\x9b'
        require(actual[32:32+len(expected)] == expected, repr(actual[32:]))
    result['status'] = 'pass'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--return-probe', type=int, choices=(0, 7), default=0)
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.return_probe, args.replay)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('FastBasic lifetime', result['checks'], 'checks; BREAK', result['breakTicks'], 'ticks')
