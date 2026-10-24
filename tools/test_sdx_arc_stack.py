#!/usr/bin/env python3
"""Force the recursive ARC gate's resource failure and check archive rollback."""
import argparse
import json
from pathlib import Path

from arc_archive import member
from native_program import ROOT,build,compiler,verify_machine,sha256
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership
from test_sdx_md5 import PIN


def run(out):
    original=member('OLD.BIN',b'old')+b'\x1a\0'
    files={name:(ROOT/'build/sdx-inputs/arc'/name).read_bytes()
           for name in ('ARC.COM','ARCLST.OVL','ARCADD.OVL','ARCEXT.OVL')}
    files.update({'NEW.ARC':original,'TEXT.BIN':bytes(range(256))*64})
    payload=bytearray();setup=[];addresses={}
    for name,raw in files.items():
        at=0x300000+len(payload);addresses[name]=at;payload+=raw
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${at:x})),{len(raw)})')
    text=(ROOT/'tests/programs/sdx_arc_mutate.act').read_text()
    text=text[:text.index('  Run(0,')]+f'''  Run(0,BYTE POINTER(c"A NEW.ARC TEXT.BIN"),18,20,158)
  Verify(BYTE POINTER(c"RAM:NEW.ARC"),BYTE POINTER(ADDRESS(${addresses['NEW.ARC']:x})),{len(original)},0)
  NoTemporary()
  Require(DOS.ReleaseContext()<>0)
  Require(FSBOOT.Stop()<>0)
  Require(EXEC.AvailMem(0)=baseline)

RETURN

ENDMODULE
'''
    source=out/'probe.act';source.write_text(text.replace('SETUP_FILES','\n'.join(setup)))
    # Force the normal resource-error path on a small real archive. Production
    # uses $01A0; this override cannot permit an unsafe entry or change cleanup.
    service=(ROOT/'lib/dos/sdxservice.act').read_text().replace('SDXABI.ARC_STACK_MINIMUM_S','$1ff')
    (out/'sdxservice.act').write_text(service)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=32768
    memory=out/'memory-profile.json';memory.write_text(json.dumps(profile))
    p=build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,
            task_capacity=12,console=False,console_test=True,sdx=True,
            image_data=[(0x300000,bytes(payload))],memory_profile=memory,
            dos_mounts=[dict(alias='RAM',format=3)])
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=180,frame_limit=9000)
        except Exception:
            print({k:data(b,p['image'],k) for k in ('checks','primary','secondary','reason')},flush=True)
            raise
        ownership(b,p,out)
        checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
    return dict(status='pass',tier='development',qualification=False,checks=checks,
                runtime=runtime,machine=machine,build=p['build'],
                injection=dict(threshold=511,production_threshold=416,source_sha256=sha256(out/'sdxservice.act')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out)
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ARC stack failure:',result['checks'],'checks passed')
