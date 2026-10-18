#!/usr/bin/env python3
"""Emitted native SDX decoder against the independent host placement oracle."""
import argparse
import json
from pathlib import Path
import struct
import time

from native_program import ROOT, build, compiler, verify_machine
from os_boundary import emulator
from sdx_file import parse, place
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import module_files, PIN


def fixture(out, smoke):
    origin, payload = 0x180000, bytearray()
    code, symbols, cases = [], {}, []

    def store(raw):
        address = origin + len(payload)
        payload.extend(raw)
        return f'BYTE POINTER(ADDRESS(${address:x}))'

    files = module_files(ROOT/'build/sdx-inputs/md5', ROOT/'build/sdx-inputs/arc')
    for path in files.values():
        for name in parse(path.read_bytes()).imports:
            symbols.setdefault(name, 0xe000 + len(symbols)*32)
    resolver = []
    for name, address in symbols.items():
        ptr = store(name.encode().ljust(8, b' '))
        resolver.append(f'  IF O65READ.Equal(name,{ptr},8)<>0 THEN\n    RETURN(${address:x})\n  FI')
    for filename, path in files.items():
        raw = path.read_bytes()
        program = parse(raw)
        ptr = store(raw)
        for base in ((0x2000,) if smoke else (0x2000, 0x4100)):
            expected, layout = place(program, base, 0xe000, symbols)
            oracle = store(expected[base:layout['end']])
            code.append(f'''  A816MEMORY.Clear(bank,65536)
  layout=SDXFILE.Load({ptr},{len(raw)},bank,${base:x},$e000,@Resolve,NULL,0)
  Require(layout<>NULL)
  Require(layout.end=${layout['end']:x})
  Require(layout.blockCount={len(program.blocks)})
  Require(O65READ.Equal(bank+${base:x},{oracle},{layout['end']-base})<>0)''')
            for name, at in layout['exports'].items():
                nameptr = store(name.encode().ljust(8, b' '))
                code.append(f'  Require(SDXFILE.Symbol(layout,{nameptr})=${at:x})')
            code.append('  SDXFILE.Release(layout)')
            cases.append(dict(file=filename, placement=base, end=layout['end']))
        if smoke:
            break
    # Forward base/export, nonzero assembled origins, page alignment and BSS.
    block = lambda n,c,at,b: struct.pack('<HBBHH',0xfffe,n,c,at,len(b))+(b if not c&128 else b'')
    fix = lambda n,s: struct.pack('<HBH',0xfffd,n,len(s))+s
    exp = struct.pack('<HBH',0xfffc,2,0x502)+b'MAIN    '
    raw = (exp+fix(2,b'\xfe\x01\x01\xfc')+block(1,0,0x200,b'\xea\x02\x05')
           +block(2,0xc0,0x500,bytes(9)))
    expected, layout = place(parse(raw),0x4021,0xe000,{})
    ptr, oracle = store(raw), store(expected[0x4021:layout['end']])
    code.append(f'''  A816MEMORY.Clear(bank,65536)
  layout=SDXFILE.Load({ptr},{len(raw)},bank,$4021,$e000,@Resolve,NULL,0)
  Require(layout<>NULL)
  Require(O65READ.Equal(bank+$4021,{oracle},{layout['end']-0x4021})<>0)
  SDXFILE.Release(layout)''')
    valid = block(1,0,0,b'\x00\x00\x00\x00')
    # One import, two caller-owned parent namespaces. Each load must use its
    # own binding, including a nonzero original operand addend.
    bound = block(1,0,0,b'\x03\x00')+struct.pack('<H',0xfffb)+b'_ARC    '+b'\x04\x00\xfe\x01\x00\xfc'
    ptr = store(bound)
    nameptr = store(b'_ARC    ')
    code.append(f'''  A816MEMORY.Move(@parent.name,{nameptr},8)
  parent.value=$3959
  layout=SDXFILE.Load({ptr},{len(bound)},bank,$3000,$e000,@Resolve,@parent,1)
  Require(layout<>NULL)
  Require(bank($3000)=$5c AND bank($3001)=$39)
  SDXFILE.Release(layout)
  parent.value=$4750
  layout=SDXFILE.Load({ptr},{len(bound)},bank,$3000,$e000,@Resolve,@parent,1)
  Require(layout<>NULL)
  Require(bank($3000)=$53 AND bank($3001)=$47)
  SDXFILE.Release(layout)''')
    invalid = [b'', b'\xfe\xff\x01', valid[:-1], valid+valid,
               valid+fix(2,b'\xfc'), valid+fix(1,b'\x01\xfc'),
               valid+fix(1,b'\xfe\x01\x03\xfc'),
               valid+fix(1,b'\xfe\x01\x00\x01\xfc'),
               valid+struct.pack('<H',0xfffb)+b'MISSING '+b'\x01\x00\xfc',
               block(1,128,0,bytes(4))+fix(1,b'\xfe\x01\x00\xfc'),
               valid+fix(1,b'\xfe\x01\xfd\xfc'),
               valid+fix(1,b'\xfe\x01\x00\xfc\x00'),
               valid+struct.pack('<HBH',0xfffc,1,4)+b'MAIN    ']
    for raw in invalid:
        ptr = store(raw)
        code.append(f'  Require(SDXFILE.Load({ptr},{len(raw)},bank,$2000,$e000,@Resolve,NULL,0)=NULL)')
    source = out/'probe.act'
    source.write_text('''MODULE SDXLOADERPROBE
USE EXEC
USE HEAPCORE
USE O65READ
USE SDXFILE
USE A816MEMORY
USE DOSCLIENT
CARD checks
LONGINT reason

PROC Require(BYTE okay)

  IF okay=0 THEN
    reason=DOSCLIENT.IoErr()
    HEAPCORE.Abort($f900+checks)
  FI
  checks==+1

RETURN

CARD FUNC Resolve(BYTE POINTER name)

'''+ '\n'.join(resolver)+'''

RETURN(0)

PROC Main()
  SDXFILE.Layout POINTER layout
  SDXFILE.Binding parent
  BYTE POINTER bank

  bank=BYTE POINTER(ADDRESS($300000))
  A816MEMORY.Clear(bank,65536)
'''+ '\n'.join(code)+'\n\nRETURN\n\nENDMODULE\n')
    return source, [(origin,bytes(payload)),(0x300000,bytes(65536))], cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('opt','raw'),default='opt')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    result=dict(status='running')
    try:
        source,payload,cases=fixture(out,args.case=='raw')
        program=build(compiler(ROOT/'build/actionc',release=True),source,out,
                      optimize=args.case=='opt',tasks=True,task_capacity=8,
                      console=False,image_data=payload)
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            try:
                runtime,_=execute(b,program,timeout=180,frame_limit=9000)
            except Exception:
                print('Decoder checks:',data(b,program['image'],'checks'),'reason:',data(b,program['image'],'reason'),flush=True)
                raise
            ownership(b,program,out)
            checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
        result=dict(status='pass',tier='development',mode=args.case,checks=checks,
                    cases=cases,machine=machine,runtime=runtime,build=program['build'],
                    bank_zero_delta=dict(fixed=0,per_task=0))
    except Exception as error:
        result.update(status='fail',error=str(error))
        raise
    finally:
        result['seconds']=round(time.monotonic()-started,3)
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SDX decoder:',checks,'checks passed',flush=True)


if __name__=='__main__':
    main()
