#!/usr/bin/env python3
"""Inject short writes and late failures at DOS calls in emitted guest adapters."""
import argparse
import json
from pathlib import Path

from build_fastbasic import ROOT, profile, sha256
from library_paths import read_source
from native_program import build, compiler, require, verify_machine, read_build
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN


def run(out, floating=False,reuse_native=False):
    out.mkdir(parents=True,exist_ok=True)
    previous=(out/'probe.act').read_text() if reuse_native else None
    # Explicitly local overrides; production sources have no fault seam.
    (out/'fbfault.act').write_text((ROOT/'tests/programs/fbfault.act').read_text())
    for module in ('fbfiles','sdxfiles'):
        text=read_source(ROOT/f'lib/dos/{module}.act')
        text=text.replace('USE DOS\n','USE DOS\nUSE FBFAULT\n')
        for name in ('Open','Write','Close'):
            text=text.replace('DOS.'+name+'(', 'FBFAULT.'+name+'(')
        (out/(module+'.act')).write_text(text)
    compiler_name='FBC' if floating else 'FBCI'
    compiler_path=ROOT/('build/fastbasic/'+compiler_name+'.COM')
    compiler_bytes=compiler_path.read_bytes()
    basic=b'? "FAULT RECOVERY"\x9b? 1.25*2.0\x9b' if floating else b'? "FAULT RECOVERY"\x9b'
    arguments='RAM:SOURCE.BAS RAM:FRESH.COM'
    calls=[]
    for mode,error in ((1,221),(2,213),(3,221),(4,0),(0,0)):
        calls.append(f'''  FBFAULT.mode={mode}
  Run(BYTE POINTER(c"RAM:{compiler_name}.COM"),BYTE POINTER(c"{arguments}"),{len(arguments)},{20 if error else 0})
  Require(secondary={error})''')
    calls.append('  Run(BYTE POINTER(c"RAM:FRESH.COM"),NULL,0,0)')
    extra='''  LET generated=DOS.Open(BYTE POINTER(c"RAM:FRESH.COM"),DOS.MODE_OLDFILE)
  Require(generated<>NULL)
  freshBytes=CARD(DOS.Read(generated,@fresh,16384))
  Require(DOS.Close(generated)<>0)'''
    text=(ROOT/'tests/programs/fastbasic.act').read_text().replace('USE DOS\n','USE DOS\nUSE FBFAULT\n')
    text=text.replace('SETUP_FILES',f'''  Put(BYTE POINTER(c"RAM:{compiler_name}.COM"),BYTE POINTER($300000),{len(compiler_bytes)})
  Put(BYTE POINTER(c"RAM:SOURCE.BAS"),BYTE POINTER(${0x300000+len(compiler_bytes):x}),{len(basic)})''')
    text=text.replace('RUN_PROGRAMS','\n'.join(calls)).replace('EXTRA_CHECKS',extra)
    source=out/'probe.act';source.write_text(text)
    memory=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    memory['image_data_bytes']=32768
    memory_path=out/'memory-profile.json';memory_path.write_text(json.dumps(memory))
    p=read_build(out) if reuse_native else build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,
            task_capacity=8,console=False,console_test=True,sdx=True,
            memory_profile=memory_path,dos_mounts=[dict(alias='RAM',format=3)],
            image_data=[(0x300000,compiler_bytes+basic)])
    from fastbasic_test_support import guest_inputs
    stimulus=guest_inputs(p,previous,text,[(0x300000,compiler_bytes+basic)]) if reuse_native else None
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=150,frame_limit=7500,before_run=stimulus)
        except Exception:
            print({name:data(b,p['image'],name,True) for name in
                   ('checks','primary','secondary','reason')},flush=True)
            raise
        ownership(b,p,out)
        count=int.from_bytes(bytes(data(b,p['image'],'actualBytes')),'little')
        actual=bytes(data(b,p['image'],'actual'))[:count]
        require(actual.endswith(b'FAULT RECOVERY\x9b2.5\x9b' if floating else b'FAULT RECOVERY\x9b'),repr(actual))
        count=int.from_bytes(bytes(data(b,p['image'],'freshBytes')),'little')
        generated=profile(bytes(data(b,p['image'],'fresh'))[:count])
        checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
    return dict(status='pass',tier='development',scope='Test-only DOS boundary overrides with real file ownership; short writes, write error, late Close error, first-cause retention, recovery and full heap reclamation',
                build=p['build'],machine=machine,runtime=runtime,checks=checks,
                compiler_sha256=sha256(compiler_path),floating=floating,reused_native_fixture=reuse_native,
                generated=generated,actual_hex=actual.hex())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/fastbasic/faults')
    parser.add_argument('--float',dest='floating',action='store_true')
    parser.add_argument('--reuse-native',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out,args.floating,args.reuse_native)
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('FastBasic fault checks:',result['checks'])
