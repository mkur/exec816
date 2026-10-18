#!/usr/bin/env python3
"""Public SetFileDate, failure/ownership and independent persisted SDFS bytes."""
import argparse,json,struct,time
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine
from os_boundary import emulator
from test_sdx_md5 import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership
from sdfs_reference import make


def run(out,raw):
    source=out/'probe.act'
    source.write_text((ROOT/'tests/programs/dos_file_date.act').read_text().replace('DISK_CASES','' if raw else '  Check(BYTE POINTER(c"D1:DATE.BIN"))'))
    mounts=[dict(alias='RAM',format=3)]
    if not raw:
        empty=out/'empty';empty.mkdir(exist_ok=True)
        make(out/'volume.atr',empty,1024,256,'DATE')
        mounts.append(dict(alias='D1',format=2,device='sio.device',unit=49,sectors=1024,sector_bytes=256,access='readwrite',profile=4))
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4096
    (out/'memory-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    program=build(compiler(ROOT/'build/actionc',release=True),source,out,optimize=not raw,tasks=True,task_capacity=8,console_deferred=True,dos_mounts=mounts,memory_profile=out/'memory-profile.json')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','generic56k');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        if not raw:b.mount(0,str(out/'volume.atr'))
        try:runtime,_=execute(b,program,timeout=180,frame_limit=9000)
        except Exception:
            print({k:data(b,program['image'],k) for k in ['checks','reason']},flush=True);raise
        ownership(b,program,out);checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
        if not raw:
            time.sleep(3);b._cmd_ok('EJECT drive=0')
    if not raw:
        disk=(out/'volume.atr').read_bytes();at=disk.index(b'DATE    BIN')
        assert disk[at+11:at+17]==bytes([18,10,26,14,32,14]),disk[at+11:at+17].hex()
    return dict(status='pass',tier='development',mode='raw' if raw else 'opt',checks=checks,machine=machine,runtime=runtime,build=program['build'],bank_zero_delta=dict(fixed=0,per_task=0))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(out,a.raw)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SetFileDate',result['status'],result['checks'],flush=True)
