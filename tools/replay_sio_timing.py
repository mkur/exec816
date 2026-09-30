#!/usr/bin/env python3
"""Replay saved recovery/deadline images unchanged without the passive observer."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,execute,require,sha256,verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from test_sio_recovery import CASES
from test_cooperative import data
from sio_transactions import disk_image
from banked_test_memory import read as far_read

def replay(directory,kind):
    record=json.loads((directory/'results.json').read_text())
    require(record['status']=='pass','Cannot replay failed evidence')
    labels={}
    for filename in ('hosted.lbl','loader.lbl'):
        for line in (directory/filename).read_text().splitlines():
            fields=line.split();labels[fields[2].lstrip('.')]=int(fields[1],16)
    p=dict(xex=directory/'program.xex',labels=labels,image=json.loads((directory/'program.a816.json').read_text()),build=record['build'])
    require(sha256(p['xex'])==record['build']['xex_sha256'],'Changed replay image')
    binary=ROOT/'build/altirra-sio-multi'
    require(sha256(binary/'AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned replay emulator')
    for key in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS','EXEC816_SIO_FAULT_FILE'):os.environ.pop(key,None)
    out=directory/'uninstrumented';out.mkdir(exist_ok=True)
    with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        b.config('diskemu','fastest');verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        for index,case in enumerate(record['cases']):
            if index:b.state_load(slot='loaded')
            caseout=out/case['name'];caseout.mkdir(exist_ok=True)
            if kind=='recovery':
                scenario,unit,error,offline,fault=CASES[case['name']]
                require(not fault and scenario in (2,4,6),'Only timed non-responder cases can use the uninstrumented binary')
                disk_image(caseout/'disk.atr')
                values=dict(kind=scenario,unit=unit,expected=error,offlineExpected=offline)
            else:values=dict(explicit=index)
            def before(b):
                if not index:b.state_save(slot='loaded')
                if kind=='recovery':b.mount(0,str(caseout/'disk.atr'))
                for name,value in values.items():
                    symbol=next(d for d in p['image']['data'] if '_'+name.upper()+'_' in d['name'])
                    b.poke(symbol['address'],value)
            runtime,_=execute(b,{**p,'output':caseout},before_run=before,preloaded=bool(index),expected_status=case['runtime']['status'],timeout=240,frame_limit=12000)
            hardware=far_read(b,p['build']['task_storage']['BASE']+0x800,128,caseout).hex()
            require(runtime==case['runtime'] and hardware==case['hardware'],'Observer/replay result mismatch')
            require(data(b,p['image'],'checks',True)==case.get('checks',[137]),'Observer/replay assertion mismatch')
    record['replay']=dict(status='identical',xex_sha256=sha256(p['xex']),emulator_sha256=PIN['emulator']['sha256'],cases=[c['name'] for c in record['cases']])
    (directory/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Unchanged timing replay passed',directory.name)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=('profile','recovery'),required=True);p.add_argument('--input',type=Path,required=True)
    args=p.parse_args();replay(args.input.resolve(),args.kind)
