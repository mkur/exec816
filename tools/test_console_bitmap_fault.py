#!/usr/bin/env python3
"""Quiesced display failure retires I/O; unquiesced DMA retains it for reset."""
import argparse,json
from pathlib import Path
from build_bitmap_console import build_bitmap
from native_program import ROOT,read_build,require,verify_machine
from test_mouse_observe import PIN,BRIDGE,ROM
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
import adapter_state as adapter
from generate_console import constants
LAYOUT=constants()


def run(out,mode,replay=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if replay else build_bitmap(ROOT/'tests/programs/console_bitmap_fault.act',out,mode=='opt',fault=True)
    sy=json.loads((out/'c-image.json').read_text())['symbols']
    at=lambda name:next(d['address'] for d in p['image']['data'] if '_BITMAPFAULT_'+name+'_' in d['name'])
    result=dict(status='running',tier='development',mode=mode,build=p['build'],cases=[])
    try:
        for fault in (1,2,3,4,5,6,7,8):
            folder=out/f'fault-{fault}';folder.mkdir(exist_ok=True)
            with emulator(BRIDGE,ROM,folder,pin=PIN) as b:
                machine=verify_machine(b,ROM,PIN);saved={}
                def before(b):
                    b.memload(at('VARIANT'),bytes([fault]))
                    saved['at']=b.peek16(88);saved['screen']=b.memdump(saved['at'],960)
                    saved['display']=b.memdump(0x22f,3)
                    marker=p['labels']['native_nmi'];condition=f'dw(${at("CHECKPOINT"):x})=1'
                    b.bp_set(marker,condition=condition);run_to(b,marker,condition=condition,frame_limit=8000,timeout=90);b.bp_clear_all()
                    if 3<=fault<=4:
                        owner=int.from_bytes(b.memdump(at('OWNER'),3),'little')
                        instance=int.from_bytes(b.memdump(owner+19,3),'little')
                        saved['instance']=instance
                        # Arm the copy-triggered fault after the warm-up scrolls.
                        b.memload(sy['ConsoleCopyChunks'],b'\0\0')
                        require(b.peek16(instance+LAYOUT['INSTANCE_CELLORIGIN'])==2320,'Missing wrapped fault setup')
                    b.memload(sy['ConsoleFaultMode'],fault.to_bytes(2,'little'));b.memload(at('GATE'),b'\1\0')
                runtime,_=execute(b,p,before_run=before,expected_status=0 if fault&1 else 0xff93,frame_limit=8000,timeout=90)
                require(b.peek16(sy['ConsoleStopCount'])==1,'Missing single STOP')
                if 3<=fault<=4:require(b.peek16(sy['ConsoleCopyChunks'])==1,'Fault was not after the scroll launch')
                if fault>=5:require(b.peek16(sy['ConsoleTextChunks'])==1,'Missing first text batch fault or later batch launched')
                if fault>=7:require(b.peek16(sy['ConsoleTextFillRows'])==1,'Fault missed the combined text/caret list')
                if fault&1:
                    ownership(b,p,p['output'])
                    require(b.memdump(saved['at'],960)==saved['screen'] and b.memdump(0x22f,3)==saved['display'],'Quiesced fault did not restore OS')
                else:
                    read=int.from_bytes(b.memdump(at('READ'),3),'little')
                    require(b.memdump(read+6,1)==bytes([5]),'Reset-required failure replied to retained I/O')
                    if fault==4:
                        require(b.peek16(saved['instance']+LAYOUT['INSTANCE_CELLORIGIN'])==0,'Reset-required failure lost the committed wrap')
                result['cases'].append(dict(fault=fault,machine=machine,runtime=runtime,checks=data(b,p['image'],'checks',True)))
        result['status']='pass'
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Bitmap fault handling passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true');a=p.parse_args();run(a.output,a.mode,a.replay)
