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


def run(out, probe=0, replay=False, floating=False,reuse_native=False):
    out.mkdir(parents=True, exist_ok=True)
    previous=(out/'probe.act').read_text() if reuse_native else None
    files = {}
    for name in (('worker','second','busy') if floating else ('worker', 'busy')):
        binary = out/'guest'/f'{name.upper()}.COM'
        basic=ROOT/f'tests/fastbasic/{"fp_" if floating else ""}{name}.bas'
        compile_program(ROOT/'build/fastbasic/source', basic, binary, floating=floating)
        files[binary.name] = binary.read_bytes()
    if floating:
        files['FBC.COM']=(ROOT/'build/fastbasic/FBC.COM').read_bytes()
        files['FRESH.BAS']=b'? 1.25*2.0\x9b'
    files['MD5.COM'] = (ROOT/'build/sdx-inputs/md5/MD5.COM').read_bytes()
    files['ABC.TXT'] = b'abc'
    payload, setup = bytearray(), []
    for name, raw in files.items():
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${0x300000+len(payload):x})),{len(raw)})')
        payload += raw
    source = out/'probe.act'
    text=(ROOT/'tests/programs/fastbasic_lifetime.act').read_text().replace('SETUP_FILES', '\n'.join(setup))
    text=text.replace('SECOND_GUEST','SECOND' if floating else 'WORKER')
    compile_check='''  LET compiler=PROGRAMFILE.Load(BYTE POINTER(c"RAM:FBC.COM"))
  Require(compiler<>NULL)
  secondId=PROCESS.StartBackgroundLoaded(BYTE POINTER(compiler),
      BYTE POINTER(c"RAM:FRESH.BAS RAM:FRESH.COM"),27)
  Require(secondId<>0)
  Wait(secondId,0)
  PROGRAM.Unload(compiler)''' if floating else ''
    source.write_text(text.replace('FLOAT_COMPILER_RUN',compile_check))
    memory = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    memory['image_data_bytes'] = 16384
    config = out/'memory-profile.json'
    config.write_text(json.dumps(memory))
    p = read_build(out) if replay or reuse_native else build(compiler(ROOT/'build/actionc', release=True),
        source, out, tasks=True, task_capacity=8, console=False, console_test=True,
        sdx=True, sdx_return_probe=probe, memory_profile=config,
        image_data=[(0x300000, bytes(payload))], dos_mounts=[dict(alias='RAM', format=3)])
    result = dict(status='running', tier='development', return_probe=probe, build=p['build'],
        floating=floating,inputs={name:hashlib.sha256(raw).hexdigest() for name, raw in files.items()})
    from fastbasic_test_support import guest_inputs
    stimulus=guest_inputs(p,previous,source.read_text(),[(0x300000,bytes(payload))]) if reuse_native else None
    result['reused_native_fixture']=reuse_native
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        result['machine'] = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            result['runtime'], _ = execute(b, p, timeout=150, frame_limit=7500,before_run=stimulus)
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
    parser.add_argument('--float',dest='floating',action='store_true')
    parser.add_argument('--reuse-native',action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.return_probe, args.replay,args.floating,args.reuse_native)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('FastBasic lifetime', result['checks'], 'checks; BREAK', result['breakTicks'], 'ticks')
