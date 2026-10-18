#!/usr/bin/env python3
"""Native Task tests for SDX identification and transactional patch application.

No guest is launched. Optimized is the development default; --case raw checks
the small compiler-facing CRC call/record-layout fixture independently.
"""
import argparse
import json
from pathlib import Path
import time

from native_program import ROOT, build, compiler, verify_machine
from os_boundary import emulator
from sdx_file import parse, place
from sdx_patch import manifests, prepare, select
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import module_files, PIN


def fixture(out, files, smoke):
    catalog = manifests(ROOT/'compat/sdx')
    ids = json.loads((ROOT/'abi/sdx.json').read_text())['modules']
    payload = bytearray()
    origin = 0x28fff0
    code = []

    def store(raw):
        address = origin+len(payload)
        payload.extend(raw)
        return f'BYTE POINTER(ADDRESS(${address:x}))'

    def emit(text):
        code.append(text)

    check = store(b'123456789')
    emit(f'''  Require(SDXCRC32.Update({check},0,$ffffffff)=$ffffffff)
  Require(SDXCRC32.Update({check},9,$ffffffff)=$340bc6d9)
  state=SDXCRC32.Update({check},4,$ffffffff)
  state=SDXCRC32.Update(BYTE POINTER(ADDRESS(${origin+4:x})),5,state)
  Require(state=$340bc6d9)''')
    for name, path in files.items():
        raw = path.read_bytes()
        select(raw, catalog)
        ptr = store(raw)
        emit(f'''  bytes={ptr}
  Require(SDXIDENTIFY.Select(bytes,{len(raw)})={ids[name]})
  saved=bytes({len(raw)-1})
  bytes({len(raw)-1})=saved XOR 1
  Require(SDXIDENTIFY.Select(bytes,{len(raw)})=0)
  bytes({len(raw)-1})=saved
  Require(SDXIDENTIFY.Select(bytes,{len(raw)-1})=0)''')
    placements = (0x2000,) if smoke else (0x2000, 0x4100)
    cases = []
    for name in ('MD5.COM', 'ARC.COM'):
        raw = files[name].read_bytes()
        program = parse(raw)
        symbols = {n: 0xe000+i*16 for i, n in enumerate(program.imports)}
        for base in placements:
            original, layout = place(program, base, 0x8000, symbols)
            patched = prepare(raw, catalog, base, 0x8000, symbols)
            ptr = store(original[base:layout['end']])
            emit(f'  Copy(@bank(${base:x}),{ptr},{layout["end"]-base})')
            for i, patch in enumerate(patched.record['patches']):
                before, after = bytes.fromhex(patch['before']), bytes.fromhex(patch['after'])
                expected, replacement = store(before), store(after)
                emit(f'''  patches({i}).offset=${patch['address']:x}
  patches({i}).length={len(before)}
  patches({i}).expected={expected}
  patches({i}).replacement={replacement}''')
            count = len(patched.record['patches'])
            emit(f'''  Require(SDXPATCH.Apply(bank,@patches,{count})=SDXCATALOG.ERROR_OK)
  Require(SDXPATCH.Apply(bank,@patches,{count})=SDXCATALOG.ERROR_PREIMAGE)''')
            target = store(patched.image[base:layout['end']])
            emit(f'  Require(Equal(@bank(${base:x}),{target},{layout["end"]-base})<>0)')
            cases.append(patched.record | dict(placement=base))
    # Two patches: second failure must leave the first untouched. Probe both
    # disjoint spans at bank edges, overlap, capacity and overflow rejection.
    first, second = store(b'\xa5'), store(b'\xea')
    emit(f'''  patches(0).offset=0
  patches(0).length=1
  patches(0).expected={first}
  patches(0).replacement={second}
  patches(1).offset=65535
  patches(1).length=1
  patches(1).expected={first}
  patches(1).replacement={second}
  bank(0)=$a5
  bank(65535)=$5a
  Require(SDXPATCH.Apply(bank,@patches,2)=SDXCATALOG.ERROR_PREIMAGE)
  Require(bank(0)=$a5 AND bank(65535)=$5a)
  bank(65535)=$a5
  patches(1).length=2
  Require(SDXPATCH.Apply(bank,@patches,2)=SDXCATALOG.ERROR_PLAN)
  patches(1).offset=0
  patches(1).length=1
  Require(SDXPATCH.Apply(bank,@patches,2)=SDXCATALOG.ERROR_PLAN)
  patches(1).offset=65535
  Require(SDXPATCH.Apply(bank,@patches,SDXCATALOG.PATCH_LIMIT+1)=SDXCATALOG.ERROR_PLAN)
  Require(bank(0)=$a5 AND bank(65535)=$a5)
  Require(SDXPATCH.Apply(bank,@patches,2)=SDXCATALOG.ERROR_OK)
  Require(bank(0)=$ea AND bank(65535)=$ea)
  patches(0).length=0
  Require(SDXPATCH.Apply(bank,@patches,1)=SDXCATALOG.ERROR_PLAN)
  Require(SDXPATCH.Apply(bank,@patches,0)=SDXCATALOG.ERROR_OK)
  Require(SDXIDENTIFY.Select(bank,65537)=0)
  Require(SDXIDENTIFY.Select(bank,0)=0)
  Require(SDXIDENTIFY.Select(bank,65536)=0)''')
    source = out/'probe.act'
    source.write_text('''MODULE SDXNATIVEPROBE
USE EXEC
USE HEAPCORE
USE SDXCRC32
USE SDXIDENTIFY
USE SDXCATALOG
USE SDXPATCH

LONGCARD checks,state
BYTE saved
BYTE POINTER bank,bytes
SDXPATCH.Patch ARRAY patches(2)

PROC Require(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($f700+CARD(checks & 255))
  FI
  checks==+1

RETURN

PROC Copy(BYTE POINTER target,source CARD length)
  CARD index

  index=0
  WHILE index<length DO
    target(index)=source(index)
    index==+1
  OD

RETURN

BYTE FUNC Equal(BYTE POINTER first,second CARD length)
  CARD index

  index=0
  WHILE index<length DO
    IF first(index)<>second(index) THEN
      RETURN(0)
    FI
    index==+1
  OD

RETURN(1)

PROC Main()

  bank=BYTE POINTER(ADDRESS($300000))
'''+ '\n'.join(code)+'\n\nRETURN\n\nENDMODULE\n')
    return source, [(origin, bytes(payload)), (0x300000, bytes([0xa5])*65536)], cases


def run(out, mode, files):
    out.mkdir(parents=True, exist_ok=True)
    source, image_data, cases = fixture(out, files, mode == 'raw')
    toolchain = compiler(ROOT/'build/actionc', release=True)
    program = build(toolchain, source, out, optimize=mode == 'opt', tasks=True,
                    task_capacity=8, console=False, sdx_patches=True, image_data=image_data)
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(b, program, timeout=120, frame_limit=6000)
        except Exception:
            print('SDX checks before failure:', data(b, program['image'], 'checks'), flush=True)
            raise
        ownership(b, program, out)
        checks = int.from_bytes(bytes(data(b, program['image'], 'checks')), 'little')
    return dict(status='pass', mode=mode, tier='development', checks=checks, runtime=runtime,
                machine=machine, build=program['build'], cases=cases,
                bank_zero_delta=dict(fixed=0, per_task=0),
                scope='Native CRC ABI, file identification and patch transaction; no guest admission')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--md5', type=Path, default=ROOT/'build/sdx-inputs/md5')
    parser.add_argument('--arc', type=Path, default=ROOT/'build/sdx-inputs/arc')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    started = time.monotonic()
    try:
        result = run(out, args.case, module_files(args.md5, args.arc))
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        result['seconds'] = round(time.monotonic()-started, 3)
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('SDX native:', args.case, result['checks'], 'checks passed', flush=True)


if __name__ == '__main__':
    main()
