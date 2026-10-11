#!/usr/bin/env python3
"""Actual INFO body, parser, formatting and WriteAll on controlled native I/O."""
import argparse
import json
import struct
from pathlib import Path

from library_paths import read_source
from native_program import ROOT, build, compiler, execute, require, verify_machine, sha256
from os_boundary import emulator
from test_cooperative import data
from test_toolbox import fixture, PIN, STRIDE


def record(name, label='', format=2, backend=1, readonly=0, state=1,
           flags=1, unit=1, size=512, total=1440, free=1000, allocated=0):
    return struct.pack('<32s9s5B2H3I', name.encode(), label.encode(), format,
                       backend, readonly, state, flags, unit, size, total, free, allocated)


def vectors():
    sys = record('SYSTEM', 'SYS', readonly=1)
    work = record('WORK', 'WORK', unit=2)
    ram = record('RAM', format=3, flags=2, unit=0, size=0, total=0, free=0, allocated=1142)
    sysout = b'SYSTEM: (SYS)\n  Size 720K Used 220K Free 500K RO\n  SpartaDOS 512B ideplus.device/1\n'
    workout = b'WORK: (WORK)\n  Size 720K Used 220K Free 500K RW\n  SpartaDOS 512B ideplus.device/2\n'
    ramout = b'RAM:\n  Size dynamic Used 1K Free - RW\n  RAM, volatile\n'
    allout = sysout+workout+ramout
    def c(name, args=b'', expected=b'', records=(sys, work, ram), **extra):
        return dict(name=name, args=args, expected=expected, payload=b''.join(records),
                    entries=len(records), **extra)
    offline = record('WORK', unit=2, state=2)
    offlineout = b'WORK:\n  Size - Used - Free - RW\n  SpartaDOS 512B ideplus.device/2\n'
    blank = bytes(62)
    cases = [c('all', expected=allout, opens=3),
             c('named', b'WORK:', workout, opens=1),
             c('assign', b'C:', sysout, opens=1),
             c('relative', b'.', sysout, opens=1),
             c('ram', b'RAM:', ramout, opens=1),
             c('empty', expected=b'No mounted volumes\n', records=()),
             c('sparse', expected=sysout+ramout, records=(sys, blank, ram), opens=2),
             c('offline', expected=sysout+offlineout+b'  Volume not mounted (218)\n'+ramout,
               records=(sys, offline, ram), opens=2, status=5),
             c('mixed-error', expected=sysout+b'WORK:\n  Size - Used - Free - RW\n'
               b'  SpartaDOS 512B ideplus.device/2\n  No disk or disk I/O failure (226)\n'+ramout,
               records=(sys, record('WORK', unit=2), ram), opens=3,
               enumerationError=226, closeError=202, error=226),
             c('named-error', b'WORK:', opens=1, enumerationError=226, closeError=202, error=226),
             c('missing', b'MISSING', error=205),
             c('break', breakAt=0, error=304),
             c('query-break', records=(sys, work), expected=sysout,
               opens=2, enumerationError=304, error=304),
             c('break-after-query', opens=1, breakAt=1, error=304),
             c('partial-write', b'WORK:', workout, opens=1, writeChunk=1),
             c('output-error', b'WORK:', opens=1, writeFail=1, error=214),
             c('zero-write', b'WORK:', opens=1, writeChunk=0, error=206),
             c('max-counts', b'C:', b'SYSTEM:\n  Size 32767K Used 7767K Free 25000K RW\n'
               b'  SpartaDOS 512B ideplus.device/1\n',
               records=(record('SYSTEM', total=65535, free=50000),), opens=1),
             c('mydos', b'C:', b'D1:\n  Size 90K Used 27K Free 62K RW\n  MyDOS 128B sio.device/D1\n',
               records=(record('D1', format=1, backend=0, unit=49, size=128, total=720, free=500),), opens=1),
             c('long-label', b'C:', b'ABCDEFGHIJKLMNOPQRSTUVWXYZ12345:\n(ABCDEFGH)\n'
               b'  Size 720K Used 220K Free 500K RW\n  SpartaDOS 512B ideplus.device/1\n',
               records=(record('ABCDEFGHIJKLMNOPQRSTUVWXYZ12345', 'ABCDEFGH'),), opens=1)]
    for name, args, extra in [
            ('help', b'?', {}), ('help-spaces', b' \t?\t ', {}),
            ('help-no-console', b'?', dict(interactive=0, opens=0, error=212, consoleExpected=b'')),
            ('help-write-error', b'?', dict(writeFail=1, error=214, consoleExpected=b'')),
            ('help-close-error', b'?', dict(closeError=202, error=202)),
            ('help-break', b'?', dict(breakAt=0, error=304, consoleExpected=b''))]:
        case = c(name, args, interactive=1, opens=1, consoleExpected=b'Arguments: VOLUME\n')
        case.update(extra)
        cases.append(case)
    return cases


def run(output, mode):
    cases = vectors()
    path, blob = fixture(output, 'info', cases, faults=True)
    calls = read_source(output/'doscalls.act').replace('USE TOOLBOXSTATE AS T',
                                                      'USE TOOLBOXSTATE AS T\nUSE A816MEMORY')
    calls = calls[:calls.index('PUBLIC LONGINT FUNC GetVolume(')]+calls[calls.index('PUBLIC BYTE POINTER FUNC Selected('):]
    first = calls.index('PUBLIC BYTE POINTER FUNC Lock(')
    last = calls.index('PUBLIC LONGINT FUNC Information(')
    calls = calls[:first]+read_source(ROOT/'tests/programs/info_calls.inc')+'\n'+calls[last:]
    (output/'doscalls.act').write_text(calls)
    for module, routine in [('DOSRAW', 'ValidExtent'), ('FSNAMES', 'Mapped')]:
        (output/(module.lower()+'.act')).write_text(f'''MODULE {module}
PUBLIC BYTE FUNC {routine}(BYTE POINTER buffer LONGINT length)
RETURN(buffer<>NULL AND ADDRESS(buffer)>=ADDRESS($10000) AND length>0)
ENDMODULE
''')
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 8192
    (output/'profile.json').write_text(json.dumps(profile))
    p = build(compiler(ROOT/'build/actionc', release=True), path, output,
              optimize=mode == 'opt', banked=True, console=False,
              memory_profile=output/'profile.json',
              image_data=[(0x300000, blob), (0x200000, bytes(STRIDE*len(cases)))])
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        runtime, _ = execute(b, p, timeout=180, frame_limit=9000)
        require(data(b, p['image'], 'finished') == [1], 'INFO did not finish')
        require(data(b, p['image'], 'rowBytes', True) == [STRIDE], 'INFO result layout')
        require(data(b, p['image'], 'scenarioBytes', True)[0]*len(cases) == len(blob), 'Scenario layout')
        rows = b.memdump(0x200000, STRIDE*len(cases))
        for i, c in enumerate(cases):
            row = rows[i*STRIDE:(i+1)*STRIDE]
            primary, error, used, consoleUsed, opens, closes, reads, writes = struct.unpack('<ii6H', row[:20])
            require((primary, error) == (c.get('status', 10 if c.get('error') else 0), c.get('error', 0)),
                    f'{c["name"]}: result {(primary, error)}')
            require(row[20:20+used] == c['expected'], f'{c["name"]}: output {row[20:20+used]!r}')
            require(opens == closes == c.get('opens', 0), f'{c["name"]}: lock/handle leak {(opens, closes)}')
            require(reads == 0, 'INFO consumed input data')
            if 'consoleExpected' in c:
                require(row[4116:4116+consoleUsed] == c['consoleExpected'], 'INFO help console')
            require(all(len(line) <= 40 for line in c['expected'].splitlines()), 'INFO exceeds standard width')
    result = dict(status='pass', tier='development', mode=mode, cases=[c['name'] for c in cases],
                  build=p['build'], runtime=runtime, machine=machine,
                  bank_zero_delta=dict(fixed=0, per_task=0, idle=0),
                  source_inputs={str(f.relative_to(ROOT)):sha256(f) for f in
                      (Path(__file__), ROOT/'examples/commands/info.act', ROOT/'tests/programs/info_calls.inc')})
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('INFO command passed', mode, len(cases), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.case)
