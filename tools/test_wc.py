#!/usr/bin/env python3
"""Focused raw/optimized native WC checks with controlled input/error streams."""
import argparse
import json
import struct
from pathlib import Path
from library_paths import read_source

from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def cases():
    return [
        dict(name='empty', pattern=b'', length=0),
        dict(name='unterminated', pattern=b'one two', length=7),
        dict(name='ascii-space', pattern=b' \t\v\f\r\n', length=6),
        dict(name='mixed-lines', pattern=b'a\r\nb\rc\nd\x9be', length=10),
        dict(name='binary-bytes', pattern=b'\x00\xff\x80 \x9b', length=5),
        dict(name='split-crlf', pattern=b'\r\n', length=1026, chunk=1),
        dict(name='split-word', pattern=b'x', length=1025),
        dict(name='partial-reads', pattern=b'abc def\n', length=1031, chunk=7),
        dict(name='wide-bytes', pattern=b'x', length=65537),
        dict(name='wide-lines-words', pattern=b'x\n', length=131074),
        dict(name='arguments', pattern=b'x', length=1, arguments=1, cause=118),
        dict(name='read-error', pattern=b'x', length=1024, read_failure=2, cause=226),
        dict(name='write-error', pattern=b'x\n', length=2, write_error=214, cause=214),
        dict(name='break-before-read', pattern=b'x', length=1024, break_after=0, cause=304),
        dict(name='break-between-reads', pattern=b'x', length=1024, break_after=512, cause=304),
        dict(name='break-at-eof', pattern=b'x', length=512, break_after=512, cause=304),
    ]


def expected(case):
    if case.get('cause'):
        return b''
    pattern, length = case['pattern'], case['length']
    payload = (pattern*((length+len(pattern)-1)//len(pattern)))[:length] if pattern else b''
    # Independent whole-input semantics: normalize only line delimiters for
    # counting, leaving the byte total and the original fixture bytes intact.
    lines = payload.replace(b'\r\n', b'\n').replace(b'\r', b'\n').replace(b'\x9b', b'\n').count(b'\n')
    words = len(payload.replace(b'\x9b', b' ').split())
    return f'{lines} {words} {length}\n'.encode()


def command_source(text):
    text=text.replace('\r\n','\n')
    require(text.count('LONGINT FUNC Main()')==1,'Missing command entry')
    return text.replace('LONGINT FUNC Main()','LONGINT FUNC CountInput()')


def run(out, mode, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    (out/'command.act').write_text(read_source(ROOT/'tests/programs/wc_stream.act'))
    source = command_source((ROOT/'examples/commands/wc.act').read_text())
    # The command body and its helpers are unchanged; the fixture calls the
    # entry repeatedly against the local stream implementation.
    source = source.replace('ENDMODULE', '')
    source = source.replace('USE COMMAND', 'USE COMMAND\nUSE EXECPOLICY', 1)
    source = source.replace('USE CSTRING AS STR', 'USE CSTRING.IMPL AS STR', 1)
    source += '''
TYPE Observation=[LONGINT primary,secondary CARD used BYTE ARRAY output(33)]
TYPE Scenario=[LONGCARD length,breakAfter LONGINT writeError CARD chunk,argumentBytes,readFailure,patternLength BYTE ARRAY pattern(16)]
Observation ARRAY observations(16)
CARD rowBytes,scenarioBytes,digits
BYTE finished
PROC Main()
  CARD index,which
  Scenario POINTER testCase
  rowBytes=SIZEOF(Observation)
  scenarioBytes=SIZEOF(Scenario)
  FOR which=0 TO 15 DO
    testCase=Scenario POINTER(ADDRESS($e0000)+SIZE(which*SIZEOF(Scenario)))
    COMMAND.length=testCase.length COMMAND.breakAfter=testCase.breakAfter
    COMMAND.writeError=testCase.writeError COMMAND.chunk=testCase.chunk
    COMMAND.argumentBytes=testCase.argumentBytes COMMAND.readFailure=testCase.readFailure
    COMMAND.patternLength=testCase.patternLength
    FOR index=0 TO 15 DO COMMAND.pattern(index)=testCase.pattern(index) OD
    COMMAND.Reset() COMMAND.primary=CountInput() COMMAND.secondary=COMMAND.IoErr()
    observations(which).primary=COMMAND.primary observations(which).secondary=COMMAND.secondary
    observations(which).used=COMMAND.outputBytes
    FOR index=0 TO 32 DO observations(which).output(index)=COMMAND.captured(index) OD
  OD
  digits=STR.u32toa($ffffffff,report,SIZEOF(report)) finished=1
RETURN
ENDMODULE
'''
    vectors = cases()
    blob = b''.join(struct.pack('<IIiHHHH16s', c['length'], c.get('break_after', 0xffffffff),
                               c.get('write_error', 0), c.get('chunk', 512), c.get('arguments', 0),
                               c.get('read_failure', 0), len(c['pattern']), c['pattern']) for c in vectors)
    fixture = out/'wc_probe.act'
    fixture.write_text(source)
    p = read_build(out) if reuse else build(compiler(ROOT/'build/actionc'), fixture, out, optimize=mode=='opt',
                                          banked=True, console=False, image_data=[(0xe0000, blob)])
    require(p['build']['optimize'] == (mode == 'opt') and p['build']['source_sha256'] == sha256(fixture),
            'Replay does not match the requested fixture')
    require(any(s['address'] == 0xe0000 and bytes(s['bytes']) == blob for s in p['image']['segments']),
            'Replay vectors differ from the built image')
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer') == PIN['emulator']['sha256'],
            'Unpinned emulator binary')
    require(sha256(ROOT/'build/firmware/altirraos-816.rom') == PIN['rom']['sha256'], 'Unpinned ROM')
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        for name, value in PIN['configuration'].items():
            b.config(name, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        runtime, _ = execute(b, p, timeout=120, frame_limit=6000)
        require(data(b, p['image'], 'finished') == [1], 'WC cases did not finish')
        require(data(b, p['image'], 'scenarioBytes', True) == [36], 'Scenario layout mismatch')
        stride = int.from_bytes(bytes(data(b, p['image'], 'rowBytes')), 'little')
        rows = bytes(data(b, p['image'], 'observations'))
        for i, case in enumerate(vectors):
            row = rows[i*stride:(i+1)*stride]
            outcome = tuple(int.from_bytes(row[j:j+4], 'little', signed=True) for j in (0, 4))
            cause = case.get('cause', 0)
            require(outcome == (10 if cause else 0, cause), 'WC result: '+case['name'])
            payload = expected(case)
            require(int.from_bytes(row[8:10], 'little') == len(payload), 'WC output size: '+case['name'])
            require(row[10:43] == payload+b'\xa5'*(33-len(payload)), 'WC output: '+case['name'])
        require(data(b, p['image'], 'digits', True) == [10], 'Wide decimal length')
        require(bytes(data(b, p['image'], 'report'))[:10] == b'4294967295', 'Wide unsigned decimal output')
        require(data(b, p['image'], 'report')[10] == 0, 'Wide decimal terminator')
    return dict(status='pass', tier='development', mode=mode, cases=[dict(c, pattern=c['pattern'].hex(), expected=expected(c).decode()) for c in vectors],
                build=p['build'], runtime=runtime, machine=machine, pin=PIN,
                source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in
                               (ROOT/'examples/commands/wc.act', ROOT/'tests/programs/wc_stream.act', ROOT/'lib/dos/dosargs.act', Path(__file__))},
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true', help='Run the matching frozen native image again')
    args = parser.parse_args()
    result = run(args.output.resolve(), args.case, args.reuse)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('WC native checks passed:', args.case, len(result['cases']))
