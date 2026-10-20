#!/usr/bin/env python3
"""Exercise the source-built 6502 FastBasic runtime and compiler on Exec."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN
from build_fastbasic import compile_program, profile, sha256


def fixture(out, group):
    source = ROOT/'build/fastbasic/source'
    programs = ['hello'] + (['values', 'files', 'clock'] if group == 'all' else [])
    files, calls, expected, corpus = [], [], b'', []
    for index, name in enumerate(programs, 1):
        basic = ROOT/f'tests/fastbasic/{name}.bas'
        binary = out/'guest'/f'{name.upper()}.COM'
        layout = compile_program(source, basic, binary)
        files.append((binary.name, binary.read_bytes()))
        calls.append(f'  currentCase={index}\n  Run(BYTE POINTER(c"RAM:{binary.name}"),NULL,0,0)')
        expected += (ROOT/f'tests/fastbasic/{name}.out').read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\x9b')
        corpus.append(dict(name=name, source_sha256=sha256(basic), binary_sha256=sha256(binary), layout=layout))
    if group=='all':
        binary=out/'guest/STDIN.COM'
        basic=ROOT/'tests/fastbasic/stdin.bas'
        layout=compile_program(source,basic,binary)
        files += [(binary.name,binary.read_bytes()),('INPUT.TXT',b'Z')]
        calls.append('''  LET redirected=DOS.Open(BYTE POINTER(c"RAM:INPUT.TXT"),DOS.MODE_OLDFILE)
  Require(redirected<>NULL)
  LET originalInput=DOS.SelectInput(redirected)
  Run(BYTE POINTER(c"RAM:STDIN.COM"),NULL,0,0)
  DOS.SelectInput(originalInput)
  Require(DOS.Close(redirected)<>0)''')
        expected += b'90\x9b'
        corpus.append(dict(name='stdin',source_sha256=sha256(basic),
                           binary_sha256=sha256(binary),layout=layout))
        binary=out/'guest/ALLOC.COM'
        basic=ROOT/'tests/fastbasic/allocation.bas'
        layout=compile_program(source,basic,binary)
        files.append((binary.name,binary.read_bytes()))
        calls.append('  Run(BYTE POINTER(c"RAM:ALLOC.COM"),NULL,0,20)\n  Require(secondary=103)')
        corpus.append(dict(name='allocation',source_sha256=sha256(basic),
                           binary_sha256=sha256(binary),layout=layout))
    extra = ''
    if group in ('compiler', 'all'):
        files += [('FBCI.COM', (source/'build/bin/fbci.xex').read_bytes()),
                  ('SOURCE.BAS', b'? "ON MACHINE"\r\nA=6\r\n? A*7'),
                  ('BROKEN.BAS', b'IF\x9b')]
        arguments = 'RAM:SOURCE.BAS RAM:FRESH.COM'
        calls.append(f'  currentCase=20\n  Run(BYTE POINTER(c"RAM:FBCI.COM"),BYTE POINTER(c"{arguments}"),{len(arguments)},0)')
        calls.append('  currentCase=21\n  Run(BYTE POINTER(c"RAM:FRESH.COM"),NULL,0,0)')
        expected += b'Compiled RAM:FRESH.COM\x9bON MACHINE\x9b42\x9b'
        if group == 'all':
            arguments = 'RAM:BROKEN.BAS RAM:BAD.COM'
            calls.append(f'''  LET errorFile=DOS.Open(BYTE POINTER(c"RAM:ERROR.TXT"),DOS.MODE_NEWFILE)
  Require(errorFile<>NULL)
  LET normal=DOS.SelectOutput(errorFile)
  currentCase=22
  Run(BYTE POINTER(c"RAM:FBCI.COM"),BYTE POINTER(c"{arguments}"),{len(arguments)},20)
  Require(secondary=306)
  DOS.SelectOutput(normal)
  Require(DOS.Close(errorFile)<>0)
  LET parse=DOS.Open(BYTE POINTER(c"RAM:ERROR.TXT"),DOS.MODE_OLDFILE)
  Require(parse<>NULL)
  parseBytes=CARD(DOS.Read(parse,@parseOutput,256))
  Require(DOS.Close(parse)<>0)
  Require(DOS.Open(BYTE POINTER(c"RAM:BAD.COM"),DOS.MODE_OLDFILE)=NULL)
  currentCase=23
  Run(BYTE POINTER(c"RAM:FRESH.COM"),NULL,0,0)''')
            expected += b'ON MACHINE\x9b42\x9b'
        extra = '''  LET generated=DOS.Open(BYTE POINTER(c"RAM:FRESH.COM"),DOS.MODE_OLDFILE)
  Require(generated<>NULL)
  freshBytes=CARD(DOS.Read(generated,@fresh,4096))
  Require(freshBytes>16 AND freshBytes<4096)
  Require(DOS.Close(generated)<>0)
  ; Structural admission precedes slot ownership and allocation.
  LET saved=fresh(4)
  fresh(4)=99
  Require(PROGRAM.Load(@fresh,LONGCARD(freshBytes))=NULL)
  Require(DOS.IoErr()=307)
  fresh(4)=saved
  Require(PROGRAM.Load(@fresh,LONGCARD(freshBytes)-1)=NULL)
  Require(DOS.IoErr()=306)
  LET first=PROGRAM.Load(@fresh,LONGCARD(freshBytes))
  Require(first<>NULL)
  LET second=PROGRAM.Load(@fresh,LONGCARD(freshBytes))
  Require(second<>NULL)
  LET one=FBSTATE.Session POINTER(first.extension)
  LET two=FBSTATE.Session POINTER(second.extension)
  Require(one.guest.slot<>two.guest.slot AND one.guest.bank<>two.guest.bank)
  Require(PROGRAM.Load(@fresh,LONGCARD(freshBytes))=NULL)
  Require(DOS.IoErr()=308)
  PROGRAM.Unload(second)
  PROGRAM.Unload(first)
'''
    payload = bytearray()
    setup = []
    for name, raw in files:
        at = 0x300000+len(payload)
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${at:x})),{len(raw)})')
        payload += raw
    probe = out/'probe.act'
    probe.write_text((ROOT/'tests/programs/fastbasic.act').read_text()
                     .replace('SETUP_FILES', '\n'.join(setup))
                     .replace('RUN_PROGRAMS', '\n'.join(calls)).replace('EXTRA_CHECKS', extra))
    return probe, [(0x300000, bytes(payload))], expected, corpus


def run(out, group, replay=False, optimize=True):
    out.mkdir(parents=True, exist_ok=True)
    probe, payload, expected, corpus = fixture(out, group)
    memory_profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    memory_profile['image_data_bytes'] = 24576
    memory = out/'memory-profile.json'
    memory.write_text(json.dumps(memory_profile))
    p = read_build(out) if replay else build(compiler(ROOT/'build/actionc', release=True),
        probe, out, optimize=optimize, tasks=True, task_capacity=8, console=False, console_test=True,
        sdx=True, image_data=payload, memory_profile=memory,
        dos_mounts=[dict(alias='RAM', format=3)])
    result = dict(status='running', tier='development', group=group, optimize=optimize, build=p['build'], pin=PIN,
                  corpus=corpus, fastbasic=json.loads((ROOT/'build/fastbasic/build.json').read_text()))
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        result['machine'] = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            result['runtime'], _ = execute(b, p, timeout=120, frame_limit=6000)
        except Exception:
            b.bp_clear_all()
            print('FastBasic failure', {k:data(b, p['image'], k, True) for k in
                  ('checks', 'currentCase', 'reason', 'primary', 'secondary', 'guestBank')},
                  b.regs(), flush=True)
            bank = int.from_bytes(bytes(data(b, p['image'], 'guestBank')), 'little')
            if bank:
                (out/'failed-guest.bin').write_bytes(b.memdump(bank, 65536))
            raise
        ownership(b, p, p['output'])
        count = int.from_bytes(bytes(data(b, p['image'], 'actualBytes')), 'little')
        actual = bytes(data(b, p['image'], 'actual'))[:count]
        print('FastBasic output', repr(actual), flush=True)
        require(actual == expected, f'Wrong output: {actual!r} != {expected!r}')
        if group in ('compiler', 'all'):
            generated_bytes = int.from_bytes(bytes(data(b, p['image'], 'freshBytes')), 'little')
            generated = bytes(data(b, p['image'], 'fresh'))[:generated_bytes]
            result['generated_profile'] = profile(generated)
            (out/'FRESH.COM').write_bytes(generated)
        if group == 'all':
            count = int.from_bytes(bytes(data(b, p['image'], 'parseBytes')), 'little')
            diagnostic = bytes(data(b, p['image'], 'parseOutput'))[:count]
            require(b'at line 1' in diagnostic and b'column' in diagnostic, repr(diagnostic))
            result['parse_error_hex'] = diagnostic.hex()
        result.update(status='pass', actual_hex=actual.hex(),
                      session_bytes=int.from_bytes(bytes(data(b, p['image'], 'stateBytes')), 'little'),
                      checks=int.from_bytes(bytes(data(b, p['image'], 'checks')), 'little'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--group', choices=('runtime', 'compiler', 'all'), default='all')
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--raw', action='store_true', help='Focused unoptimized ABI check; use --group runtime')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.group, args.replay, not args.raw)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
