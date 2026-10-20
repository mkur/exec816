#!/usr/bin/env python3
"""Exercise the source-built 6502 FastBasic runtime and compiler on Exec."""
import argparse
import json
from pathlib import Path
import re
import struct
from decimal import Decimal

from native_program import ROOT, build, compiler, read_build, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN
from build_fastbasic import compile_program, profile, sha256


def decimal_nmi_probe(binary):
    """One-shot test-only WAI after SED; the real VBI must resume decimal math."""
    raw=bytearray(binary.read_bytes())
    layout=profile(raw)
    labels={name:int(address,16) for address,name in re.findall(
        r'al ([0-9A-Fa-f]+) \.(\S+)',binary.with_suffix('.lbl').read_text())}
    address=labels['fb_ifp']
    offset=address-0x2ff0
    original=bytes(raw[offset:offset+3])
    require(original==bytes.fromhex('f8a2d6'),'Changed IFP decimal entry')
    # Preserve all linked BSS homes before adding the diagnostic trampoline.
    segments=binary.with_suffix('.map').read_text()
    bss=re.search(r'^BSS\s+([0-9A-F]+)\s+([0-9A-F]+)',segments,re.M)
    at=max(layout['end'],int(bss[2],16)+1 if bss else layout['end'])
    code=bytearray()
    for index,value in enumerate(original):
        code+=bytes((0xa9,value,0x8d))+struct.pack('<H',address+index)
    marker=at+28
    code+=bytes((0xa9,1,0x8d))+struct.pack('<H',marker)
    code+=bytes.fromhex('f8cba2d6')+b'\x4c'+struct.pack('<H',address+3)
    require(len(code)<=28,'Decimal probe marker overlap')
    code+=bytes(29-len(code))
    raw+=bytes(at-layout['end'])+code
    raw[offset:offset+3]=b'\x4c'+struct.pack('<H',at)
    struct.pack_into('<H',raw,10,at+len(code))
    binary.write_bytes(raw)
    return dict(entry=address,trampoline=at,marker=marker,kind='One-shot SED/WAI with real VBI')


def snapshot_probe(binary):
    """Test-only RND input snapshots: unsigned zero, then UINT32_MAX."""
    raw=bytearray(binary.read_bytes())
    layout=profile(raw)
    labels={name:int(address,16) for address,name in re.findall(
        r'al ([0-9A-Fa-f]+) \.(\S+)',binary.with_suffix('.lbl').read_text())}
    address=labels['EXE_FP_RND']+3
    offset=address-0x2ff0
    require(raw[offset:offset+3]==bytes.fromhex('2080f9'),'Changed RND snapshot site')
    bss=re.search(r'^BSS\s+([0-9A-F]+)\s+([0-9A-F]+)',binary.with_suffix('.map').read_text(),re.M)
    at=max(layout['end'],int(bss[2],16)+1 if bss else layout['end'])
    marker=at+21
    code=bytearray(b'\xad'+struct.pack('<H',marker)+bytes.fromhex('49ff8d')+struct.pack('<H',marker))
    for index in range(4):code+=b'\x8d'+struct.pack('<H',0x700+index)
    code+=b'\x60\xff'
    require(len(code)==22,'Snapshot probe layout')
    raw+=bytes(at-layout['end'])+code
    raw[offset:offset+3]=b'\x20'+struct.pack('<H',at)
    struct.pack_into('<H',raw,10,at+len(code))
    binary.write_bytes(raw)
    return dict(entry=address,marker=marker,kind='Test-only fixed RND snapshots 0 / UINT32_MAX')


def fixture(out, group, floating=False, decimal_probe=False):
    source = ROOT/'build/fastbasic/source'
    programs = (['fp_math'] if floating else ['hello']) + (
        ['fp_values', 'files', 'fp_clock'] if floating and group == 'all' else
        ['values', 'files', 'clock'] if group == 'all' else [])
    if group=='edges':
        require(floating,'The numeric edge group requires --float')
        programs=['fp_edges']
    files, calls, expected, corpus = [], [], b'', []
    completion=''
    for index, name in enumerate(programs, 1):
        basic = ROOT/f'tests/fastbasic/{name}.bas'
        binary = out/'guest'/f'{name.replace("_", "").upper()}.COM'
        layout = compile_program(source, basic, binary, floating=floating)
        numeric_injection=None
        if group=='edges':
            numeric_injection=snapshot_probe(binary)
            layout=profile(binary.read_bytes())
        if decimal_probe and index==1:
            injection=decimal_nmi_probe(binary)
            completion=f'IF currentCase=1 THEN\n    Require(state.guest.bank(${injection["marker"]:x})=1)\n  FI'
            layout=profile(binary.read_bytes())
        files.append((binary.name, binary.read_bytes()))
        calls.append(f'  currentCase={index}\n  Run(BYTE POINTER(c"RAM:{binary.name}"),NULL,0,0)')
        expected += (ROOT/f'tests/fastbasic/{name}.out').read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\x9b')
        corpus.append(dict(name=name, source_sha256=sha256(basic), binary_sha256=sha256(binary), layout=layout,
                           decimal_probe=injection if decimal_probe and index==1 else None,
                           numeric_snapshot_probe=numeric_injection))
    if group=='all':
        binary=out/'guest/STDIN.COM'
        basic=ROOT/'tests/fastbasic/stdin.bas'
        layout=compile_program(source,basic,binary,floating=floating)
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
        layout=compile_program(source,basic,binary,floating=floating)
        files.append((binary.name,binary.read_bytes()))
        calls.append('  Run(BYTE POINTER(c"RAM:ALLOC.COM"),NULL,0,20)\n  Require(secondary=103)')
        corpus.append(dict(name='allocation',source_sha256=sha256(basic),
                           binary_sha256=sha256(binary),layout=layout))
    extra = ''
    if group in ('compiler', 'all','capacity'):
        compiler_name = 'FBC' if floating else 'FBCI'
        files += [(compiler_name+'.COM', (source/f'build/bin/{compiler_name.lower()}.xex').read_bytes()),
                  ('SOURCE.BAS', b'? "ON MACHINE"\r\nA%=6.5\r\n? A%*2\r\nX%=1.234567895\r\n? X%' if floating else b'? "ON MACHINE"\r\nA=6\r\n? A*7'),
                  ('BROKEN.BAS', b'IF\x9b')]
        arguments = 'RAM:SOURCE.BAS RAM:FRESH.COM'
        calls.append(f'  currentCase=20\n  Run(BYTE POINTER(c"RAM:{compiler_name}.COM"),BYTE POINTER(c"{arguments}"),{len(arguments)},0)')
        calls.append('  currentCase=21\n  Run(BYTE POINTER(c"RAM:FRESH.COM"),NULL,0,0)')
        machine_output = b'ON MACHINE\x9b13\x9b1.23456789\x9b' if floating else b'ON MACHINE\x9b42\x9b'
        expected += b'Compiled RAM:FRESH.COM\x9b'+machine_output
        if group=='capacity':
            calls.append('''  LET capacityOutput=DOS.Open(BYTE POINTER(c"RAM:CAPERR.TXT"),DOS.MODE_NEWFILE)
  Require(capacityOutput<>NULL)
  LET savedOutput=DOS.SelectOutput(capacityOutput)
  sourceCapacity=$e000-sourceBase''')
            for index,delta in enumerate((-1,0,1)):
                arguments='RAM:BND.BAS RAM:BND.COM'
                calls.append(f'''  Put(BYTE POINTER(c"RAM:BND.BAS"),BYTE POINTER(ADDRESS(BOUND_SOURCE)),sourceCapacity{delta:+d})
  currentCase={30+index}
  Run(BYTE POINTER(c"RAM:{compiler_name}.COM"),BYTE POINTER(c"{arguments}"),{len(arguments)},-1)
  capacityResults({index*2})=primary
  capacityResults({index*2+1})=secondary
  Require(primary=0 OR primary=20)''')
            calls.append('''  DOS.SelectOutput(savedOutput)
  Require(DOS.Close(capacityOutput)<>0)
  Run(BYTE POINTER(c"RAM:FRESH.COM"),NULL,0,0)''')
            expected+=machine_output
        if group == 'all':
            arguments = 'RAM:BROKEN.BAS RAM:BAD.COM'
            calls.append(f'''  LET errorFile=DOS.Open(BYTE POINTER(c"RAM:ERROR.TXT"),DOS.MODE_NEWFILE)
  Require(errorFile<>NULL)
  LET normal=DOS.SelectOutput(errorFile)
  currentCase=22
  Run(BYTE POINTER(c"RAM:{compiler_name}.COM"),BYTE POINTER(c"{arguments}"),{len(arguments)},20)
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
            expected += machine_output
        extra = '''  LET generated=DOS.Open(BYTE POINTER(c"RAM:FRESH.COM"),DOS.MODE_OLDFILE)
  Require(generated<>NULL)
  freshBytes=CARD(DOS.Read(generated,@fresh,16384))
  Require(freshBytes>16 AND freshBytes<16384)
  Require(DOS.Close(generated)<>0)
  ; Structural admission precedes slot ownership and allocation.
  LET saved=fresh(4)
  fresh(4)=99
  Require(PROGRAM.Load(@fresh,LONGCARD(freshBytes))=NULL)
  Require(DOS.IoErr()=307)
  fresh(4)=saved
  LET savedTarget=fresh(6)
  fresh(6)=1
  Require(PROGRAM.Load(@fresh,LONGCARD(freshBytes))=NULL)
  Require(DOS.IoErr()=307)
  fresh(6)=savedTarget
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
    if group=='capacity':
        blob=0x300000+len(payload)
        payload+=(b' '*255+b'\x9b')*255+b' '*255
        calls=[call.replace('BOUND_SOURCE',f'${blob:x}') for call in calls]
    probe = out/'probe.act'
    template=(ROOT/'tests/programs/fastbasic.act').read_text()
    if group=='capacity':
        labels={name:int(address,16) for address,name in re.findall(
            r'al ([0-9A-Fa-f]+) \.(\S+)',(source/'build/bin/fbc.lbl').read_text())}
        template=template.replace('CARD checks,','CARD sourceBase,sourceCapacity\nLONGINT ARRAY capacityResults(6)\nCARD checks,')
        template=template.replace('Require(primary=expectedPrimary)','Require(expectedPrimary=-1 OR primary=expectedPrimary)')
        completion+=f'\n  IF currentCase=20 THEN\n    sourceBase=SDXSTATE.ReadWord(state.guest.bank,${labels["fb_var_MEMSTART"]:x})\n  FI'
    probe.write_text(template
                     .replace('SETUP_FILES', '\n'.join(setup))
                     .replace('RUN_PROGRAMS', '\n'.join(calls)).replace('EXTRA_CHECKS', extra)
                     .replace('; RUN_COMPLETION_CHECKS',completion))
    return probe, [(0x300000, bytes(payload))], expected, corpus


def run(out, group, replay=False, optimize=True, floating=False, decimal_probe=False,reuse_native=False):
    out.mkdir(parents=True, exist_ok=True)
    fastbasic_record=json.loads((ROOT/'build/fastbasic/build.json').read_text())
    previous=(out/'probe.act').read_text() if reuse_native else None
    probe, payload, expected, corpus = fixture(out, group, floating, decimal_probe)
    memory_profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    memory_profile['image_data_bytes'] = 40960
    memory = out/'memory-profile.json'
    memory.write_text(json.dumps(memory_profile))
    p = read_build(out) if replay or reuse_native else build(compiler(ROOT/'build/actionc', release=True),
        probe, out, optimize=optimize, tasks=True, task_capacity=8, console=False, console_test=True,
        sdx=True, image_data=payload, memory_profile=memory,
        dos_mounts=[dict(alias='RAM', format=3)])
    result = dict(status='running', tier='development', group=group, optimize=optimize, floating=floating, build=p['build'], pin=PIN,
                  corpus=corpus, decimal_probe=decimal_probe,fastbasic=fastbasic_record)
    from fastbasic_test_support import guest_inputs
    stimulus=guest_inputs(p,previous,probe.read_text(),payload) if reuse_native else None
    result['reused_native_fixture']=reuse_native
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        result['machine'] = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            result['runtime'], _ = execute(b, p, timeout=120, frame_limit=6000,before_run=stimulus)
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
        compared=actual
        if floating and group=='all':
            lines=actual.split(b'\x9b')
            # 4^0.5 uses the donor LOG10/EXP10 approximation, not SQR.
            index=8+13
            value=Decimal(lines[index].decode())
            require(abs(value-Decimal(2))<=Decimal('0.0000001'),'Power approximation outside tolerance')
            result['power_tolerance']=dict(actual=str(value),expected='2',absolute='0.0000001')
            lines[index]=b'2'
            compared=b'\x9b'.join(lines)
        require(compared == expected, f'Wrong output: {actual!r} != {expected!r}')
        if group in ('compiler', 'all','capacity'):
            generated_bytes = int.from_bytes(bytes(data(b, p['image'], 'freshBytes')), 'little')
            generated = bytes(data(b, p['image'], 'fresh'))[:generated_bytes]
            result['generated_profile'] = profile(generated)
            (out/'FRESH.COM').write_bytes(generated)
        if group=='capacity':
            result['source_base']=int.from_bytes(bytes(data(b,p['image'],'sourceBase')),'little')
            result['source_capacity']=int.from_bytes(bytes(data(b,p['image'],'sourceCapacity')),'little')
            raw=bytes(data(b,p['image'],'capacityResults'))
            outcomes=[int.from_bytes(raw[i:i+4],'little',signed=True) for i in range(0,24,4)]
            result['capacity_results']=outcomes
            require(outcomes[2:]==[20,306,20,306],f'Full/oversize source admission differs: {outcomes}')
            require(outcomes[:2] in ([0,0],[20,103]),f'Boundary source behavior differs: {outcomes}')
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
    parser.add_argument('--group', choices=('runtime', 'compiler', 'all','edges','capacity'), default='all')
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--raw', action='store_true', help='Focused unoptimized ABI check; use --group runtime')
    parser.add_argument('--float', dest='floating', action='store_true')
    parser.add_argument('--decimal-probe',action='store_true')
    parser.add_argument('--reuse-native',action='store_true',help='Reuse identical native fixture; install fresh guest inputs at paused bootstrap')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.group, args.replay, not args.raw, args.floating,args.decimal_probe,args.reuse_native)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
