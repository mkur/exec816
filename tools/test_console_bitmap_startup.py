#!/usr/bin/env python3
"""Bitmap startup rollback, absent hardware and compatible FX revisions."""
import argparse,copy,json
from pathlib import Path
import generate_tasks
from build_bitmap_console import build_bitmap
from native_program import ROOT,read_build,require,verify_machine
from test_mouse_observe import PIN,BRIDGE,ROM
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data


def run(out,mode,replay=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    (out/'consolestartprobe.act').write_bytes((ROOT/'tests/programs/consolestartprobe.act').read_bytes())
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs);path=directory/'consoledriver.act'
        text=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE CONSOLESTARTPROBE\n',1)
        lifetime=(ROOT/'lib/console/console-lifetime.inc').read_text();needle='  service.generation==+1'
        require(lifetime.count(needle)==1,'Worker admission changed')
        lifetime=lifetime.replace(needle,needle+'\n  IF CONSOLESTARTPROBE.reservedBit<>0 THEN item.tc_SigAlloc=item.tc_SigAlloc OR (LONGCARD(1) LSH CONSOLESTARTPROBE.reservedBit) FI')
        target=directory/'console-lifetime-probe.inc';target.write_text(lifetime)
        path.write_text(text.replace(str(ROOT/'lib/console/console-lifetime.inc'),str(target)))
        return directory
    generate_tasks.policy_modules=instrument
    try:p=read_build(out/'program') if replay else build_bitmap(ROOT/'tests/programs/console_bitmap_startup.act',out,mode=='opt')
    finally:generate_tasks.policy_modules=original
    result=dict(status='running',tier='development',mode=mode,build=p['build'],cases=[])
    try:
        for name in ('rollback','absent','compatible'):
            folder=out/name;folder.mkdir(exist_ok=True);pin=copy.deepcopy(PIN)
            if name=='absent':pin['machine']['addons']='off';pin['devices']=[]
            if name=='compatible':pin['devices'][0]['settings']['version']=124;pin['devices'][0]['readback'][0]['bytes'][1]=0x24
            with emulator(BRIDGE,ROM,folder,pin=pin) as b:
                machine=verify_machine(b,ROM,pin);saved={}
                def before(b):
                    b.poke(p['build']['memory']['boot_config']['address']+7,0)
                    saved['at']=b.peek16(88);saved['screen']=b.memdump(saved['at'],960)
                    saved['os']=b.memdump(0x22f,3);saved['input']=b.memdump(0x208,2)
                try:
                    runtime,_=execute(b,p,before_run=before,expected_status=0xf731 if name=='absent' else 0,frame_limit=15000,timeout=120)
                except Exception:
                    names=('checks','heldCount','baseline','remaining','heldReady')
                    print('Startup failure',name,{n:data(b,p['image'],n,n=='checks') for n in names},flush=True)
                    raise
                require(b.memdump(0x22f,3)==saved['os'],'Startup changed OS display registers')
                if name=='absent':
                    from test_boot_diagnostics import os_text
                    require('NO VBXE; IDs=' in os_text(b),'Missing hardware was not reported')
                else:
                    require(b.memdump(saved['at'],960)==saved['screen'],'Startup changed OS display')
                require(b.memdump(0x208,2)==saved['input'],'Startup changed input')
                ownership(b,p,p['output'])
                result['cases'].append(dict(name=name,machine=machine,runtime=runtime,checks=data(b,p['image'],'checks',True)))
        result['status']='pass'
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Bitmap startup passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true');a=p.parse_args();run(a.output,a.mode,a.replay)
