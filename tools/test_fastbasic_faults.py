#!/usr/bin/env python3
"""Inject short writes and late failures at DOS calls in emitted guest adapters."""
import argparse
import json
from pathlib import Path

from build_fastbasic import ROOT, profile, sha256
from library_paths import read_source
from native_program import build, compiler, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    # Explicitly local overrides; production sources have no fault seam.
    (out/'fbfault.act').write_text((ROOT/'tests/programs/fbfault.act').read_text())
    for module in ('fbfiles','sdxfiles'):
        text=read_source(ROOT/f'lib/dos/{module}.act')
        text=text.replace('USE DOS\n','USE DOS\nUSE FBFAULT\n')
        for name in ('Open','Write','Close'):
            text=text.replace('DOS.'+name+'(', 'FBFAULT.'+name+'(')
        (out/(module+'.act')).write_text(text)
    compiler_bytes=(ROOT/'build/fastbasic/FBCI.COM').read_bytes()
    basic=b'? "FAULT RECOVERY"\x9b'
    arguments='RAM:SOURCE.BAS RAM:FRESH.COM'
    calls=[]
    for mode,error in ((1,221),(2,213),(3,221),(4,0),(0,0)):
        calls.append(f'''  FBFAULT.mode={mode}
  Run(BYTE POINTER(c"RAM:FBCI.COM"),BYTE POINTER(c"{arguments}"),{len(arguments)},{20 if error else 0})
  Require(secondary={error})''')
    calls.append('  Run(BYTE POINTER(c"RAM:FRESH.COM"),NULL,0,0)')
    extra='''  LET generated=DOS.Open(BYTE POINTER(c"RAM:FRESH.COM"),DOS.MODE_OLDFILE)
  Require(generated<>NULL)
  freshBytes=CARD(DOS.Read(generated,@fresh,4096))
  Require(DOS.Close(generated)<>0)'''
    text=(ROOT/'tests/programs/fastbasic.act').read_text().replace('USE DOS\n','USE DOS\nUSE FBFAULT\n')
    text=text.replace('SETUP_FILES',f'''  Put(BYTE POINTER(c"RAM:FBCI.COM"),BYTE POINTER($300000),{len(compiler_bytes)})
  Put(BYTE POINTER(c"RAM:SOURCE.BAS"),BYTE POINTER(${0x300000+len(compiler_bytes):x}),{len(basic)})''')
    text=text.replace('RUN_PROGRAMS','\n'.join(calls)).replace('EXTRA_CHECKS',extra)
    source=out/'probe.act';source.write_text(text)
    memory=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    memory['image_data_bytes']=16384
    memory_path=out/'memory-profile.json';memory_path.write_text(json.dumps(memory))
    p=build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,
            task_capacity=8,console=False,console_test=True,sdx=True,
            memory_profile=memory_path,dos_mounts=[dict(alias='RAM',format=3)],
            image_data=[(0x300000,compiler_bytes+basic)])
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=150,frame_limit=7500)
        except Exception:
            print({name:data(b,p['image'],name,True) for name in
                   ('checks','primary','secondary','reason')},flush=True)
            raise
        ownership(b,p,out)
        count=int.from_bytes(bytes(data(b,p['image'],'actualBytes')),'little')
        actual=bytes(data(b,p['image'],'actual'))[:count]
        require(actual.endswith(b'FAULT RECOVERY\x9b'),repr(actual))
        count=int.from_bytes(bytes(data(b,p['image'],'freshBytes')),'little')
        generated=profile(bytes(data(b,p['image'],'fresh'))[:count])
        checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
    return dict(status='pass',tier='development',scope='Test-only DOS boundary overrides with real file ownership; short writes, write error, late Close error, first-cause retention, recovery and full heap reclamation',
                build=p['build'],machine=machine,runtime=runtime,checks=checks,
                compiler_sha256=sha256(ROOT/'build/fastbasic/FBCI.COM'),
                generated=generated,actual_hex=actual.hex())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/fastbasic/faults')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out)
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('FastBasic fault checks:',result['checks'])
